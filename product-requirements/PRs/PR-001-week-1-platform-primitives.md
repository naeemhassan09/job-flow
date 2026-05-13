# PR-001 — Week 1: Platform Primitives

**Branch**: `feat/week-1-platform-primitives` → `dev`
**Status**: ready for review (no remote yet — see "How to push" below)

## Summary

Builds the reusable LLM-platform layer that the LangGraph workflow (Week 2) will sit on. This is the spec §17 Week 1 checkpoint — these primitives alone form a small standalone LLM-platform library.

- Provider abstraction (OpenAI + Anthropic) behind a single `LLMProvider` Protocol
- Cost-aware router with §7.2 task→model table and automatic fallback on error
- `BudgetGuard` with monthly + per-workflow caps, raises `BudgetExceeded`
- USD→EUR cost calculator with Anthropic cached-token pricing
- PII redactor (email, phone, address, PPSN, doc number, candidate name)
- Injection regex pre-filter with 15-attack regression set
- Structured JSON logger with defensive PII scrub processor
- SQLAlchemy 2.x async models per §13
- FastAPI app with `/healthz` (DB ping) and `/metrics` (Prometheus)
- CI: ruff lint+format, mypy --strict, pytest + coverage, scope-guard for `legacy/` imports

## Test plan

- [x] `pytest tests/test_pii_redaction.py` — email/phone/PPSN/name/address all flagged
- [x] `pytest tests/test_injection_classifier.py` — 15 attacks caught, 4 benign clean
- [x] `pytest tests/test_logs_no_pii.py` — scrub walks dict/list
- [x] `pytest tests/test_cost_calculator.py` — cached < fresh, unknown model → 0
- [x] `pytest tests/test_provider_fallback.py` — fallback fires on default-provider error
- [x] `pytest tests/test_budget_guard.py` — both caps enforced, precheck and post-record
- [x] Local smoke run (no deps): all five pure-Python modules pass

## Acceptance checks (spec §17 W1)

- [x] FastAPI skeleton with `/healthz` (returns DB status) and `/metrics`
- [x] Postgres + docker-compose
- [x] SQLAlchemy models for `users`, `applications`, `llm_usage_events`, `budget_limits`
- [x] Provider abstraction (`OpenAIProvider`, `AnthropicProvider`)
- [x] Cost-aware router with per-task defaults + fallback
- [x] Token + EUR cost calculator
- [x] `BudgetGuard` with monthly + per-workflow caps
- [x] PII redactor + injection classifier
- [x] Tests: `test_pii_redaction`, `test_injection_classifier`, `test_budget_guard`, `test_provider_fallback`
- [x] `.github/workflows/ci.yml`

## Out of scope (intentional)

- LangGraph workflow + Postgres checkpointer — Week 2
- MCP server, agentic research loop, SSE streaming — Week 3
- Alembic migration files — generated alongside the Week 2 workflow PR via `alembic revision --autogenerate`
- LangSmith wiring — Week 5
- UI / extension — Week 5

## Risk / follow-ups

- The injection classifier is regex-only. An LLM judge wrapper lands in Week 3 with the `preprocess` node — the regex layer is the fast, deterministic CI gate.
- `Router.route` swallows exception types broadly; we should narrow to `(httpx.HTTPError, openai.APIError, anthropic.APIError)` once those are imported in providers (follow-up issue).
- No retry/backoff yet at the router layer — by design for Week 1 to keep the seam clean; Tenacity wrapper lands with Week 2.

## How to push (when a GitHub remote exists)

```bash
# Create the GitHub repo and push both branches
gh repo create careeros-ai --private --source=. --remote=origin
git push -u origin main
git push -u origin dev
git push -u origin feat/week-1-platform-primitives

# Open the PR
gh pr create --base dev --head feat/week-1-platform-primitives \
  --title "feat(week-1): platform primitives — providers, router, budget, PII, injection" \
  --body-file product-requirements/PRs/PR-001-week-1-platform-primitives.md
```

Until then, review locally:

```bash
git log --oneline dev..feat/week-1-platform-primitives
git diff dev...feat/week-1-platform-primitives
```
