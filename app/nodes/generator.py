from __future__ import annotations

import json

from langchain_core.runnables import RunnableConfig

from app.graph.state import JobSearchState
from app.llm import prompts
from app.llm.json_utils import parse_json
from app.llm.types import LLMRequest, Message

from ._common import context_from, stamp_call_context


async def generator(state: JobSearchState, config: RunnableConfig) -> JobSearchState:
    stamp_call_context(state, "generator")
    ctx = context_from(config)

    if state.get("decision") != "apply":
        return {"current_step": "generator_skipped"}

    prompt = prompts.load("generator")
    response = await ctx.router.route(
        "cover_letter",
        LLMRequest(
            system=prompt.system,
            messages=[
                Message(
                    role="user",
                    content=prompt.render_user(
                        parsed_job_json=json.dumps(state.get("parsed_job", {})),
                        candidate_profile_json=json.dumps(state.get("candidate_profile", {})),
                        company_brief=state.get("company_brief") or "",
                        tone=ctx.profile.cover_letter_tone,
                        must_mention=ctx.profile.cover_letter_must_mention,
                        forbid_phrases=ctx.profile.cover_letter_forbid_phrases,
                    ),
                )
            ],
            model="placeholder",
            temperature=0.3,
            metadata={"node": "generator", "workflow_id": state.get("workflow_id", "")},
        ),
    )
    parsed = parse_json(response.text)
    return {
        "current_step": "generator",
        "cover_letter": parsed.get("cover_letter"),
        "tailored_bullets": list(parsed.get("tailored_bullets") or []),
    }
