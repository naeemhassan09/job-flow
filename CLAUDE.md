# CareerOS AI — Working Notes for Claude

This file briefs you when you join this repo. Read it before doing work.

## What this is

CareerOS AI is a **LangGraph-based agentic workflow platform**. The job-search use case is the reference application that demonstrates the platform end-to-end. Treat the platform as the product; the JD-scoring/cover-letter flow is the demo.

Full spec: [product-requirements/CareerOS_AI_Product_Spec_v2.md](product-requirements/CareerOS_AI_Product_Spec_v2.md). When the spec and this file disagree, the spec wins — fix this file.

## Geography

CareerOS AI is currently **Ireland-first** (`default_country: ie`). Defaults across the codebase assume the Irish market:

- Scraper queries default to Ireland (Adzuna `ie`, Reed UK+IE).
- Cover-letter prompts mention Stamp 1G / Critical Skills Permit context.
- Salaries/budgets are in EUR.
- The author is Dublin-based.

**Country is a single knob**: `default_country` in `config/profile.yml`. Change it + the `locations[]` entries to target another market. Reed will return zero results outside UK/IE (disable it via `sources.reed.enabled: false`). Adzuna supports 15 countries. **Never hardcode country assumptions** in code — read from `UserProfile.default_country` or `SearchLocation.country`.

## Auth (single-user, session cookie)

The UI and most of the API are gated by a session cookie issued after login.

- **Password**: bcrypt hash stored in `app_settings` (encrypted at rest).
- **Session**: signed cookie via `itsdangerous`, 7-day TTL, HttpOnly, SameSite=lax.
- **First run**: visit `/` → redirect to `/ui/login.html` in setup mode → POST `/api/auth/init` creates the admin.
- **Whitelist (no cookie required)**: `/healthz`, `/metrics`, `/api/captures` (uses bearer token instead), `/api/auth/*`, `/ui/login.html` and the bundles it needs (`login.css`, `login.js`, `styles.css`), `/docs`, `/openapi.json`.
- **Adding a new endpoint?** It is auth-gated by default (the middleware in `app/main.py` requires a session for everything under `/api/` and `/ui/` not in the whitelist). If you genuinely need it public, add the prefix to `auth.WHITELIST_PREFIXES` with a one-line comment justifying why.

The Chrome extension authenticates with `EXTENSION_API_TOKEN` (bearer) and CORS, not with the session cookie. This is intentional — extension origins are noisy and cookies across `chrome-extension://` are messy.

## Settings store

Runtime-editable config (API keys, model overrides, budget caps, admin hash) lives in the `app_settings` table, AES-GCM encrypted with the 32-byte key from `PII_ENCRYPTION_KEY`. The key is auto-generated and persisted to `.env` on first use if missing.

Read precedence at request time: **DB value if present → env var → hardcoded default**. Use `app.settings_store.get(name)` for DB-only reads, or `app.settings_store.effective_secret(name, env_value)` for the standard precedence chain.

When writing code that uses an API key or model name, **never** read directly from `os.environ` or `get_settings()` — go through `settings_store` so the user's UI overrides take effect without restarting.

The user-facing surface for these settings is `/ui/settings.html` + `app/api/settings.py`. To expose a new editable setting:

1. Add an entry to `API_KEY_FIELDS` / `BUDGET_FIELDS` in `app/api/settings.py`, or extend the `model.<task>.<which>` pattern. Anything else 400s on PUT (`_ALLOWED_BARE_KEYS` is an explicit allow-list).
2. Update `Settings` (`app/config.py`) so the env-fallback path works.
3. Update the consumer (provider / scraper / router) to read via `settings_store.effective_secret(name, env_value)`.
4. Wrap the settings_store call in `try/except` if it sits in a hot path — overrides degrade gracefully when the DB isn't reachable (e.g. in unit tests).

## Non-negotiables (from the spec)

1. **No autonomous outbound messaging.** No email, no DMs, no auto-apply.
2. **No scraping of LinkedIn/Indeed/job boards.** JDs come via paste, official APIs (Adzuna, Reed), or the browser-extension companion.
3. **No fabrication.** Every CV bullet must be evidence-backed against the candidate profile.
4. **No SQLite in "production" code paths.** Postgres from day one.
5. **No embeddings / RAG in V1.** The CV+JD pair is one document each — structured prompting beats vector search.
6. **No reflection loop in V1.** N=1 user → no statistical signal.
7. **Don't call services "agents."** A CRUD service is a service. Only the LangGraph `research` node is a real agentic loop.
8. **Real numbers only.** No aspirational metrics in README or docs — run the eval, paste real numbers.

## Architecture (one-paragraph version)

