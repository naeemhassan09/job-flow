# Roadmap

6-week plan per spec §17, plus post-spec amendments (spec §25).

**Geography**: Ireland-first in V1. The single knob to retarget another country is `default_country` in [`config/profile.yml`](../config/profile.example.yml). See spec §25.1.

## Status (2026-05-14)

| Week | Theme | Status |
|---|---|---|
| 0 | Foundation (repo, docs, skills, scaffold) | ✅ done |
| 1 | Platform primitives (FastAPI, providers, router, budget, PII, injection) | ✅ done |
| 2 | LangGraph workflow + 5 nodes + HITL + Postgres checkpointer | ✅ done |
| 2.5 | Job discovery via Adzuna + Reed official APIs (scope expansion §25.2) | ✅ done |
| 2.6 | Chrome extension MV3 + `/api/captures` (LinkedIn / Indeed companion) | ✅ done |
| 2.7 | Inbox UI + per-job score + human feedback (`/ui/`) | ✅ done |
| 2.8 | Claude-design restyle + always-on Docker container with hot-reload | ✅ done |
| 2.9 | Token tracking middleware + Usage page (`/ui/usage.html`) | ✅ done |
| 2.10 | Session auth + encrypted settings store + login page (spec §25.4) | ✅ done |
| 2.11 | Settings UI page (API keys, model overrides, budgets, change password) | **next** |
| 3 | Agentic research loop + MCP server + SSE streaming + Tavily | pending |
| 4 | Eval harness (50 labeled pairs) + CI regression on PRs | pending |
| 5 | CLI + Cloud Run deploy + LangSmith | pending |
| 6 | Polish: README hook, 90-sec demo video, eval report, blog post | pending |

## What's shipped beyond the original spec

These items came from user direction during build and exist in addition to the spec §17 weekly plan:

- **Chrome extension companion** (originally week 5) — moved earlier so JD capture from LinkedIn/Indeed worked alongside Adzuna/Reed discovery.
- **Job discovery via partner APIs** (Adzuna, Reed) — spec §3.2 originally banned all scraping; user-authorised override in §25.2 covers official-API sources only. LinkedIn/Indeed remain extension-only.
- **Inbox UI** at `/ui/` with per-row scoring + human feedback (thumb/score correction/decision override/notes). Originally just a CLI + minimal page in week 5; expanded into the daily-use surface.
- **Usage page** at `/ui/usage.html` — month-to-date spend, by model, by node, recent calls. Realises the spec §9 observability gap.
- **Session auth + AES-GCM settings store** (spec §25.4) — added because the Settings UI exposes editable API keys. Single-user only; SSO / RBAC / MFA explicitly out of scope.
- **Always-on Docker container** with hot-reload bind mounts of `app/`, `evals/`, `config/`, `data/`. Used in place of repeated `kill && uvicorn`.

## What still needs to ship for V1 to be "complete"

Spec §23 self-check answers:

| Gate | Status |
|---|---|
| README convinces a senior reviewer in 30 seconds this isn't another AI cover-letter generator | partial — Ireland focus + scope discipline + endpoint table help; missing 90-sec video + real eval numbers |
| Real agentic loop with tool use + replanning, readable in the code | **missing — week 3** |
| Eval table with reproducible numbers | **missing — week 4** |
| Failure-injection test proves provider fallback works | ✅ |
| Budget guard blocks over-budget workflows in a test | ✅ |
| 90-second demo video | **missing — week 6** |
| Demo MCP tool calls from Claude Desktop on the spot | **missing — week 3** |
| Cleanly runnable in under 5 minutes from clone | ✅ `docker compose up` |

## Future weeks

See spec §17 + §25. If a week slips, **eval harness and MCP server remain non-negotiable** (spec §17 closing note). Cut UI polish or research-loop sophistication first.
