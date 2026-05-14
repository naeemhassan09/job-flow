from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from app.graph.state import JobSearchState
from app.llm import prompts
from app.llm.json_utils import parse_json
from app.llm.types import LLMRequest, Message
from app.security.pii import redact

from ._common import context_from, stamp_call_context


async def profile(state: JobSearchState, config: RunnableConfig) -> JobSearchState:
    stamp_call_context(state, "profile")
    ctx = context_from(config)

    raw_cv = state.get("raw_cv_text") or ctx.profile.load_cv_text()
    redacted_cv, _ = redact(raw_cv, candidate_names=ctx.profile.candidate.full_names)

    prompt = prompts.load("profile")
    response = await ctx.router.route(
        "cv_profile_compress",
        LLMRequest(
            system=prompt.system,
            messages=[Message(role="user", content=prompt.render_user(redacted_cv=redacted_cv))],
            model="placeholder",
            temperature=0.0,
            metadata={"node": "profile", "workflow_id": state.get("workflow_id", "")},
        ),
    )
    return {
        "current_step": "profile",
        "redacted_cv": redacted_cv,
        "candidate_profile": parse_json(response.text),
    }
