"""Tool handlers used by both the MCP server and the HTTP API.

These wrap the existing workflow nodes / prompts / router so the MCP server
can call them request/response style without going through FastAPI. Each
returns a JSON-serialisable dict (no Pydantic models, no SQLAlchemy rows).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import desc, select

from app.db.models import DiscoveredJob
from app.db.session import get_sessionmaker
from app.graph.context import WorkflowContext
from app.llm import prompts
from app.llm.json_utils import parse_json
from app.llm.types import LLMRequest, Message
from app.llm.usage import CallContext, set_call_context
from app.observability.log import get_logger
from app.profile import UserProfile
from app.security.injection import scan as injection_scan
from app.security.pii import redact

_log = get_logger(__name__)


def _stamp(workflow_id: str, node: str, task: str) -> None:
    set_call_context(
        CallContext(workflow_id=workflow_id, node_name=node, application_id=None, task=task)
    )


async def analyze_jd(ctx: WorkflowContext, raw_jd: str) -> dict[str, Any]:
    """Parse a JD into structured fields. Returns the matcher-ready parsed_job dict.

    Mirrors `app/nodes/preprocess.py` minus the LangGraph plumbing.
    """
    workflow_id = str(uuid.uuid4())
    _stamp(workflow_id, "mcp.analyze_jd", "jd_parsing")
    inj = injection_scan(raw_jd)
    if inj.is_quarantined:
        return {
            "ok": False,
            "quarantined": True,
            "injection_flags": inj.flags,
            "parsed_job": {},
        }
    redacted, _ = redact(raw_jd, candidate_names=ctx.profile.candidate.full_names)
    p = prompts.load("extract")
    response = await ctx.router.route(
        "jd_parsing",
        LLMRequest(
            system=p.system,
            messages=[Message(role="user", content=p.render_user(redacted_jd=redacted))],
            model="placeholder",
            temperature=0.0,
        ),
    )
    parsed = parse_json(response.text)
    return {
        "ok": True,
        "quarantined": False,
        "parsed_job": parsed,
        "cost_eur": float(response.estimated_cost_eur),
    }


async def _candidate_profile_summary(profile: UserProfile) -> dict[str, Any]:
    cv = profile.load_cv_text()
    return {
        "display_name": profile.candidate.display_name,
        "headline": profile.candidate.display_name,
        "location": profile.candidate.location,
        "work_authorisation": profile.candidate.work_authorisation,
        "cv_excerpt": cv[:6000],
    }


async def score_fit(ctx: WorkflowContext, raw_jd: str) -> dict[str, Any]:
    """Run preprocess + matcher only. Returns fit_score + decision + breakdown."""
    pre = await analyze_jd(ctx, raw_jd)
    if not pre.get("ok") or pre.get("quarantined"):
        return {
            "ok": False,
            "quarantined": pre.get("quarantined", False),
            "fit_score": None,
            "decision": None,
            "decision_reason": pre.get("injection_flags") and "quarantined" or "parse failed",
        }
    candidate = await _candidate_profile_summary(ctx.profile)

    workflow_id = str(uuid.uuid4())
    _stamp(workflow_id, "mcp.score_fit", "matcher")
    p = prompts.load("matcher")
    response = await ctx.router.route(
        "matcher",
        LLMRequest(
            system=p.system,
            messages=[
                Message(
                    role="user",
                    content=p.render_user(
                        parsed_job_json=json.dumps(pre["parsed_job"]),
                        candidate_profile_json=json.dumps(candidate),
                    ),
                )
            ],
            model="placeholder",
            temperature=0.0,
        ),
    )
    parsed = parse_json(response.text)
    fit = float(parsed.get("fit_score", 0))
    decision = parsed.get("decision") or ("apply" if fit >= 70 else ("maybe" if fit >= 50 else "skip"))
    return {
        "ok": True,
        "quarantined": False,
        "parsed_job": pre["parsed_job"],
        "fit_score": fit,
        "decision": decision,
        "decision_reason": parsed.get("decision_reason", ""),
        "score_breakdown": parsed.get("score_breakdown", {}),
        "cost_eur": float(pre.get("cost_eur") or 0) + float(response.estimated_cost_eur),
    }


async def generate_cover_letter(ctx: WorkflowContext, raw_jd: str) -> dict[str, Any]:
    """Full pipeline: preprocess + matcher + generator. Returns cover_letter + bullets.

    Note: synchronous (collects the full generator output before returning) since
    MCP is request/response, not streaming. For streaming UX, use the HTTP SSE
    endpoint instead.
    """
    score = await score_fit(ctx, raw_jd)
    if not score.get("ok"):
        return {**score, "cover_letter": None, "bullets": []}
    if score["decision"] != "apply":
        return {
            "ok": True,
            "fit_score": score["fit_score"],
            "decision": score["decision"],
            "decision_reason": score["decision_reason"],
            "cover_letter": None,
            "bullets": [],
            "skipped": "not in apply band — pass force=true via the HTTP API if you want to override",
            "cost_eur": score.get("cost_eur", 0),
        }

    candidate = await _candidate_profile_summary(ctx.profile)
    workflow_id = str(uuid.uuid4())
    _stamp(workflow_id, "mcp.generate_cover_letter", "cover_letter")
    p = prompts.load("generator")
    response = await ctx.router.route(
        "cover_letter",
        LLMRequest(
            system=p.system,
            messages=[
                Message(
                    role="user",
                    content=p.render_user(
                        parsed_job_json=json.dumps(score["parsed_job"]),
                        candidate_profile_json=json.dumps(candidate),
                        company_brief="",
                        tone=ctx.profile.cover_letter_tone,
                        must_mention=ctx.profile.cover_letter_must_mention,
                        forbid_phrases=ctx.profile.cover_letter_forbid_phrases,
                    ),
                )
            ],
            model="placeholder",
            temperature=0.3,
            max_tokens=1400,
        ),
    )
    parsed = parse_json(response.text)
    return {
        "ok": True,
        "fit_score": score["fit_score"],
        "decision": score["decision"],
        "decision_reason": score["decision_reason"],
        "cover_letter": parsed.get("cover_letter"),
        "bullets": list(parsed.get("tailored_bullets") or []),
        "cost_eur": float(score.get("cost_eur", 0)) + float(response.estimated_cost_eur),
    }


async def research_company(
    ctx: WorkflowContext, company: str, role: str = ""
) -> dict[str, Any]:
    """Run the agentic research loop and return the structured brief."""
    from app.research.agent import run_research

    brief: dict | None = None
    trace: list = []
    iterations = 0
    cost_eur = 0.0
    async for ev in run_research(ctx=ctx, company=company, role=role or ""):
        if ev.kind == "plan":
            cost_eur += float(ev.data.get("cost_eur") or 0)
        elif ev.kind == "final":
            brief = ev.data["brief"]
            trace = ev.data["trace"]
            iterations = ev.data.get("iterations", 0)
            cost_eur += float(ev.data.get("synth_cost_eur") or 0)
        elif ev.kind == "error":
            return {
                "ok": False,
                "detail": ev.data.get("detail", "research failed"),
                "brief": None,
                "trace": trace,
            }
    return {
        "ok": brief is not None,
        "brief": brief or {},
        "trace": trace,
        "iterations": iterations,
        "cost_eur": cost_eur,
    }


async def list_applications(
    status: str | None = None, limit: int = 20
) -> dict[str, Any]:
    """Return the inbox in MCP-friendly shape: lightweight, no nulls in the
    top fields, sorted by application_status (open pipeline first) then by
    scraped_at."""
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    async with get_sessionmaker()() as session:
        stmt = (
            select(DiscoveredJob)
            .order_by(desc(DiscoveredJob.scraped_at))
            .limit(limit)
        )
        if status:
            stmt = stmt.where(DiscoveredJob.application_status == status)
        rows = (await session.execute(stmt)).scalars().all()

    return {
        "count": len(rows),
        "filter": {"status": status, "limit": limit},
        "applications": [
            {
                "id": str(r.id),
                "title": r.title,
                "company": r.company,
                "location": r.location,
                "url": r.url,
                "source": r.source,
                "fit_score": float(r.fit_score) if r.fit_score is not None else None,
                "decision": r.decision,
                "application_status": r.application_status,
                "applied_at": r.applied_at.isoformat() if r.applied_at else None,
                "cover_letter_approved": bool(r.cover_letter_approved),
            }
            for r in rows
        ],
    }
