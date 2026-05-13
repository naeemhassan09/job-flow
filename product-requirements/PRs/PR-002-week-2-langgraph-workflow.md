# PR-002 — Week 2: LangGraph Workflow + HITL + Postgres Checkpointer

**Branch**: `feat/week-2-langgraph-workflow` → `dev`
**Depends on**: PR-001 (merge first; this branch is currently stacked on top of `feat/week-1-platform-primitives`).
**Status**: 56/56 tests pass locally

## Summary

Stateful agentic workflow on top of the week-1 platform primitives. Paste a JD → workflow runs preprocess → profile → matcher → (generator | end), pauses at HITL approval gate before the evaluator finalises. Postgres checkpointer persists state at every node; MemorySaver in tests.

## What's in

- LangGraph `StateGraph` with 5 functional nodes + conditional routing per spec §5.3
- `interrupt_before=["evaluator"]` HITL gate; resume via `POST /approve`
- AsyncPostgresSaver wired (MemorySaver in `APP_ENV=test`)
- Alembic baseline migration for the six application tables (§13)
- 5 versioned prompts under `app/prompts/`, loaded by `app.llm.prompts`
- User-profile config (`config/profile.example.yml`) + loader (`app/profile.py`)
- API: `POST /api/applications`, `POST /{id}/approve`, `POST /{id}/reject`, `GET /{id}`
- Tests covering apply path, skip path, injection quarantine path

## Test plan

- [x] `pytest tests/test_workflow_assembly.py` — compiles, expected nodes, HITL configured
- [x] `pytest tests/test_workflow_hitl.py` — apply pauses + resumes, skip bypasses HITL, injection halts
- [x] `pytest tests/test_prompt_loader.py` — all 5 prompts load with correct task
- [x] `pytest tests/test_profile_loader.py` — example loads, CV path resolves
- [x] All 6 week-1 test suites still pass (56 total)
- [ ] (post-merge) `alembic upgrade head` against a fresh Postgres confirms schema applies cleanly

## Acceptance checks (spec §17 W2)

- [x] LangGraph workflow with the 5 functional nodes
- [x] Postgres checkpointer
- [x] HITL approval interrupt + resume
- [x] Structured logging (week-1 logger inherited; nodes flow JSON metadata)

## Out of scope (intentional)

- Agentic research loop (web_search + fetch_url tools) — Week 3
- MCP server exposing nodes as tools — Week 3
- SSE streaming endpoint for cover-letter generation — Week 3
- LLM-as-judge wrapper around the regex injection classifier — Week 3
- Persisting per-call `llm_usage_events` rows from the nodes — follow-up in Week 3 with the agentic loop
- LangSmith trace wiring — Week 5

## Risk / follow-ups

- `llm_usage_events` rows are not yet inserted from node calls. The `BudgetGuard` from PR-001 can read the table, but nothing is writing to it. Follow-up issue: wrap router calls with a `usage_recorder` middleware in Week 3.
- The evaluator's quality-gate decision is computed but does not yet route back to a re-generation step. By design — re-generate would be a second loop and the spec wants one real loop for V1.
- Address regex was widened to accept single-letter words (e.g. "O Connell"). Trade-off: slightly higher false-positive risk on text like "5 A Street". Tracked but acceptable for V1.

## How to open the PR

```
https://github.com/naeemhassan09/job-flow/pull/new/feat/week-2-langgraph-workflow
```

Base = `dev`. Use this file as the body.
