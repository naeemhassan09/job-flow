from __future__ import annotations

import json

from langchain_core.runnables import RunnableConfig

from app.graph.state import JobSearchState
from app.llm import prompts
from app.llm.json_utils import parse_json
from app.llm.types import LLMRequest, Message

from ._common import context_from, stamp_call_context


async def matcher(state: JobSearchState, config: RunnableConfig) -> JobSearchState:
    stamp_call_context(state, "matcher")
    ctx = context_from(config)
    prompt = prompts.load("matcher")
    response = await ctx.router.route(
        "matcher",
        LLMRequest(
            system=prompt.system,
            messages=[
                Message(
                    role="user",
                    content=prompt.render_user(
                        parsed_job_json=json.dumps(state.get("parsed_job", {})),
                        candidate_profile_json=json.dumps(state.get("candidate_profile", {})),
                    ),
                )
            ],
            model="placeholder",
            temperature=0.0,
            metadata={"node": "matcher", "workflow_id": state.get("workflow_id", "")},
        ),
    )
    parsed = parse_json(response.text)
    score = float(parsed.get("fit_score", 0))
    decision = parsed.get("decision") or _band(score)
    return {
        "current_step": "matcher",
        "fit_score": score,
        "score_breakdown": parsed.get("score_breakdown", {}),
        "decision": decision,
        "decision_reason": parsed.get("decision_reason", ""),
    }


def _band(score: float) -> str:
    if score >= 70:
        return "apply"
    if score >= 50:
        return "maybe"
    return "skip"
