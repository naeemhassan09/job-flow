# Roadmap

Engineering plan tracked from spec Section 17, plus post-spec amendments (spec Section 25). Updated on every shipped change.

**Geography**: Ireland-first in V1. The single switch to retarget another country is `default_country` in [`config/profile.yml`](../config/profile.example.yml). See spec Section 25.1.

## Status (2026-05-14)

| Phase | Theme | Status |
|---|---|---|
| 0 | Foundation (repo, docs, skills, scaffold) | ✅ done |
| 1 | Platform primitives — FastAPI, providers, router, budget guard, PII redaction, prompt-injection scanner | ✅ done |
| 2 | LangGraph workflow — 5 nodes + HITL + Postgres checkpointer | ✅ done |
| 2.5 | Job discovery via Adzuna + Reed official APIs (Section 25.2) | ✅ done |
| 2.6 | Chrome extension MV3 + `/api/captures` (LinkedIn / Indeed companion) | ✅ done |
| 2.7 | Inbox UI + per-job score + human feedback | ✅ done |
| 2.8 | Claude-design restyle + always-on Docker container with hot-reload | ✅ done |
| 2.9 | Token tracking middleware + Usage page (Section 9) | ✅ done |
| 2.10 | Session auth + encrypted settings store (Section 25.4) | ✅ done |
| 2.11 | Settings UI — API keys, model overrides, budgets, change password (Section 25.5) | ✅ done |
| 2.12 | Application lifecycle tracker + Dashboard (Section 25.6) | ✅ done |
| 2.13 | Inline streaming cover-letter generation + edit + approve (Section 25.7) | ✅ done |
| 3a | Agentic research loop with Tavily web_search + fetch_url tools (Section 25.8) | ✅ done |
| 3b | MCP server exposing the workflow as tools to Claude Desktop (Section 25.9) | ✅ done |
| 4 | Eval harness — 50 labeled JD/CV pairs + CI regression on PRs | **next** |
| 5 | Cloud Run deploy + LangSmith trace wiring + GitHub Actions release workflow | pending |
| 6 | Polish — README hook video, eval report write-up, blog post | pending |

## Phase 4 — Eval harness (next up)

Spec Section 11 deliverable, and the single largest remaining portfolio differentiator per spec Section 23 ("eval table with reproducible numbers").

Plan:

1. Build a labeled dataset under `evals/dataset/`:
   - 25 real Ireland-relevant JDs harvested from the inbox (captures + Adzuna/Reed).
   - 25 synthetic JDs covering edge cases (mis-titled, injection attempts, ghost-recruiter postings, distant-fit roles).
   - Each pair labelled with: expected `decision` (apply/maybe/skip), expected required skills, expected fit-score band.
   - Use the accumulating `human_feedback` rows from the inbox as ground truth for fit-score corrections.
2. Runners under `evals/runners/`:
   - JD parsing F1 vs labelled skills.
   - Fit-score mean absolute error vs labelled bands.
   - Decision accuracy on apply/maybe/skip.
   - Cover-letter factuality (LLM-as-judge against the CV).
   - Cover-letter ATS keyword coverage (rules-based, no LLM).
   - Research-brief groundedness (LLM-as-judge against the trace's sources).
3. Comparison output: run each metric against `gpt-4.1-mini` and `claude-haiku-4-5` in parallel; emit a markdown table.
4. CI integration via `.github/workflows/eval.yml`: posts a comparison comment on every PR that touches `app/prompts/`, `app/nodes/`, `app/llm/`, `app/research/`, or `evals/`. Fails the PR on >5% regression vs `main`.
5. Publish results to [EVAL_REPORT.md](EVAL_REPORT.md) (today all rows say `pending` — that's accurate, the harness hasn't run yet).

## Phase 5 — Cloud Run + LangSmith

- LangSmith trace wiring: every LangGraph run + every MCP tool call shows up in a LangSmith project, reviewers can click into traces.
- GitHub Actions: lint + mypy + pytest on every push; deploy to Cloud Run on every tag.
- Public Cloud Run URL backed by a demo dataset (no real PII).

## Phase 6 — Polish

- README "30-second hook" video (90 seconds total) walking through capture → score → research → generate → MCP.
- Architecture diagram cleaned up (mermaid in repo, PNG in README).
- Blog post: "Why LangGraph checkpointing for resumable agentic workflows on a €15/month budget."
- Threat model: complete the high-entropy-string pre-commit hook (currently a TODO in [THREAT_MODEL.md](THREAT_MODEL.md)).

## Spec Section 23 self-check

| Gate | Status |
|---|---|
| README convinces a senior reviewer in 30 seconds this isn't another AI cover-letter generator | ✅ — leads with platform language, links to architecture, threat model, MCP guide |
| Real agentic loop with tool use + replanning, readable in the code | ✅ — `app/research/agent.py` with `web_search` + `fetch_url`, MAX_ITERATIONS=6, dedupe sets, append-only trace |
| Eval table with reproducible numbers | **pending — Phase 4** |
| Failure-injection test proves provider fallback works | ✅ — `tests/test_provider_fallback.py` |
| Budget guard blocks over-budget workflows in a test | ✅ — `tests/test_budget_guard.py` |
| 90-second demo video | **pending — Phase 6** |
| Demo MCP tool calls from Claude Desktop on the spot | ✅ — five tools, structured-JSON returns, [wiring guide](mcp-server.md) |
| Cleanly runnable in under 5 minutes from clone | ✅ — `docker compose up -d` |

## What's shipped beyond the original spec

Items the user explicitly authorised during build:

- **Chrome extension companion** for LinkedIn / Indeed JD capture (originally Phase 5, moved earlier).
- **Job discovery via partner APIs** (Adzuna, Reed) — spec Section 3.2 originally banned all scraping; Section 25.2 narrows that to "official partner APIs are in, LinkedIn/Indeed scraping is still out".
- **Inbox UI** with per-row scoring + human feedback, application lifecycle tracker, dashboard, inline streaming cover-letter generation, and the agentic research panel (originally just a minimal page in Phase 5).
- **Usage page** at `/ui/usage.html` realising spec Section 9 observability.
- **Session auth + AES-GCM settings store** (spec Section 25.4-25.5) — added because the Settings UI exposes editable API keys.
- **Always-on Docker container** with hot-reload bind mounts of `app/`, `evals/`, `config/`, `data/`.
