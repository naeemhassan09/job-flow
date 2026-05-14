# Architecture

## Geography

CareerOS AI is **Ireland-first** in V1. Defaults across the stack assume the Irish market:

- `default_country: ie` in [`config/profile.yml`](../config/profile.example.yml).
- Scraper queries hit Adzuna IE + Reed (UK/IE coverage).
- Cover-letter prompts include Stamp 1G + Critical Skills Permit context.
- Budgets and salary fields are in EUR.

Country is a single configurable knob (`default_country` + `locations[]`). Code reads country from `UserProfile.default_country` / `SearchLocation.country` — never hardcoded. See spec §25.1.

## System diagram

```text
              ┌──────────────────────────────────────────┐
              │  Clients                                 │
              │  ┌─────────────┐ ┌──────┐ ┌────────────┐ │
              │  │ Next.js UI  │ │ CLI  │ │ Chrome ext │ │
              │  └─────────────┘ └──────┘ └────────────┘ │
              │  ┌──────────────────────────────────┐    │
              │  │ Claude Desktop (MCP client)      │    │
              │  └──────────────────────────────────┘    │
              └────────────────────┬─────────────────────┘
                                   │ HTTPS / MCP
                                   ▼
              ┌──────────────────────────────────────────┐
              │  FastAPI                                 │
              │  - REST (/api/...)                       │
              │  - SSE streaming (/api/.../stream)       │
              │  - MCP server (/mcp/...)                 │
              │  - Prometheus metrics (/metrics)         │
              └────────────────────┬─────────────────────┘
                                   │
                                   ▼
              ┌──────────────────────────────────────────┐
              │  LangGraph workflow                      │
              │   preprocess → profile → research(loop)  │
              │            → matcher → generator         │
              │            → evaluator → [HITL interrupt]│
              │                                          │
              │  Postgres checkpointer (resumable state) │
              └────────────────────┬─────────────────────┘
                                   │
        ┌──────────────────────────┼─────────────────────────┐
        ▼                          ▼                         ▼
  ┌─────────────┐         ┌──────────────────┐      ┌────────────────┐
  │ Postgres    │         │ LLM providers    │      │ LangSmith      │
  │  app data   │         │  OpenAIProvider  │      │  traces / evals│
  │  usage      │         │  AnthropicProvider│     │                │
  │  checkpoints│         │  cost-aware router│     │                │
  └─────────────┘         └──────────────────┘      └────────────────┘
```

## Key decisions

### Why LangGraph (not LangChain agents, not custom)
- First-class **state checkpointer** with Postgres backend → genuine resumability across process restarts.
- **HITL interrupt** primitive matches our approval-gate requirement.
- **Time-travel debugging** via `graph.get_state_history()`.
- LangChain "agents" are a deprecated abstraction; CrewAI / AutoGen overfit to multi-agent narratives we explicitly reject.

### Why one real agentic loop, not many
The spec rejects the "16 agents" framing. The `research` node is a real loop (plan → tool call → observe → replan → stop). Everything else is deterministic. One real loop is honest and demonstrable; 15 fake agents are a credibility cost.

### Why Postgres from day one
SQLite cannot back a LangGraph Postgres checkpointer, and "production with SQLite" is the spec's example of an anti-pattern. Postgres also gives us `JSONB` for parsed JD storage and `NUMERIC` for accurate EUR cost accounting.

### Why a provider abstraction (not direct SDK calls)
- Cost-aware routing (per-task default + fallback) requires a unified interface.
- Failure-injection tests (kill OpenAI mid-workflow, expect Claude completion) require a single seam to swap providers.
- Adding Gemini = one file in `app/llm/providers/`, not a refactor.

### Why MCP server
- 2026 hiring signal. Demonstrates interoperability with Claude Desktop and the broader MCP ecosystem.
- Doubles as a daily-use ergonomics win: invoke `score_fit` from inside Claude Desktop while triaging JDs.
- Server is a thin wrapper over the LangGraph nodes — no business logic duplication.

### Why a Chrome extension (not scraping) for LinkedIn / Indeed
LinkedIn and Indeed ToS forbid automated scraping. The extension only reads the JD text from a page the user is already viewing and POSTs it to our API. No automation of clicks, applies, or messages.

### Why official APIs for proactive discovery (Adzuna, Reed)
Beyond the user clicking on a specific JD, we proactively discover Ireland-relevant roles via the **Adzuna** and **Reed** developer APIs. These are partner programmes with explicit free tiers (Adzuna ~1k calls/month, Reed ~1k/day). Discovered jobs land in `discovered_jobs`, are deduped on `(source, external_id)`, and auto-run through `preprocess + matcher` only (no generator) — so cost stays bounded. Only `fit_score >= 70` rows are promoted to `applications`; the rest stay in the table for review. We never scrape LinkedIn or Indeed directly (ToS).

### Why Cloud Run (not K8s, not Lambda)
- Serverless containers — right level of abstraction for bursty GenAI workloads.
- Scales to zero (cost) and to GBs of memory (large prompts) without K8s ops burden.
- On-trend for 2026 enterprise GenAI deploys.
- ECS task-def kept in `deploy/` as a parity reference for AWS-leaning reviewers.

## What's deliberately NOT in the architecture

- **Vector DB**: structured prompting over a CV + a JD is the right tool here.
- **Message queue**: the workflow is per-request, latency-bounded; SSE handles streaming.
- **Service mesh**: one service.
- **Multi-tenant SSO / RBAC**: single-user app in V1.
- **Feature flags**: not needed at N=1.

## Cross-cutting concerns

| Concern | Mechanism |
|---|---|
| State persistence | LangGraph Postgres checkpointer |
| Cost tracking | `app/llm/budget.py` + `llm_usage_events` table |
| PII | `app/security/pii.py` runs in `preprocess` node |
| Prompt injection | `app/security/injection.py` runs in `preprocess` node |
| Observability | LangSmith traces + JSON logs + `/metrics` |
| Eval | `evals/runners/` invoked by `.github/workflows/eval.yml` |
