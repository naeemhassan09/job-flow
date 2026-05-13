from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from app.graph.state import JobSearchState
from app.llm import prompts
from app.llm.json_utils import parse_json
from app.llm.types import LLMRequest, Message
from app.security.injection import scan as injection_scan
from app.security.pii import redact

from ._common import context_from


async def preprocess(state: JobSearchState, config: RunnableConfig) -> JobSearchState:
    ctx = context_from(config)
    raw_jd = state.get("raw_jd", "")

    inj = injection_scan(raw_jd)
    redacted_jd, jd_findings = redact(raw_jd, candidate_names=ctx.profile.candidate.full_names)

    update: JobSearchState = {
        "current_step": "preprocess",
        "redacted_jd": redacted_jd,
        "injection_flags": inj.flags,
        "quarantined": inj.is_quarantined,
        "pii_findings": [{"kind": f.kind, "placeholder": f.placeholder} for f in jd_findings],
    }

    if inj.is_quarantined:
        update["errors"] = state.get("errors", []) + ["jd_quarantined"]
        return update

    prompt = prompts.load("extract")
    response = await ctx.router.route(
        "jd_parsing",
        LLMRequest(
            system=prompt.system,
            messages=[Message(role="user", content=prompt.render_user(redacted_jd=redacted_jd))],
            model="placeholder",
            temperature=0.0,
            metadata={"node": "preprocess", "workflow_id": state.get("workflow_id", "")},
        ),
    )
    update["parsed_job"] = parse_json(response.text)
    return update
