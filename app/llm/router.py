from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.llm.types import LLMProvider, LLMRequest, LLMResponse

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
        try:
            provider = self._providers[route.default_provider]
            return await provider.generate(request.model_copy(update={"model": route.default_model}))
        except Exception:
            provider = self._providers[route.fallback_provider]
            return await provider.generate(request.model_copy(update={"model": route.fallback_model}))
