# Roadmap

6-week plan per spec §17. Updated at the end of each week.

## Status

| Week | Theme | Status |
|---|---|---|
| 0 | Foundation | done |
| 1 | Platform primitives (FastAPI, providers, budget, PII, injection) | done |
| 2 | LangGraph workflow + HITL + checkpointer | done |
| 2.5 | Job discovery via Adzuna + Reed APIs (scope expansion) | done |
| 3 | Agentic research loop + MCP server + SSE | next |
| 4 | Eval harness (50 pairs) + CI integration | pending |
| 5 | UI + CLI + Cloud Run deploy + LangSmith + Chrome extension | pending |
| 6 | Polish: README, threat model, eval report, demo video | pending |

## Week 0 — Foundation (current)

- [x] Archive legacy `jobflow/` Python project
- [x] git init with `main` + `dev` branches
- [x] `CLAUDE.md`
- [x] `product-requirements/` with spec, architecture, threat model, eval report shell, this roadmap
- [x] `.claude/skills/` with project-specific skills
- [ ] Repo scaffold (`app/`, `evals/`, `frontend/`, `extension/`, `tests/`, `deploy/`)
- [ ] First PR merged to `dev`

## Week 1 — Platform primitives

Deliverables:
- FastAPI skeleton with `/healthz` and Prometheus `/metrics`.
- Postgres + docker-compose.
- SQLAlchemy models for `users`, `applications`, `llm_usage_events`, `budget_limits`.
- Alembic baseline migration.
- `app/llm/` provider abstraction (`OpenAIProvider`, `AnthropicProvider`).
- Cost-aware router with per-task defaults + fallback.
- Token + EUR cost calculator.
- `BudgetGuard` with monthly cap + per-workflow soft cap.
- `app/security/pii.py` (regex-based redactor) + `app/security/injection.py` (classifier prompt).
- Tests: `test_pii_redaction`, `test_injection_classifier`, `test_budget_guard`, `test_provider_fallback`.
- `ruff` + `mypy --strict` + `pytest` wired into `.github/workflows/ci.yml`.

Acceptance:
- `docker compose up && curl :8000/healthz` returns 200.
- All four tests pass.
- A budget-exceeded provider call raises `BudgetExceeded`.
- Provider failure-injection swaps to fallback successfully.

Non-goals this week: LangGraph, MCP, UI, eval dataset.

## Future weeks

See spec §17. If a week slips, **eval harness and MCP server are non-negotiable** (spec §17 closing note). Cut UI polish or research-loop sophistication first.
