from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.llm.types import LLMProvider, LLMRequest, LLMResponse
from app.llm.usage import CallContext, get_call_context, record_usage

Task = Literal[
    "jd_parsing",
    "cv_profile_compress",
    "research_step",
    "matcher",
    "cover_letter",
    "evaluator",
]


@dataclass(frozen=True)
class TaskRoute:
    default_provider: str
    default_model: str
    fallback_provider: str
    fallback_model: str


# Spec §7.2 routing table.
ROUTES: dict[Task, TaskRoute] = {
    "jd_parsing": TaskRoute("openai", "gpt-4.1-mini", "anthropic", "claude-haiku-4-5"),
    "cv_profile_compress": TaskRoute("anthropic", "claude-sonnet-4-6", "openai", "gpt-4.1-mini"),
    "research_step": TaskRoute("openai", "gpt-4.1-mini", "anthropic", "claude-haiku-4-5"),
    "matcher": TaskRoute("openai", "gpt-4.1-mini", "anthropic", "claude-haiku-4-5"),
    "cover_letter": TaskRoute("anthropic", "claude-sonnet-4-6", "openai", "gpt-4.1-mini"),
    "evaluator": TaskRoute("openai", "gpt-4.1-mini", "anthropic", "claude-haiku-4-5"),
}


class Router:
    """Cost-aware router with automatic fallback on provider error.

    The router is the single seam for failure-injection tests (spec §7.2): swap one
    provider's ``generate`` to raise and assert the workflow completes via the fallback.
    """

    def __init__(self, providers: dict[str, LLMProvider]) -> None:
        self._providers = providers

    async def route(self, task: Task, request: LLMRequest | None = None, **kwargs: object) -> LLMResponse:
        route = ROUTES[task]
        if request is None:
            request = LLMRequest(model=route.default_model, **kwargs)  # type: ignore[arg-type]
        ctx = _ctx_for_task(task)
        try:
            provider = self._providers[route.default_provider]
            response = await provider.generate(
                request.model_copy(update={"model": route.default_model})
            )
        except Exception:
            provider = self._providers[route.fallback_provider]
            response = await provider.generate(
                request.model_copy(update={"model": route.fallback_model})
            )
        await record_usage(response, ctx=ctx)
        return response


def _ctx_for_task(task: Task) -> CallContext | None:
    """Refine the current CallContext with the routed task name. The node sets
    workflow_id + node_name on entry; this stamps the task so the usage row
    distinguishes 'matcher' from 'evaluator' even when both share a node."""
    base = get_call_context()
    if base is None:
        return None
    return CallContext(
        workflow_id=base.workflow_id,
        node_name=base.node_name,
        application_id=base.application_id,
        step_name=base.step_name,
        task=task,
    )
