# CareerOS AI — Agentic Workflow Platform

CareerOS AI is a production-grade LangGraph platform for stateful, evaluated, cost-governed agentic workflows. It demonstrates the architectural patterns modern enterprise GenAI teams are converging on: provider abstraction, genuine agentic loops with tool use, prompt-injection defense, per-step cost governance, MCP interoperability, and a CI-integrated evaluation harness with published benchmarks.

The reference application is a job-search workflow tuned for the **Irish market**: discover roles via the Adzuna and Reed APIs, paste (or capture via the Chrome extension) a JD, get a calibrated fit score, an auto-researched company brief, and a draft cover letter — with every LLM call traced, costed, evaluated, and gated by human approval.

- → [Architecture](product-requirements/ARCHITECTURE.md)
- → [Latest eval results](product-requirements/EVAL_REPORT.md) — OpenAI vs Claude across 6 tasks
- → [Threat model](product-requirements/THREAT_MODEL.md)
- → [Roadmap](product-requirements/ROADMAP.md)
- → 90-second demo video — coming with v1 ship

## Geography — Ireland focus

The current reference deployment targets **jobs in Ireland (`ie`)**. Both job-discovery sources (Adzuna IE + Reed IE/UK) are configured for the Dublin market by default.

**To target a different country**, change one knob — `default_country` in [`config/profile.yml`](config/profile.example.yml) — and update the `locations[]` entries. Supported Adzuna countries: `ie, gb, us, de, fr, au, ca, nl, pl, in, za, br, mx, nz, sg`. Reed only covers `gb + ie`; if you switch to another country, disable Reed via `sources.reed.enabled: false` (or leave it on — it'll just return zero results).

LinkedIn and Indeed are **never** scraped, regardless of country. They flow in through the Chrome extension companion (Week 5) when you click "Send to CareerOS" on a JD page you're viewing.

## Status

Active development — week 2 + scope-expanded job discovery shipped. See [ROADMAP.md](product-requirements/ROADMAP.md) for what's next.

## Quick start

### Recommended: Docker (stays running, hot-reload on file changes)

```bash
# 1. Copy env, fill in OPENAI_API_KEY at minimum.
cp .env.example .env

# 2. Make sure your local Postgres has a `careeros` database with the migrations
#    applied. The container talks to your host Postgres via host.docker.internal
#    so the data persists across container restarts.
createdb careeros 2>/dev/null || true
.venv/bin/alembic upgrade head

# 3. Build and start the app container.
docker compose up -d --build app

# Logs / common ops
docker compose logs -f app          # tail logs
docker compose restart app          # only needed if .env changed
docker compose down                 # stop
docker compose up -d                # start again

# Open the inbox
open http://127.0.0.1:8000/ui/
```

Source folders (`app/`, `evals/`, `config/`, `data/`) are bind-mounted into the
container, so any code edit triggers `uvicorn --reload` inside the container —
you don't restart manually. The only changes that need a container restart are
`.env` edits (`docker compose restart app`).

### Native Python (without Docker)

```bash
cp .env.example .env
createdb careeros
.venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
cp config/profile.example.yml config/profile.yml
.venv/bin/uvicorn app.main:app --reload --reload-dir app
```

API surface:

| Endpoint | What it does |
|---|---|
| `GET  /healthz` | Liveness + DB ping |
| `GET  /metrics` | Prometheus-compatible metrics |
| `POST /api/applications` | Paste a JD; run the workflow up to the HITL approval gate |
| `POST /api/applications/{id}/approve` | Resume past the HITL gate (runs the evaluator) |
| `POST /api/applications/{id}/reject` | Cancel the run |
| `GET  /api/applications/{id}` | Full state snapshot incl. `next_nodes` |
| `POST /api/discover` | Fan-out to Adzuna + Reed, dedupe, auto-score, promote `fit_score ≥ 70` to applications |
| `GET  /api/jobs` | Browse the discovered-jobs inbox (filter by `status`, `source`) |
| `GET  /api/jobs/{id}` | Full discovered-job row incl. raw payload |
| `POST /api/jobs/{id}/score` | Score-only workflow (preprocess + matcher) against a single discovered_jobs row |
| `POST /api/jobs/{id}/feedback` | Persist human feedback (thumb, score correction, decision override, notes) |
| `POST /api/jobs/{id}/status` | Update application lifecycle status (manual; appends to status_history) |
| `GET  /api/stats/dashboard` | Pipeline counts, response rate, avg fit applied, weekly applications, stale follow-ups |
| `POST /api/captures` | Chrome-extension capture endpoint (bearer-token auth, not session) |
| `GET  /api/usage/{monthly,by-model,by-node,recent}` | Token + cost telemetry |
| `POST /api/auth/{init,login,logout,change-password}` | Session auth (first run uses `/init`, then `/login`) |
| `GET  /api/auth/{status,me}` | Auth introspection |
| `GET  /api/settings` | All editable settings, secrets masked, session-protected |
| `PUT  /api/settings/{key}` | Upsert a setting (empty value deletes → revert to .env) |
| `POST /api/settings/test/{provider}` | Ping `openai` / `anthropic` / `tavily` / `adzuna` / `reed` with currently-configured creds |
| `GET  /ui/` | Inbox UI (session-cookie protected) |
| `GET  /ui/usage.html` | Usage dashboard (session-cookie protected) |
| `GET  /ui/settings.html` | Settings page — API keys, model overrides, budgets, change password |
| `GET  /ui/dashboard.html` | Application pipeline dashboard — counts by status, response rate, weekly applications, stale follow-ups |
| `GET  /ui/login.html` | Sign-in / first-run setup |
| `GET  /docs` | OpenAPI / Swagger UI |

## Get the discovery API keys (free, 5 min each)

- **Adzuna**: https://developer.adzuna.com/signup → register an app → copy `Application ID` + `Application Key` into `.env` as `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- **Reed**: https://www.reed.co.uk/developers → request a free Jobseeker API key → copy into `REED_API_KEY`.

If either is missing, that scraper is silently skipped — you can run the system with only one configured.

## Tests

```bash
.venv/bin/python -m pytest -q
```

63 tests covering: PII redaction, prompt-injection defence, cost calculator, provider fallback, budget guard, prompt loader, profile loader, LangGraph workflow assembly + HITL pause/resume, scraper query building, scraper red-flag filter, and mocked Adzuna + Reed HTTP parsing.

## Repo layout

See [CLAUDE.md](CLAUDE.md) for working notes, conventions, and contribution rules.

## Auth

Single-user local auth with a session cookie:

1. First run, open http://127.0.0.1:8000/ — you'll be redirected to the login page in **first-run setup** mode. Pick a username (`admin` is fine) and a password ≥ 8 chars. The credentials are stored as a bcrypt hash inside the encrypted `app_settings` table.
2. From then on, the same login form authenticates you. Cookie lasts 7 days.
3. **Two endpoints bypass the session cookie on purpose:**
   - `GET /healthz` and `GET /metrics` — open, for monitoring
   - `POST /api/captures` — bearer-token auth (`EXTENSION_API_TOKEN`) so the Chrome extension works without browser cookies
4. To change password: log in, then `POST /api/auth/change-password` (will be wired into the settings page next).

All API keys (OpenAI, Anthropic, Tavily, Adzuna, Reed, Chrome extension bearer, LangSmith), per-task model overrides, and budget caps are editable from `/ui/settings.html`. Values are AES-GCM encrypted at rest with `PII_ENCRYPTION_KEY` (auto-generated on first run if not set). Read precedence at runtime: **DB value if set → env var → hardcoded default**, so a UI edit takes effect immediately without restarting the app.

### Quick test — does my OpenAI key work?

On the Settings page → API keys section → click **Test** next to any provider. The backend hits the provider's own auth endpoint (e.g. `GET /v1/models` for OpenAI) with whichever value is currently effective (DB override > .env) and surfaces `connected` / `failed (HTTP 401)` inline.

## Non-goals

No direct scraping of LinkedIn / Indeed / any ToS-restricted site. No autonomous outbound messaging. No fabrication (every cover-letter claim is grounded against your CV). No SQLite in prod paths. See [spec §3.3](product-requirements/CareerOS_AI_Product_Spec_v2.md).
