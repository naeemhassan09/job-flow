# CareerOS AI — Agentic Workflow Platform (v2 Spec)

> **Reframed, scope-cut, and 2026-aligned.**
> A production-grade agentic workflow platform demonstrated on a job-search use case.
> Designed to be (a) a hireable portfolio artifact for senior AI Platform / Architect / MLOps / Agentic AI roles, and (b) a tool the author personally uses to accelerate his own Ireland-based job search.

---

## 1. Product Name & Positioning

**CareerOS AI** — *A LangGraph-based agentic workflow platform with first-class cost governance, evaluation, security, and protocol interoperability (MCP).*

The job-search workflow is the **reference application** that proves the platform end-to-end. The README, architecture diagram, and resume positioning all foreground the platform; the job-search use case is the demo.

This positioning matters because:
- Job-search AI is the most over-saturated portfolio category in 2026.
- The same architecture (stateful agentic workflows, provider abstraction, cost governance, eval) is what enterprise teams are actually building for compliance review, RFP response, contract analysis, and internal copilots.
- Reviewers should pattern-match this to *enterprise platform engineering*, not *another cover-letter generator*.

---

## 2. Dual Goals

### 2.1 Portfolio goal (primary)
Demonstrate the architectural patterns senior AI Platform / Agentic AI hiring managers screen for in 2026:
- Stateful agentic workflows with LangGraph (checkpointing, resumability, HITL)
- A genuine agentic loop (tool use, replanning) — not just a deterministic pipeline
- Multi-provider LLM abstraction (OpenAI + Claude) with cost-aware routing
- Production observability (LangSmith + structured logs)
- Cost governance (per-step token + cost tracking, budget guards, prompt caching)
- Security (PII redaction, prompt-injection treatment of untrusted inputs)
- Evaluation harness with a labeled dataset and CI regression
- MCP server exposing platform capabilities as tools
- Cloud-deployed (Cloud Run for GCP exposure; ECS-compatible for AWS)

### 2.2 Personal-use goal (the system must actually be useful)
The author will use CareerOS AI daily during his job search. So the system must:
- Reliably parse pasted JDs into structured fields
- Score JD-vs-CV fit with a calibrated, evidence-grounded number
- Generate Ireland-tuned cover letters and tailored CV bullets
- Auto-research the target company (via the agentic loop) before he applies
- Persist everything in a tracker so he can audit what he applied to and when
- Be cheap to run (under €15/month at his expected volume)
- Be available as MCP tools so he can invoke it from Claude Desktop

If a feature doesn't serve **both** goals, it's cut.

---

## 3. What's IN and what's OUT (compared to v1 spec)

### 3.1 IN
- LangGraph workflow with 5 functional nodes + 1 agentic research loop
- Postgres checkpointer for state persistence
- Human-in-the-loop approval gate before any artifact is finalized
- OpenAI + Claude provider abstraction with cost-aware router
- Token/cost tracking at workflow + step granularity, with hard budget cap
- Anthropic prompt caching with measured savings reported in dashboard
- PII redaction and prompt-injection classifier for untrusted JD inputs
- Eval harness: 50 labeled JD/CV pairs, regression suite in CI, published benchmark
- MCP server exposing `analyze_jd`, `score_fit`, `generate_cover_letter`, `research_company`
- Streaming endpoint for cover-letter generation
- Cloud Run deployment + Dockerfile + GitHub Actions CI
- Single-page web UI (minimal) + CLI

### 3.2 OUT (cut from v1)
| Cut | Reason |
|---|---|
| Reflection / learning agent | N=1 user, no statistical signal — pure aspiration, hurts credibility |
| Vector embeddings for CV/JD match | Embedding retrieval over two documents is cargo-culted RAG |
| Recruiter outreach agent | Adds LLM calls without architectural novelty; "AI wrapper" smell |
| Interview-prep agent | Same — out of V1, optional V2 |
| 16-agent framing | Conflates services with agents; reviewers count nodes |
| Multi-page Streamlit dashboard | Half-built UI hurts more than no UI |
| Four separate observability dashboards | One is enough; LangSmith covers most |
| "Tracker Agent" / "Token Governance Agent" | These are services/middleware, not agents |
| LinkedIn scraping, browser automation, auto-apply | Risk without engineering signal |

### 3.3 Explicit non-goals
- No autonomous email/message sending
- No CAPTCHA bypass, no scraping of job boards
- No fabrication: every CV bullet must be evidence-backed
- No K8s in V1 (Cloud Run is sufficient and on-trend for serverless GenAI)
- No Neo4j / GraphRAG (would be cargo-culting for this use case)

---

## 4. High-Level Architecture

```text
                ┌────────────────────────────┐
                │    Web UI (Next.js)        │
                │    CLI                     │
                │    MCP Client (Claude)     │
                └────────────┬───────────────┘
                             │ HTTP / MCP
                             ▼
            ┌──────────────────────────────────┐
            │      FastAPI                     │
            │  - REST endpoints                │
            │  - MCP server                    │
            │  - Streaming SSE for generation  │
            └────────────┬─────────────────────┘
                         │
                         ▼
            ┌──────────────────────────────────┐
            │    LangGraph Workflow            │
            │  ┌────────────────────────────┐  │
            │  │ Preprocess (security+JD)   │  │
            │  │   ↓                        │  │
            │  │ Profile (CV compress)      │  │
            │  │   ↓                        │  │
            │  │ Research Loop (agentic) ◄──┼──┐ tool calls
            │  │   ↓                        │  │
            │  │ Matcher (fit + decision)   │  │
            │  │   ↓                        │  │
            │  │ Generator (cover + bullets)│  │
            │  │   ↓                        │  │
            │  │ Evaluator + HITL gate      │  │
            │  └────────────────────────────┘  │
            └────────────┬─────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐     ┌──────────┐     ┌──────────┐
   │Postgres │     │ LLM      │     │LangSmith │
   │ - app   │     │ Providers│     │  traces  │
   │ - usage │     │ OpenAI   │     │          │
   │ - chkpt │     │ Claude   │     │          │
   └─────────┘     └──────────┘     └──────────┘
```