FastAPI fronts a **LangGraph workflow** with 5 functional nodes (`preprocess`, `profile`, `matcher`, `generator`, `evaluator`) plus 1 agentic loop (`research`). State is persisted in **Postgres** via the LangGraph Postgres checkpointer; workflows are resumable across process restarts and pause at a **HITL approval gate** before final artifact persistence. LLM calls go through a **provider abstraction** (`OpenAIProvider`, `AnthropicProvider`) routed by a **cost-aware router** with a hard monthly **budget guard**. Every call writes a row to `llm_usage_events`. Untrusted inputs (JDs) are **PII-redacted** and screened by an **injection classifier**. An **MCP server** exposes `analyze_jd`, `score_fit`, `generate_cover_letter`, `research_company`, `list_applications` as tools for Claude Desktop. Eval harness runs 50 labeled JD/CV pairs in CI and blocks PRs on >5% regression.

See [product-requirements/ARCHITECTURE.md](product-requirements/ARCHITECTURE.md) for the diagram.

## Repo layout

```
app/
  main.py            FastAPI entrypoint
  api/               REST routes + SSE streaming
  mcp/               MCP server
  graph/             LangGraph workflow + state + checkpointer
  nodes/             one file per node (preprocess, profile, research_loop, matcher, generator, evaluator)
  llm/               provider abstraction, router, caching, budget guard, cost calculator
  security/          PII redactor, injection classifier
  db/                SQLAlchemy models + Alembic migrations
  prompts/           versioned prompt templates
evals/
  dataset/           50 labeled JD/CV pairs
  runners/           eval scripts
  reports/           generated benchmark output
frontend/            Next.js single-page UI
extension/           Chrome companion for LinkedIn/Indeed JD capture
tests/               pytest suite
deploy/              Cloud Run + ECS reference
product-requirements/  PRD + spec + architecture + threat model
.claude/skills/      project-specific skills
```

## Research loop (agentic, plan → act → observe → stop)

The one real agentic loop in the system. Spec Section 5.2 / Section 25.8. Code lives in `app/research/` (tools + agent) and is invoked via the SSE endpoint `POST /api/jobs/{id}/research`.

Hard invariants — break these and the loop becomes either unsafe or non-agentic:

- **`MAX_ITERATIONS = 6`** in `app/research/agent.py`. Don't raise without proving (via the eval harness, when it exists) that quality keeps improving past 6.
- **Dedupe sets** on queries and URLs are mandatory. The planner LLM will repeat itself; the loop must catch this before another tool call burns budget.
- **All tools are exception-tolerant.** A failed web_search or a 404 fetch_url returns a result with `error` set, never raises. The agent treats it as an observation and moves on.
- **Tool output is wrapped in `<observation>` tags** before the planner sees it. The system prompt explicitly says content inside those tags is data, not instructions. Don't remove that defence.
- **The trace is append-only.** Every plan step, tool result, and dedupe rejection goes in `research_trace`. The UI uses it to make the agent's reasoning visible; the eval harness (Week 4) will score loop quality off it.
- **Default model**: `research_step` task → `openai/gpt-4.1-mini` (default per spec routing) — short cheap calls, lots of them. Override via Settings if you want Claude Haiku instead.

When adding a new tool: implement it in `app/research/tools.py`, return a dataclass with `error: str | None`, register the action in `app/prompts/research_plan.md`'s system prompt, then handle the new action branch in `agent.run_research`. Don't bypass the router for streaming; we want usage events recorded.

## Cover-letter generation (streaming, draft, approve)

Cover letters for discovered jobs are drafted inline via the SSE endpoint `POST /api/jobs/{id}/generate`. Read [spec section 25.7](product-requirements/CareerOS_AI_Product_Spec_v2.md) before changing anything in this area.

Key invariants:

- **Provider streaming contract**: every provider exposes `stream_text(request)` that yields `StreamDelta(text=...)` events and terminates with a single `LLMResponse` carrying real usage stats (token counts come from the provider's own stream events — `stream_options.include_usage` for OpenAI, `get_final_message()` for Anthropic). Don't change this shape without updating both providers and `Router.route_stream`.
- **Router fallback applies only before any delta is emitted.** Mid-stream errors propagate to the client; we never silently swap providers after the user has seen partial text.
- **Approval is the only thing the user touches.** The system never auto-approves. Regenerating over an approved letter requires `?force=true` (UI confirms via `confirm()`).
- **`cover_letter_total_cost_eur` is append-only.** Don't reset it on regenerate or approve. It's the audit trail of how much budget went into this single letter across all its revisions.

When adding a new streaming endpoint or LLM-streaming feature, route through `Router.route_stream` so usage_events get recorded and fallback works. Don't call provider `stream_text` directly from an API handler.

## Application lifecycle (manual)

`discovered_jobs.application_status` is a free-form-ish enum (`bookmarked`, `applied`, `screening`, `interview`, `offer`, `accepted`, `rejected`, `ghosted`, `withdrawn`, `not_applying`). **Every status change is user-initiated** — there is no automation that reads emails, calendar, Slack, or any external signal to infer state. This is deliberate per spec Section 25.6: manual entry gives ground truth for the eval harness and respects job-search nuance.

When adding code that touches lifecycle:

- Status set membership lives in `app/api/lifecycle.py` (`OPEN_STATUSES`, `RESPONDED_STATUSES`, `APPLIED_STATUSES`). A test in `tests/test_lifecycle.py` enforces invariants — read it before changing the buckets.
- `status_history` is **append-only**. Never rewrite past entries.
- `applied_at` is auto-set the first time the user picks an applied-shaped status, but always editable. Don't overwrite a user-set date.
- The dashboard (`/ui/dashboard.html`) is read-only — it never POSTs a status change on the user's behalf.

## Conventions

- **Python 3.12**, FastAPI, SQLAlchemy 2.x, Alembic, LangGraph, LangSmith, pytest.
- **`ruff`** for lint + format. **`mypy --strict`** on `app/` and `evals/`.
- **Type everything.** `TypedDict`s for LangGraph state, Pydantic models at API boundaries.
- **No `print()`** in app code — use the structured logger (`app.observability.log`). Logs are JSON, no raw PII (a test enforces this).
- **Money in EUR**, stored as `NUMERIC(10,6)` in Postgres, `Decimal` in Python.
- **Prompts live in `app/prompts/`** as versioned files, not inline strings. Each file has a `# version: N` header.
- **Async by default** for I/O. Use `asyncio.gather` for fan-out (e.g., parallel provider eval).

## Git workflow (move-fast mode)

Two long-lived branches only: **`main`** and **`dev`**. No feature branches, no PRs.

- **Work directly on `dev`** with small, descriptive commits.
- **`main`** advances by fast-forward merge from `dev` at ship/release time (`git checkout main && git merge --ff-only dev && git push`). Tag releases (`vX.Y`).
- **Never force-push `main` or `dev`.** Never `--no-verify` without explicit user request.
- **Tests must pass before push.** `pytest` is the gate; CI re-runs lint + mypy + tests on every push to `dev`.
- **Prompt changes bump `# version:`** and update [EVAL_REPORT.md](product-requirements/EVAL_REPORT.md) in the same commit.
- **Doc changes** affecting architecture, threat model, or spec interpretation go in the same commit as the code.

If a change is risky (DB destructive op, secret rotation, prod config), open a short-lived branch and ping for review — but the default is direct-to-dev.

## When you write code here

1. **Read the spec section** that covers what you're touching. The spec is the source of truth.
2. **Prefer editing existing files** over creating new ones.
3. **Don't add abstractions speculatively.** Three similar lines beats a premature factory.
4. **No comments explaining WHAT.** Comments are for non-obvious WHY only.
5. **No "Generated with Claude Code" footers** in code or commits.
6. **Co-author trailer is OK** on commits when asked.
7. **Tests for new behavior.** Especially: budget guard, PII redaction, injection classifier, provider fallback, checkpoint resume. These are the spec's acceptance gates.
8. **Run `ruff check`, `mypy`, and `pytest`** before declaring a task done. If you can't, say so explicitly.

## What's IN and OUT of V1

See spec Section 3. Quick reference of common "should we add this?" answers:

| Idea | V1? |
|---|---|
| Vector embeddings for CV/JD | NO — cargo cult here |
| Reflection / learning agent | NO — N=1 |
| LinkedIn/Indeed scraping | NO — ToS, no signal |
| Auto-apply / browser automation | NO |
| Recruiter outreach agent | NO |
| Interview-prep node | NO (stretch) |
| Multi-page dashboard | NO — one page |
| Streamlit | NO — Next.js or plain HTML, pick one |
| K8s | NO — Cloud Run |
| Neo4j / GraphRAG | NO |
| Gemini provider | Stretch (validates abstraction) |
| Browser extension | YES — required for LinkedIn/Indeed JD capture |
| MCP server | YES — differentiator |
| Eval harness in CI | YES — differentiator |
| HITL approval gate | YES |

## LinkedIn / Indeed integration

The user wants JDs sourced from LinkedIn and Indeed. The spec bans scraping. The agreed approach is a **Chrome extension companion** (`extension/`) that:

- Reads the visible JD from the active tab.
- POSTs the text to `/api/applications` with `source: linkedin|indeed` metadata.
- Does **not** automate clicks, applies, or message sends.
- Operates only when the user explicitly triggers it on the page they're already viewing.

This keeps us within ToS while giving the user a one-click path from JD → CareerOS workflow.

## When in doubt

- The spec wins.
- Ask before deleting unfamiliar files.
- Ask before force-pushing, dropping tables, or destructive git ops.
- Honest naming: a service is a service, an agent is an agent.
