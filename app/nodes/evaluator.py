from __future__ import annotations

import json

from langchain_core.runnables import RunnableConfig

from app.graph.state import JobSearchState
from app.llm import prompts
from app.llm.json_utils import parse_json
from app.llm.types import LLMRequest, Message

from ._common import context_from, stamp_call_context


async def evaluator(state: JobSearchState, config: RunnableConfig) -> JobSearchState:
    stamp_call_context(state, "evaluator")
    ctx = context_from(config)

    if state.get("decision") != "apply" or not state.get("cover_letter"):
        return {
            "current_step": "evaluator_skipped",
            "quality_gate_passed": True,
            "awaiting_approval": True,
        }

    prompt = prompts.load("evaluator")
    response = await ctx.router.route(
        "evaluator",
        LLMRequest(
            system=prompt.system,
            messages=[
                Message(
                    role="user",
                    content=prompt.render_user(
                        cover_letter=state.get("cover_letter") or "",
                        tailored_bullets=state.get("tailored_bullets") or [],
                        candidate_profile_json=json.dumps(state.get("candidate_profile", {})),
                        parsed_job_json=json.dumps(state.get("parsed_job", {})),
                    ),
                )
            ],
            model="placeholder",
            temperature=0.0,
            metadata={"node": "evaluator", "workflow_id": state.get("workflow_id", "")},
        ),
    )
    parsed = parse_json(response.text)
    return {
        "current_step": "evaluator",
        "eval_scores": {
            "factuality": float(parsed.get("factuality", 0)),
            "ats_coverage": float(parsed.get("ats_coverage", 0)),
        },
        "quality_gate_passed": bool(parsed.get("overall_pass", False)),
        "awaiting_approval": True,
    }