---

## 5. LangGraph Workflow Design

### 5.1 Nodes (5 functional + 1 loop)

| Node | Type | Responsibility |
|---|---|---|
| `preprocess` | Functional | PII redaction, prompt-injection scan, JD structured extraction |
| `profile` | Functional | One-time CV compression into reusable structured profile |
| `research` | **Agentic loop** | Iteratively researches target company using web_search + fetch_url tools, decides when to stop |
| `matcher` | Functional | Scores JD-vs-CV fit, produces decision (apply / maybe / skip) |
| `generator` | Functional | Generates tailored CV bullets + cover letter (conditional on `apply`) |
| `evaluator` | Functional | Quality gates: factuality check, ATS keyword coverage, length, tone |

A human-approval **interrupt** sits between `evaluator` and final artifact persistence. Approval can come from the web UI or via MCP tool.

### 5.2 Why this is genuinely agentic (not a DAG)

The `research` node is a real agentic loop:

```python
# Pseudo-flow
state.notes = []
while True:
    plan = llm.decide_next_action(state.role, state.company, state.notes)
    if plan.action == "stop":
        break
    if plan.action == "search":
        results = tool.web_search(plan.query)
        state.notes.append(results)
    elif plan.action == "fetch":
        page = tool.fetch_url(plan.url)
        state.notes.append(page)
    if len(state.notes) > MAX_ITERATIONS:
        break
state.company_brief = llm.summarize(state.notes)
```

This is the difference between "stateful pipeline" and "agentic system." One real loop is worth more than 15 fake "agents."

### 5.3 Routing logic

```text
matcher.fit_score:
  >= 70 → generator  (apply path)
  50–69 → gap_summary only (skip generator)
  < 50  → archive with reason
```

No 7-way decision matrix. One threshold band. Simpler is more honest.

### 5.4 Persistence & resumability

- LangGraph **Postgres checkpointer** saves state at each node.
- Workflows can be paused at the HITL gate and resumed later (this is the key resumability demo).
- Time-travel debugging via `graph.get_state_history()`.
- Failed runs can be replayed from the last successful checkpoint.

---

## 6. State Schema

```python
from typing import TypedDict, Optional, List, Dict, Any, Literal

class JobSearchState(TypedDict, total=False):
    # Identity
    user_id: str
    application_id: str
    workflow_id: str

    # Inputs
    raw_jd: str
    raw_cv_text: str

    # Security outputs
    redacted_jd: str
    redacted_cv: str
    pii_findings: List[Dict[str, Any]]
    injection_flags: List[str]

    # Parsed
    parsed_job: Dict[str, Any]
    candidate_profile: Dict[str, Any]

    # Research loop
    research_iterations: int
    research_notes: List[Dict[str, Any]]
    company_brief: Optional[str]

    # Matching
    fit_score: float
    score_breakdown: Dict[str, float]
    decision: Literal["apply", "maybe", "skip"]
    decision_reason: str

    # Generation
    tailored_bullets: List[str]
    cover_letter: Optional[str]

    # Evaluation
    eval_scores: Dict[str, float]
    quality_gate_passed: bool

    # System
    current_step: str
    errors: List[str]
    retry_count: int
    awaiting_approval: bool

    # Cost telemetry (denormalized for quick reads)
    total_tokens: int
    total_cost_eur: float
```

---

## 7. Provider Abstraction & Cost-Aware Router

### 7.1 Interface

```python
class LLMProvider(Protocol):
    async def generate(
        self,
        system: str,
        messages: List[Message],
        model: str,
        max_tokens: int,
        temperature: float,
        metadata: Dict[str, Any],   # workflow_id, agent, step
        stream: bool = False,
    ) -> LLMResponse: ...

class LLMResponse(BaseModel):
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int          # prompt-cache hits
    latency_ms: int
    estimated_cost_eur: float
    raw_finish_reason: str
```

Implementations: `OpenAIProvider`, `AnthropicProvider`. Adding Gemini = one new file.

### 7.2 Router

| Task | Default | Fallback | Rationale |
|---|---|---|---|
| JD parsing | `gpt-4.1-mini` | `claude-haiku-4-5` | cheap, structured |
| CV profile compress | `claude-sonnet-4-6` | `gpt-4.1-mini` | runs once, quality matters |
| Research loop steps | `gpt-4.1-mini` | `claude-haiku-4-5` | many short calls |
| Matcher (scoring) | `gpt-4.1-mini` | `claude-haiku-4-5` | structured reasoning |
| Cover letter | `claude-sonnet-4-6` | `gpt-4.1-mini` | human-facing prose |
| Evaluator | `gpt-4.1-mini` | `claude-haiku-4-5` | classification |

Router enforces:
- Hard monthly budget cap (configurable, default €15)
- Per-workflow soft cap (default €0.50, can be raised)
- Per-step max output tokens
- Automatic fallback on provider error
- Failure-injection tests to prove the fallback works (kill OpenAI mid-workflow → expect Claude completion)

### 7.3 Caching

