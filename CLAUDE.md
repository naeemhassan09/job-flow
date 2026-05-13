# CareerOS AI — Working Notes for Claude

This file briefs you when you join this repo. Read it before doing work.

## What this is

CareerOS AI is a **LangGraph-based agentic workflow platform**. The job-search use case is the reference application that demonstrates the platform end-to-end. Treat the platform as the product; the JD-scoring/cover-letter flow is the demo.

Full spec: [product-requirements/CareerOS_AI_Product_Spec_v2.md](product-requirements/CareerOS_AI_Product_Spec_v2.md). When the spec and this file disagree, the spec wins — fix this file.

## Non-negotiables (from the spec)

1. **No autonomous outbound messaging.** No email, no DMs, no auto-apply.
2. **No scraping of LinkedIn/Indeed/job boards.** JDs come via paste, official APIs, or the browser-extension companion.
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

## Conventions

- **Python 3.12**, FastAPI, SQLAlchemy 2.x, Alembic, LangGraph, LangSmith, pytest.
- **`ruff`** for lint + format. **`mypy --strict`** on `app/` and `evals/`.
- **Type everything.** `TypedDict`s for LangGraph state, Pydantic models at API boundaries.
- **No `print()`** in app code — use the structured logger (`app.observability.log`). Logs are JSON, no raw PII (a test enforces this).
- **Money in EUR**, stored as `NUMERIC(10,6)` in Postgres, `Decimal` in Python.
- **Prompts live in `app/prompts/`** as versioned files, not inline strings. Each file has a `# version: N` header.
- **Async by default** for I/O. Use `asyncio.gather` for fan-out (e.g., parallel provider eval).

## Git workflow

- **`main`** is protected. Only release-tagged merges from `dev`.
- **`dev`** is the integration branch. Feature branches merge here via PR.
- **Branch names**: `feat/<short-slug>`, `fix/<slug>`, `chore/<slug>`, `eval/<slug>`.
- **PRs target `dev`**. Squash-merge. PR title is the eventual commit subject.
- **Every PR must**: pass CI (lint, mypy, tests, eval regression), update affected docs in `product-requirements/`, and bump prompt versions if prompts changed.
- **Never force-push `main` or `dev`.** Never `--no-verify` without explicit user request.

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

See spec §3. Quick reference of common "should we add this?" answers:

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
