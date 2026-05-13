# CareerOS AI — Agentic Workflow Platform

CareerOS AI is a production-grade LangGraph platform for stateful, evaluated, cost-governed agentic workflows. It demonstrates the architectural patterns modern enterprise GenAI teams are converging on: provider abstraction, genuine agentic loops with tool use, prompt-injection defense, per-step cost governance, MCP interoperability, and a CI-integrated evaluation harness with published benchmarks.

The reference application is a job-search workflow: paste (or capture via the Chrome extension) a JD, get a calibrated fit score, an auto-researched company brief, and a draft cover letter — with every LLM call traced, costed, evaluated, and gated by human approval.

- → [90-second demo video](#) — coming with v1 ship
- → [Architecture](product-requirements/ARCHITECTURE.md)
- → [Latest eval results](product-requirements/EVAL_REPORT.md) — OpenAI vs Claude across 6 tasks
- → [Threat model](product-requirements/THREAT_MODEL.md)
- → [Roadmap](product-requirements/ROADMAP.md)

## Status

V0 — foundation scaffold. See [ROADMAP.md](product-requirements/ROADMAP.md) for what ships in each weekly PR.

## Quick start (after Week 1 lands)

```bash
cp .env.example .env   # add OPENAI_API_KEY, ANTHROPIC_API_KEY, LANGSMITH_API_KEY
docker compose up -d
uv sync
uvicorn app.main:app --reload
```

## Repo layout

See [CLAUDE.md](CLAUDE.md) for the working-notes layout, conventions, and contribution rules.

## Non-goals

No scraping. No autonomous outbound messaging. No fabrication. No SQLite in prod paths. See [spec §3.3](product-requirements/CareerOS_AI_Product_Spec_v2.md).