- Anthropic prompt caching for the system prompt + compressed CV profile (huge token saver because the CV doesn't change between applications).
- In-process LRU for parsed-JD by hash (skip re-parse on duplicate paste).
- Reported cache savings on the observability page with measured numbers — not aspirational.

---

## 8. MCP Server

### 8.1 Why this is in V1

In 2026, demonstrating MCP fluency is a strong signal. It's also genuinely useful: the author can invoke CareerOS tools directly from Claude Desktop during his job search.

### 8.2 Exposed tools

| Tool | Description |
|---|---|
| `analyze_jd` | Returns parsed JD structure given raw text |
| `score_fit` | Returns fit score + breakdown given JD text |
| `generate_cover_letter` | Returns Ireland-tuned cover letter |
| `research_company` | Runs the agentic research loop, returns structured brief |
| `list_applications` | Returns user's tracker with statuses |

The MCP server is a thin wrapper that calls the same underlying LangGraph nodes. No business logic duplication.

### 8.3 Demo flow

> User in Claude Desktop: *"Use careeros to score this JD against my CV and draft a cover letter."*
>
> Claude Desktop calls `score_fit` → gets 82 → calls `generate_cover_letter` → returns draft inline.

This is recorded as a 60-second demo video and embedded in the README.

---

## 9. Token & Cost Governance

### 9.1 Tracking

Every LLM call writes a row to `llm_usage_events`:

```sql
CREATE TABLE llm_usage_events (
    id              UUID PRIMARY KEY,
    application_id  UUID REFERENCES applications(id),
    workflow_id     TEXT NOT NULL,
    node_name       TEXT NOT NULL,
    step_name       TEXT,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    cached_tokens   INTEGER,
    total_tokens    INTEGER,
    estimated_cost_eur NUMERIC(10,6),
    latency_ms      INTEGER,
    cache_hit       BOOLEAN,
    retry_count     INTEGER,
    status          TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 9.2 Budget guard

A `BudgetGuard` is consulted before every LLM call:
- Reads month-to-date spend.
- Warns at 70% threshold (logged + surfaced in UI).
- Hard-blocks at 100% with a clear error.
- Manual override flag for testing.

### 9.3 Reported metrics (single observability page)

- Month-to-date spend vs. budget
- Spend by provider, model, node
- Average cost per workflow
- Cache savings (€ and %)
- Most expensive workflow this month

That's it. No four dashboards. One page, real numbers.

---

## 10. Security

### 10.1 PII redaction

`SecurityAgent` (the only thing legitimately called an "agent" outside the LangGraph nodes) runs first:

- Detects: emails, phone numbers, addresses, PPSN, document numbers, full names.
- Replaces with typed placeholders: `[EMAIL]`, `[PHONE]`, `[CANDIDATE_NAME]`.
- Original PII is stored encrypted (AES-GCM) in a separate column with restricted access.
- Logs **never** contain raw PII.
- A test asserts redaction works on a fixture set.

### 10.2 Prompt-injection defense

JDs are untrusted input. The system:
- Wraps JD content in strict delimiters before any LLM call.
- Runs a small classifier prompt that flags injection patterns ("ignore previous", "reveal system prompt", "send data to", etc.).
- Includes a regression set of ~15 attack JDs that the system must catch in CI.
- Treats classifier-flagged JDs as `quarantined` — human must review before processing.

### 10.3 Secrets

- `.env` for local; AWS Secrets Manager / GCP Secret Manager for prod.
- No keys in the public repo.
- `.env.example` and a redacted sample CV ship with the repo.

---

## 11. Evaluation Harness

### 11.1 The dataset

A folder `evals/dataset/` containing 50 labeled JD/CV pairs:
- 25 real JDs scraped manually + 25 synthetic JDs covering edge cases
- Each pair labeled with: expected `decision` (apply/maybe/skip), expected required skills, expected fit score band

### 11.2 What gets evaluated

| Output | Metric |
|---|---|
| JD parsing | F1 on extracted skills vs. labels |
| Fit score | Mean absolute error vs. labeled bands |
| Decision | Accuracy on apply/maybe/skip classification |
| Cover letter | Factuality (LLM-as-judge against CV evidence) + ATS keyword coverage (rules-based) |
| Research brief | LLM-as-judge for relevance + groundedness |

### 11.3 CI integration

- `pytest evals/` runs on every PR.
- Runs against `gpt-4.1-mini` and `claude-haiku-4-5` in parallel.
- Posts a comparison table to the PR comment.
- Fails the PR if any metric regresses by > 5% from the main branch.

### 11.4 Published benchmark

The README contains a results table:

| Task | OpenAI mini | Claude Haiku | Best |
|---|---:|---:|---|
| JD parsing F1 | 0.87 | 0.84 | OpenAI |
| Fit score MAE | 6.2 | 5.8 | Claude |
| Decision accuracy | 0.92 | 0.90 | OpenAI |
| Cover-letter factuality | 0.95 | 0.97 | Claude |

Numbers are real, not made up. This single artifact is what most portfolio projects are missing.

---

## 12. Observability

### 12.1 LangSmith
- All LangGraph runs traced.
- Per-node latency, token, cost.
- Feedback scores tied back to runs.

### 12.2 Structured logs
- JSON logs to stdout (Cloud Run / CloudWatch friendly).
- `workflow_id`, `application_id`, `node`, `model`, `cost_eur`, `latency_ms` on every relevant log line.
- Never contain raw PII (enforced by a test).

### 12.3 Metrics
- Prometheus-style counters and histograms for: workflow starts, completions, errors, cost.
- Exposed at `/metrics`.

---

## 13. Database

Six tables, no more:

```sql
users(id, email_hash, created_at)
applications(id, user_id, company, role_title, job_url, status, fit_score, decision, created_at, applied_at)
job_analyses(id, application_id, parsed_job JSONB, score_breakdown JSONB, company_brief TEXT, created_at)
generated_artifacts(id, application_id, type, content, model, eval_scores JSONB, approved BOOLEAN, created_at)
llm_usage_events(...)  -- defined above
budget_limits(user_id, monthly_budget_eur, alert_threshold)
```

LangGraph checkpoints live in their own schema managed by the LangGraph Postgres checkpointer.

---

## 14. API Design

```text
# Workflow control
POST   /api/applications               # create, returns application_id
POST   /api/applications/{id}/run      # trigger LangGraph workflow
GET    /api/applications/{id}          # full state
GET    /api/applications/{id}/stream   # SSE: stream cover letter generation
POST   /api/applications/{id}/approve  # resume from HITL gate
POST   /api/applications/{id}/reject   # cancel after HITL gate

# Listing
GET    /api/applications               # tracker view

# Cost / observability
GET    /api/usage/monthly
GET    /api/usage/by-node

# MCP server
GET    /mcp                            # MCP discovery endpoint
POST   /mcp/tools/{tool_name}/invoke
```

Total: 9 REST endpoints + MCP. Compare to v1's 14+. Smaller surface = fewer half-built endpoints in the demo.

---

## 15. UI

**One page**, built with Next.js + Tailwind (or plain HTML+htmx if time-constrained):
- Paste a JD, see the live workflow run with status per node.
- See fit score, decision, and the generated cover letter.
- Approve / reject button (the HITL gate).
- Tracker table at the bottom.
- A tiny "Spend this month" widget in the header.

That's the whole UI. No multi-page dashboard. The author can use it daily; reviewers can demo it in 60 seconds.

CLI is also provided for power use:

```bash
careeros run --jd-file ./roles/openai_dublin.md
careeros score --jd "..." 
careeros tracker
careeros usage --month 2026-05
```

---

## 16. Repo Structure

```text
careeros-ai/
├── README.md                # platform-first positioning, demo video, eval table
├── ARCHITECTURE.md          # diagram + decisions
├── THREAT_MODEL.md          # PII + injection threat model
├── EVAL_REPORT.md           # latest benchmark numbers
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── app/
│   ├── main.py
│   ├── api/                 # FastAPI routes (REST + SSE)
│   ├── mcp/                 # MCP server
│   ├── graph/               # LangGraph workflow + state + checkpointer
│   ├── nodes/               # one file per node
│   │   ├── preprocess.py
│   │   ├── profile.py
│   │   ├── research_loop.py
│   │   ├── matcher.py
│   │   ├── generator.py
│   │   └── evaluator.py
│   ├── llm/                 # provider abstraction + router + caching + budget
│   ├── security/            # pii + injection
│   ├── db/                  # models + migrations
│   └── prompts/             # versioned prompt files
├── evals/
│   ├── dataset/             # 50 labeled JD/CV pairs
│   ├── runners/             # eval scripts
│   └── reports/             # generated benchmark tables
├── frontend/                # Next.js single page (or plain HTML)
├── tests/
│   ├── test_pii_redaction.py
│   ├── test_injection_classifier.py
│   ├── test_budget_guard.py
│   ├── test_provider_fallback.py
│   ├── test_research_loop.py
│   └── test_workflow_resume.py
├── deploy/
│   ├── cloudrun.yaml
│   └── ecs-task-def.json    # parity reference
└── .github/workflows/
    ├── ci.yml               # lint + tests
    ├── eval.yml             # eval regression on PR
    └── deploy.yml           # to Cloud Run
```

---

## 17. Build Phases (6 weeks, realistic)

### Week 1 — Foundations
- FastAPI skeleton, Postgres, Docker Compose
- Provider abstraction (OpenAI + Claude)
- Token tracking + cost calculator + budget guard
- PII redactor + injection classifier
- Tests for the above
**Ship checkpoint:** these alone form a small reusable LLM-platform library

### Week 2 — Workflow
- LangGraph workflow with the 5 functional nodes
- Postgres checkpointer
- HITL approval interrupt + resume
- Structured logging

### Week 3 — Agentic loop + MCP
- Implement `research` agentic loop with web_search + fetch_url tools
- MCP server exposing 4 tools
- Streaming SSE for cover-letter generation

### Week 4 — Evaluation
- Build 50-pair labeled dataset
- Eval runners for the 5 metrics
- CI integration: PR comment with comparison table
- Failure-injection tests for provider fallback

### Week 5 — UI + Deploy
- Single-page web UI
- CLI
- Cloud Run deployment via GitHub Actions
- LangSmith integration

### Week 6 — Polish
- README rewrite with platform-first positioning
- Architecture diagram
- Threat model doc
- Eval report doc
- 90-second demo video
- One blog post: "Why I chose LangGraph checkpointing over X for resumable agentic workflows"
- Optional: extract `app/llm/` as a small standalone PyPI package

If a week slips, the **eval harness and MCP server are non-negotiable**. They are the differentiators. Cut UI polish or research-loop sophistication first.

---

## 18. Acceptance Criteria

### 18.1 Functional
- A user can paste a JD and within ~60 seconds receive a fit score, decision, company brief, and (if `apply`) a draft cover letter.
- The user can approve or reject before the artifact is finalized.
- Workflows survive a process restart (checkpointer test).
- A killed OpenAI provider does not break a workflow (fallback test).
- Hard budget cap stops a workflow that would exceed it.

### 18.2 Observability
- LangSmith trace for every workflow.
- `/api/usage/monthly` returns accurate cost numbers.
- Logs contain no raw PII (asserted in a CI test).

### 18.3 Eval
- Benchmark numbers in EVAL_REPORT.md are reproducible from the eval scripts.
- CI fails the PR if any metric regresses > 5%.

### 18.4 Portfolio
- README has: 60-second hook, demo video, architecture diagram, eval table, threat model link.
- Repo runs locally via `docker compose up` after copying `.env.example` to `.env`.
- Public sample data only — no real CV in repo.

---

## 19. README Hook (top of repo)

```markdown
# CareerOS AI — Agentic Workflow Platform

CareerOS AI is a production-grade LangGraph platform for stateful, evaluated,
cost-governed agentic workflows. It demonstrates the architectural patterns
modern enterprise GenAI teams are converging on: provider abstraction,
genuine agentic loops with tool use, prompt-injection defense, per-step cost
governance, MCP interoperability, and a CI-integrated evaluation harness with
published benchmarks.

The reference application is a job-search workflow: paste a JD, get a calibrated
fit score, an auto-researched company brief, and a draft cover letter — with
every LLM call traced, costed, evaluated, and gated by human approval.

→ 90-second demo video
→ Architecture diagram
→ Latest eval results: OpenAI vs Claude across 5 tasks
→ Threat model
→ Live demo (Cloud Run): https://...
```

---

## 20. Resume Bullet (rewritten)

> **Designed and shipped CareerOS AI, a LangGraph-based agentic workflow platform with multi-provider LLM abstraction (OpenAI/Claude), Postgres-backed state checkpointing, an agentic research loop with tool use, MCP server, prompt-caching cost governance, PII + prompt-injection defense, and a CI-integrated evaluation harness with a published 50-pair benchmark. Deployed on Cloud Run with LangSmith tracing.**

Specific. Verifiable. Maps to staff/architect-level hiring rubrics. No "16 agents."

---

## 21. Stretch (post-V1, only if V1 ships clean)

- Interview-prep node (only if eval data shows it has signal)
- Recruiter-outreach node (only if user demand justifies)
- Gemini provider (third provider validates the abstraction)
- A2A protocol experiment for inter-agent communication
- Extracted `careeros-llm-platform` PyPI package
- Conference talk submission

---

## 22. Anti-patterns to avoid in implementation

1. Don't call services "agents." `tracker_agent` is just a CRUD service. Be honest in naming.
2. Don't add embeddings until there's something to retrieve over. The CV+JD pair is one document each — structured prompting beats vector search here.
3. Don't add the reflection loop until N>>1 user data exists.
4. Don't ship a Streamlit dashboard alongside a Next.js page. Pick one.
5. Don't claim "production" with SQLite. Use Postgres from day one.
6. Don't write aspirational metrics in the README. Run the eval, paste real numbers.
7. Don't bury the platform positioning under the job-search use case. Lead with the platform.

---

## 23. Self-check before shipping V1

Ask, brutally:
- [ ] Does the README convince a senior reviewer in 30 seconds this isn't another AI cover-letter generator?
- [ ] Is there a real agentic loop (tool use + replanning) someone can read in the code?
- [ ] Does the eval table contain numbers I can reproduce live?
- [ ] Does the failure-injection test prove provider fallback works?
- [ ] Does the budget guard actually block over-budget workflows in a test?
- [ ] Is there a 90-second video I'd be proud to send to a hiring manager?
- [ ] Can I demo MCP tool calls from Claude Desktop on the spot?
- [ ] Is the repo cleanly runnable in under 5 minutes from clone?

If any answer is "no," V1 isn't done.

---

## 24. References / Design basis (current to 2026)

- LangGraph: stateful workflows, Postgres checkpointer, HITL interrupts, time-travel.
- LangSmith: tracing, evals, monitoring.
- MCP (Model Context Protocol): tool-server interoperability with Claude Desktop and other clients.
- Anthropic prompt caching: significant cost reduction for stable system prompts and long context.
- OpenAI structured outputs: for parsed JD and decision schemas.
- Cloud Run: serverless container deploy, well-suited to bursty agentic workloads.

---

*End of v2 spec. Tighter, more honest, more hireable, and still genuinely useful for the author's own job search.*

---

## 25. Addenda (post-spec amendments)

Amendments to the v2 spec are logged here so the master document stays authoritative as scope evolves.

### 25.1 Ireland-first geography (2026-05-14)

CareerOS AI's reference deployment targets **jobs in Ireland (`ie`)**. This is the explicit V1 focus:

- All cover-letter prompts include Stamp 1G / Critical Skills Permit context.
- Salary thresholds and budget caps are in EUR.
- Scraper queries default to Ireland.
- Test fixtures use Ireland-relevant role titles.

**Country is a single configurable knob** — `default_country` in `config/profile.yml`. Changing it (plus the `locations[]` entries) retargets the system to another market. The architecture is country-agnostic; only the *defaults* are Ireland-tuned. Never hardcode country assumptions in code — read from `UserProfile.default_country` or `SearchLocation.country`.

### 25.2 Partner-API job discovery — IN (overrides Section 3.2)

The original Section 3.2 cut "all scraping" wholesale. User direction on 2026-05-14 narrowed this:

- **IN**: Adzuna API (developer.adzuna.com), Reed API (reed.co.uk/developers). Both are official partner APIs with free tiers and explicit ToS permitting our use.
- **STILL OUT**: LinkedIn, Indeed, or any site whose ToS forbids automated access. These flow in via the Chrome extension companion (Week 5), which captures the JD text from a tab the user is already viewing.

Discovered jobs land in a new `discovered_jobs` table (deduped on `(source, external_id)`), auto-run through `preprocess + matcher` only (no generator at discovery time → cost stays bounded), and only `fit_score >= 70` rows are promoted to real `applications`.

### 25.3 MongoDB allowed for principled cases (overrides Section 22 anti-pattern #5)

The original anti-pattern said "no Mongo, Postgres only" full stop. User direction on 2026-05-14 narrowed: Mongo is allowed when *clearly* better for a specific use case (e.g. large raw HTML capture from the Week-3 research loop). Postgres remains the default; switching requires a stated reason in the PR/commit, not aesthetic preference. See `feedback_datastore_choice` memory.

### 25.4 Single-user session auth + encrypted settings store (2026-05-14)

The original spec assumed single-user with no auth (Section 3.2 implicit). User direction on 2026-05-14: because a Settings page now exposes editable API keys and model overrides, the UI and API must be gated behind a password.

**What ships:**

- New `app_settings` table: `(key TEXT PK, encrypted_value BYTEA, nonce BYTEA, is_secret BOOL, updated_at TIMESTAMPTZ)`. AES-GCM with `PII_ENCRYPTION_KEY` (auto-generated if missing).
- New `app/auth.py`: bcrypt password hashing + `itsdangerous` signed-cookie sessions (7-day TTL, HttpOnly, SameSite=lax).
- `app/api/auth.py`: `init`, `login`, `logout`, `me`, `status`, `change-password`.
- `/ui/login.html`: dual-mode (first-run setup vs. standard login), auto-detected via `GET /api/auth/status`.
- Middleware in `app/main.py` enforces session cookie on every `/api/*` and `/ui/*` route by default.

**Whitelist (no cookie required):**

| Path | Reason |
|---|---|
| `GET /healthz`, `GET /metrics` | Monitoring; unsafe to require auth |
| `POST /api/captures` | Chrome extension authenticates with bearer token (`EXTENSION_API_TOKEN`) and CORS; cross-origin cookies from `chrome-extension://` are messy |
| `GET /api/auth/*` | Bootstrap; you can't log in without it |
| `/ui/login.html` and its assets (`login.css`, `login.js`, `styles.css`) | Same reason |
| `/docs`, `/openapi.json`, `/redoc` | Dev-time convenience — could be gated in a future prod profile |

**Settings precedence at runtime:** DB value (via `settings_store.get`) → env var → hardcoded default. Code that reads secrets or model names must go through `settings_store.effective_secret(name, env)` rather than `os.environ` or `get_settings()` directly, so UI overrides take effect without restarting the app.

**Out of scope (explicit):** multi-user, SSO, RBAC, password reset via email, MFA. Single-user local app — none of these apply at V1 scale.

### 25.5 Settings UI + runtime-editable config (2026-05-14)

Companion to Section 25.4. Realises spec Section 9's observability page and Section 7's router as user-tweakable surfaces:

- `GET /api/settings` — returns the full editable tree. Secrets are masked (`sk-•••••345`) and tagged with their source (`db` / `env` / unset). The cleartext is never returned by any GET.
- `PUT /api/settings/{key}` — upserts. Empty value deletes the row → reverts to env. Allowed keys are explicitly whitelisted in `app.api.settings._ALLOWED_BARE_KEYS` + the `model.<task>.<default|fallback>` pattern; anything else 400s.
- `POST /api/settings/test/{provider}` — connectivity check that hits the provider's own auth endpoint (`/v1/models` for OpenAI, `/v1/messages` for Anthropic, `/categories` for Adzuna, `/search` for Reed/Tavily) and returns `{ok, status, detail}`. Used by the **Test** buttons next to each key in the UI.
- `/ui/settings.html` — three panels (API keys, Models per task, Budgets) plus a Change password form. All session-protected.

**Runtime precedence:** every secret/model read now goes through `app.settings_store.effective_secret(name, env_value)` or `get(name)`. Router, OpenAI/Anthropic providers, and the scraper registry are all converted. UI edits take effect on the next call, no restart.

**Lazy provider re-init**: `OpenAIProvider._ensure_client` / `AnthropicProvider._ensure_client` runs before every `generate()` and rebuilds the SDK client if the effective key changed. Safe because client construction is cheap.

**Test-mode resilience**: settings_store reads inside hot paths swallow exceptions silently and fall back to spec defaults. This keeps unit tests passing without Postgres while still allowing the live app to honour UI overrides.

### 25.6 Application lifecycle tracker — manual entry (2026-05-14)

Realises the Section 17 week-5 "tracker" gap as user-facing functionality. All entry is **manual** — no automation infers or sets status. This is deliberate: at single-user scale, automation invents data; manual entry gives ground truth for the eval harness (week 4) and respects job-search nuance (e.g. "ghosted at week 3 then suddenly responded" is not modellable).

**Schema** (migration `0005_application_lifecycle`):

| Column | Meaning |
|---|---|
| `application_status TEXT NULL` | One of `ALLOWED_STATUSES`. NULL = not yet triaged. |
| `applied_at TIMESTAMPTZ NULL` | When the user submitted the application. Auto-filled to `now()` the first time the user sets a status in `APPLIED_STATUSES`, but always editable. |
| `status_updated_at TIMESTAMPTZ NULL` | Bookkeeping for the dashboard's "stale follow-ups" panel. |
| `status_history JSONB NOT NULL DEFAULT '[]'` | Append-only list of `{at, status, note}` entries. Never truncated by the app. |

**Status vocabulary** (`app.api.lifecycle.ALLOWED_STATUSES`):

| Status | Bucket | Notes |
|---|---|---|
| `bookmarked` | pre-application | Saved for later, not applied yet. |
| `applied` | open · applied | You submitted the application. |
| `screening` | open · applied · responded | Recruiter call done, technical not yet. |
| `interview` | open · applied · responded | Technical / onsite scheduled or done. |
| `offer` | open · applied · responded | Offer in hand, not yet decided. |
| `accepted` | applied · responded · closed | Offer accepted. |
| `rejected` | applied · responded · closed | Either party said no after engagement. |
| `ghosted` | applied · closed | No response after N weeks; user-declared. |
| `withdrawn` | applied · closed | User withdrew. |
| `not_applying` | closed | User triaged and decided no. |

`OPEN_STATUSES = {applied, screening, interview, offer}` — drives the "open pipeline" card.
`APPLIED_STATUSES` = everything except `bookmarked`, `withdrawn`, `not_applying` — drives "total applied" and "avg fit applied".
`RESPONDED_STATUSES = {screening, interview, offer, accepted, rejected}` — drives response rate. Note `ghosted` is in `APPLIED_STATUSES` but **not** in `RESPONDED_STATUSES`, so `response_rate = responded/applied` is well-defined.

Set membership is asserted by `tests/test_lifecycle.py` so a future maintainer adding a status has to think about which bucket it belongs to.

**API**:

```
POST /api/jobs/{id}/status
  { "status": "applied", "applied_at": "2026-05-14T...", "note": "..." }
  → 200 { id, application_status, applied_at, status_updated_at, status_history }

GET /api/stats/dashboard
  → { total_jobs, by_status, open_pipeline, applied_total, responded_total,
      response_rate, avg_fit_applied, applied_per_week, top_companies_applied,
      stale_followups, allowed_statuses }
```

**UI**: `/ui/dashboard.html` (cards + status bars + weekly bar chart + top companies + stale follow-ups) and a new "Application" section on every inbox detail panel (status dropdown, applied-date picker, note textarea, status history details).

**Stale follow-ups** = applications in `applied` or `screening` whose `status_updated_at < now - 14d`. Surfaces in the dashboard "Stale follow-ups" panel; links back to the inbox row.

**Out of scope (explicit)**: no automatic state inference from email/calendar/Slack; no scraping of recruiter messages; no Slack/email reminders on stale follow-ups (UI-only nudge for V1).

### 25.7 Inline streaming cover-letter generation (2026-05-14)

Realises Section 14's streaming endpoint as the daily-use payoff. Apply-band jobs (or any job with `?force=true`) get a cover letter drafted into the inbox detail panel via server-sent events, edited inline, then saved as draft or approved.

**Schema** (migration `0006_cover_letter`): new columns on `discovered_jobs`:

| Column | Meaning |
|---|---|
| `cover_letter TEXT NULL` | Current draft text. |
| `cover_letter_bullets JSONB NOT NULL DEFAULT '[]'` | Tailored CV bullets. |
| `cover_letter_model VARCHAR(64) NULL` | Provider/model that produced this draft (e.g. `openai/gpt-4.1-mini`). |
| `cover_letter_generated_at TIMESTAMPTZ NULL` | Last generation timestamp. |
| `cover_letter_approved BOOL NOT NULL DEFAULT false` | User-signed-off flag. Regeneration over an approved letter requires `?force=true`. |
| `cover_letter_generations INT NOT NULL DEFAULT 0` | Counter for cost-awareness ("you've regenerated this 4 times for €0.012"). |
| `cover_letter_total_cost_eur NUMERIC(10,6) NOT NULL DEFAULT 0` | Sum of `estimated_cost_eur` across all generations on this row. |

**Provider streaming contract** (`app.llm.types.StreamDelta`): every provider exposes `stream_text(request)` as an async iterator that yields `StreamDelta(text=...)` for each token batch and terminates with a single `LLMResponse` carrying real usage stats. Both `OpenAIProvider` (using `stream_options.include_usage`) and `AnthropicProvider` (using `client.messages.stream` context manager + `get_final_message()`) implement this.

**Router streaming** (`Router.route_stream`): default-then-fallback behaviour mirrors the non-stream path, but **only** falls back if the default provider raises *before emitting any delta*. Mid-stream errors propagate to the client — partial-then-restart UX is worse than honest failure.

**SSE endpoint** `POST /api/jobs/{id}/generate?force=true|false`:

```
event: meta    data: {model, generations}
event: delta   data: {text}          ← repeated
event: final   data: {full_text, bullets, model, cost_eur, prompt_tokens, completion_tokens, generations, total_cost_eur}
event: error   data: {detail}
```

Preconditions enforced:

- Row must have a `parsed_job` (i.e. been scored). Otherwise 422 "score the job first".
- Unless `force=true`, `fit_score >= APPLY_BAND_THRESHOLD` (70). Otherwise 422 with the threshold message.
- Unless `force=true`, `cover_letter_approved` must be false. Otherwise 409.

On the `final` event, the draft is persisted with `approved=false` and the generation counter + cumulative cost are updated. The user signs off via:

```
PUT  /api/jobs/{id}/cover-letter        {cover_letter, bullets?, approved?}
POST /api/jobs/{id}/cover-letter/approve
POST /api/jobs/{id}/cover-letter/unapprove
```

**UI** (`/ui/`): inbox detail panel gains a Cover letter section with state pill (`No draft yet` / `Streaming…` / `Draft (unsaved)` / `Approved` / `Failed`), editable textarea (live-filled by the SSE stream), bullets list, and Generate / Regenerate / Save draft / Approve & save / Unapprove buttons. The textarea is the canonical source of truth — the user can edit between Generate and Approve.

**Cost discipline**: every regeneration writes a row to `llm_usage_events` (via the existing `record_usage` middleware) and bumps `cover_letter_total_cost_eur`. The Usage page surfaces both. Generations on `bookmarked`/`not_applying` rows require `force=true` so the user can't accidentally burn budget on jobs they've already triaged out.

**Out of scope for V1**: no template versioning per-role (one prompt for all letters); no language switching; no PDF export from the UI (copy/paste is fine); no calendar integration for follow-up reminders.

### 25.8 Agentic research loop with web_search + fetch_url (2026-05-14)

Realises spec Section 5.1's "research (agentic loop)" node as a stand-alone, UI-visible feature. **One real plan→act→observe→stop loop with tool use** — the differentiator between "stateful pipeline" and "agentic platform" called out in spec Section 5.2.

**Schema** (migration `0007_research`): five new columns on `discovered_jobs`:

| Column | Meaning |
|---|---|
| `company_brief JSONB NOT NULL DEFAULT '{}'` | Structured output from the synthesizer: summary, what_they_do, tech_stack_signals, recent_news[], culture_signals[], red_flags[], sources[]. Every claim cites a `source_index` into the sources array. |
| `research_trace JSONB NOT NULL DEFAULT '[]'` | Append-only record of every step the agent took. Used by the UI to visualise the loop, and as evidence for the eval harness. |
| `research_iterations INT NOT NULL DEFAULT 0` | Number of plan steps the agent ran on the last invocation. Hard-capped at `MAX_ITERATIONS = 6`. |
| `research_at TIMESTAMPTZ NULL` | Timestamp of the last successful synthesis. |
| `research_total_cost_eur NUMERIC(10,6) NOT NULL DEFAULT 0` | Append-only sum across all research runs for this row. |

**Tools** (`app/research/tools.py`):

- `web_search(query)` — Tavily API. Returns `SearchResult(query, hits, error)`. Error-tolerant: a missing key or HTTP failure returns `error` set, hits empty; the agent treats it as an observation rather than a crash.
- `fetch_url(url)` — `httpx` with strict limits: HTTPS-or-HTTP only, 12 s timeout, 350 KB max response, HTML-or-text content-type, body trimmed to 12 K chars after `<script>`/`<style>` stripping. Returns `FetchResult` with `error` set on any rejection so the agent moves on cleanly.

**Agent loop** (`app/research/agent.py::run_research`):

```
for iteration in 1..MAX_ITERATIONS:
    plan = LLM(prompts/research_plan.md, company, role, notes_so_far)
    yield ResearchEvent(kind="plan", data={...})
    if plan.action == "stop": break
    if plan.action == "search":
        if query in seen_queries: yield error event; continue
        result = await web_search(query)
        notes.append(observation)
        yield ResearchEvent(kind="tool_result", ...)
    elif plan.action == "fetch":
        # same dedupe pattern on URLs
brief = LLM(prompts/research_synthesize.md, observations)
yield ResearchEvent(kind="final", data={brief, trace, ...})
```

Honest agentic behaviours:

- **Dedupe sets** on queries (lowercased) and URLs prevent loops.
- **Notes window**: the most recent `MAX_TOTAL_NOTES = 14` observations are fed back to the planner, oldest dropped.
- **`<observation>` delimiters** wrap untrusted tool output before the LLM sees it, with an explicit data-not-instructions clause in the system prompt.
- **Trace is the audit trail** — even error / dedupe-rejected steps are logged with their reason so a future eval can score loop quality.

**SSE endpoint** `POST /api/jobs/{id}/research`:

```
event: meta         {company, role}
event: plan         {iteration, action, query?, url?, reason, cost_eur}
event: tool_result  {iteration, tool, hits|excerpt, error?}
event: synthesize   {iterations}
event: final        {brief, trace, iterations, cost_eur, total_cost_eur, research_at}
event: error        {detail}
```

Preconditions: row must have a non-`(unknown)` company name (422 otherwise). No apply-band check — research is cheap (~€0.003) and often more useful on borderline-fit roles to decide whether to apply at all.

**UI**: inbox detail panel "About this company" section. State pill colour-bands `thinking` (accent) / `acting` (warn) / `ready` (ok) / `error` (err). Agent trace renders as a vertical list with iteration number, action pill, and one-line rationale + linked tool result. Brief renders below the trace with summary, what-they-do, tech-stack chips, recent news, culture signals, red flags (only shown if non-empty, header in red), and a numbered sources list every claim links into.

**Cost discipline**: each plan step + the synthesizer write `llm_usage_events` rows via the standard recording middleware. A full research run sits around €0.002–€0.005 on `gpt-4.1-mini` — comparable to one cover-letter generation.

**Out of scope for V1**: no parallel tool dispatch (one tool per iteration keeps the trace human-readable); no robots.txt parsing (we don't crawl, we fetch single URLs the agent explicitly chose); no caching of search results across jobs (Tavily free tier is 1k/month — comfortable headroom); no per-source quality weighting in the synthesizer (it grounds on whatever the agent picked).

### 25.9 MCP server exposing tools to Claude Desktop (2026-05-14)

Realises spec Section 8's MCP server. Five tools over stdio, structured-JSON returns, single-user, sharing the same `settings_store` and `Router` as the HTTP app.

**Entry point** `app/mcp_server.py` is run as a subprocess by the MCP client (Claude Desktop). Tools:

| Tool | Internal call | Returns |
|---|---|---|
| `analyze_jd(raw_jd)` | `app.mcp.tool_handlers.analyze_jd` | `{ok, quarantined, parsed_job, cost_eur}` |
| `score_fit(raw_jd)` | `app.mcp.tool_handlers.score_fit` | `{ok, fit_score, decision, decision_reason, score_breakdown, parsed_job, cost_eur}` |
| `generate_cover_letter(raw_jd)` | `app.mcp.tool_handlers.generate_cover_letter` | `{ok, fit_score, decision, cover_letter, bullets, cost_eur}` — only generates when matcher returns `apply`; below-threshold use HTTP `?force=true`. |
| `research_company(company, role?)` | `app.mcp.tool_handlers.research_company` | `{ok, brief, trace, iterations, cost_eur}` — collects the full async-iterator output of the agent loop synchronously since MCP is request/response. |
| `list_applications(status?, limit?)` | `app.mcp.tool_handlers.list_applications` | `{count, filter, applications[]}` ordered by `scraped_at desc`, lifecycle-filterable. |

**Transport hygiene**:

- All logs go to **stderr** via stdlib `logging.basicConfig(stream=sys.stderr, ...)`. Stdout is the MCP wire format and must stay clean — a single stray `print()` corrupts the JSON-RPC stream and Claude Desktop disconnects.
- The `Server` is constructed once; `get_context()` is the same `lru_cache`'d singleton the HTTP app uses, so model overrides + API keys edited via the Settings UI take effect on the next MCP call too.
- Tool handler exceptions are caught at the call_tool boundary and surfaced as `{ok: false, detail: ...}` — never propagated to the MCP framework (which would tear down the session).

**Auth model**: stdio MCP doesn't ride on the HTTP session cookie. The OS process boundary IS the auth — only the user who can spawn the Python interpreter under their account can invoke the tools. The MCP server is **read-only on the lifecycle**: no tool can update status, approve a letter, or delete a job. Mutations stay in the HTTP API behind the session-cookie gate.

**Cost tracking**: every tool call writes `llm_usage_events` rows via the shared `record_usage` middleware, tagged `node_name = "mcp.<tool>"` so they're distinguishable from inbox-driven runs on the Usage page.

**Wiring**: see [product-requirements/mcp-server.md](mcp-server.md) for the Claude Desktop config snippet (native venv path recommended; in-container via `docker compose exec` documented as the alternative).

**Out of scope for V1**:
- No mutation tools (`set_status`, `approve_letter`, `delete_job`). Anything that changes server state stays HTTP-only — the audit trail is clearer that way.
- No streaming tools. MCP doesn't support partial responses well; `research_company` collects the loop synchronously. For live streaming UX use the HTTP SSE endpoints.
- No prompt servers. The MCP `prompts` capability isn't exposed — the prompts live in `app/prompts/` versioned by the spec, not duplicated over the MCP boundary.
- No tool-defined sampling. MCP supports clients sampling from a server's preferred model; we let Claude Desktop pick its own model and only return data.
