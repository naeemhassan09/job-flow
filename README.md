# CareerOS AI

**A LangGraph-based agentic workflow platform with first-class cost governance, evaluation, security, and protocol interoperability (MCP).** The reference application is a personal Ireland-tuned job-search workflow: discover roles via official partner APIs, capture from LinkedIn or Indeed with a one-click browser companion, fit-score against your CV, generate a grounded cover letter, and track every application through to offer or rejection — with every LLM call traced, costed, evaluated, and gated by human approval.

## What it is

CareerOS AI demonstrates the architectural patterns enterprise GenAI teams converge on in 2026:

- **Stateful agentic workflow** built on LangGraph with a Postgres checkpointer, conditional routing, and a human-in-the-loop approval gate.
- **Provider abstraction** with cost-aware routing across OpenAI and Anthropic, automatic fallback on error, and per-call cost telemetry.
- **Encrypted runtime settings** so API keys, model selection per task, and budget caps are editable from the UI without redeploys.
- **Per-call observability** — month-to-date spend, cache-hit rate, by-model and by-node breakdowns, recent calls.
- **PII redaction + prompt-injection defense** on every untrusted input before it reaches an LLM.
- **Manual application tracker + dashboard** that records pipeline state from bookmarked through offer, with response-rate, weekly-applications, and stale-follow-up surfaces.
- **Chrome extension companion** that captures JDs from LinkedIn / Indeed via explicit user action — no scraping, no automation, ToS-respecting.
- **Official-API job discovery** via Adzuna and Reed for proactive sourcing.

## Status

Active development on the dev branch; main is the integration branch. The application runs end-to-end locally: capture or paste a JD, fit-score it, draft a cover letter, track the application, and view aggregate stats.

## Key capabilities

| Capability | Surface |
|---|---|
| Inbox of captured + discovered jobs with per-row scoring and human feedback | `/ui/` |
| Pipeline dashboard with response rate, weekly applications, stale follow-ups | `/ui/dashboard.html` |
| Token + cost telemetry — month-to-date spend, by model, by node, recent calls | `/ui/usage.html` |
| Settings panel for API keys, per-task model overrides, budget caps, password | `/ui/settings.html` |
| Chrome extension companion (Manifest V3, scoped to LinkedIn `/jobs/*` and Indeed `/viewjob*`) | `extension/` |
| LangGraph workflow with preprocess, profile, matcher, generator, evaluator nodes | `app/graph/`, `app/nodes/` |
| Encrypted settings store (AES-GCM) with `DB → env → default` precedence | `app/settings_store.py` |
| Session-cookie auth (bcrypt, signed cookies, default-deny middleware) | `app/auth.py`, `app/api/auth.py` |

## Quick start (Docker, recommended)

```bash
# 1. Copy env template
cp .env.example .env

# 2. Create the Postgres database used by the app (host install assumed)
createdb careeros 2>/dev/null || true
.venv/bin/alembic upgrade head

# 3. Build and start the container
docker compose up -d --build app

# 4. Open the app
open http://127.0.0.1:8000/
```

First load redirects to the sign-in page in setup mode: pick a username and a password (8+ chars). Credentials are stored as a bcrypt hash inside the encrypted settings table.

Source folders (`app/`, `evals/`, `config/`, `data/`) are bind-mounted into the container, so code edits trigger an automatic reload. Only `.env` edits require `docker compose restart app`.

### Native Python (without Docker)

```bash
cp .env.example .env
createdb careeros
.venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
cp config/profile.example.yml config/profile.yml
.venv/bin/uvicorn app.main:app --reload --reload-dir app
```

## Geography

CareerOS AI is configured for the Irish job market by default. The single switch to retarget another country is `default_country` in [`config/profile.yml`](config/profile.example.yml). Adzuna supports `ie, gb, us, de, fr, au, ca, nl, pl, in, za, br, mx, nz, sg`; Reed covers `gb` and `ie`.

## Security model

- **Session auth** on the entire UI and API surface, with a small explicit whitelist (`/healthz`, `/metrics`, the Chrome-extension capture endpoint, and the auth API itself).
- **API keys at rest** are encrypted with AES-GCM; the master key is generated automatically on first start if not provided.
- **PII redaction** turns email, phone, address, PPSN, and candidate-name spans into typed placeholders before any LLM sees the text.
- **Prompt-injection defense** wraps untrusted input in tagged delimiters and runs a regex pre-filter with a 15-attack regression set, plus an LLM-as-judge layer (planned).
- **Cost governance** — hard monthly cap and per-workflow soft cap consulted before every LLM call.

## Non-goals

- No direct scraping of LinkedIn, Indeed, or any ToS-restricted site.
- No autonomous outbound messaging or auto-apply.
- No fabricated content — every cover-letter claim is grounded against the candidate profile.
- No multi-user, SSO, RBAC, or MFA — single-user local app.

## License

All rights reserved.

## Author

Built by Naeem ul Hassan — AI Platform Engineer, Dublin · MSc Artificial Intelligence (Dublin Business School) · LinkedIn: [in/naeemhassan09](https://www.linkedin.com/in/naeemhassan09/).

See [CLAUDE.md](CLAUDE.md) for working notes and conventions, and the [product-requirements/](product-requirements/) directory for the architecture overview, threat model, and roadmap.
