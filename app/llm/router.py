from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.llm.types import LLMProvider, LLMRequest, LLMResponse, StreamDelta
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

    @property
    def providers(self) -> dict[str, LLMProvider]:
        return self._providers

    async def route_stream(self, task: Task, request: LLMRequest):
        """Stream a single task. Yields StreamDelta(text=...) for each token
        batch, then a terminal LLMResponse.

        Fallback: if the default provider raises BEFORE emitting any deltas
        (e.g. auth failure surfaces during stream initialisation), we silently
        retry on the fallback provider. Once any delta has been yielded we
        can't unwind cleanly, so an error mid-stream propagates to the caller
        and the UI surfaces the failure.
        """
        default_provider, default_model, fallback_provider, fallback_model = await _resolve_route(task)
        if request is None:
            request = LLMRequest(model=default_model, system="", messages=[])
        ctx = _ctx_for_task(task)

        emitted_any = False
        final: LLMResponse | None = None
        try:
            provider = self._providers[default_provider]
            async for event in provider.stream_text(
                request.model_copy(update={"model": default_model})
            ):
                if isinstance(event, LLMResponse):
                    final = event
                    break
                emitted_any = True
                yield event
        except Exception:
            if emitted_any:
                raise  # mid-stream, can't unwind
            provider = self._providers[fallback_provider]
            async for event in provider.stream_text(
                request.model_copy(update={"model": fallback_model})
            ):
                if isinstance(event, LLMResponse):
                    final = event
                    break
                yield event

        if final is not None:
            await record_usage(final, ctx=ctx)
            yield final

    async def route(self, task: Task, request: LLMRequest | None = None, **kwargs: object) -> LLMResponse:
        default_provider, default_model, fallback_provider, fallback_model = await _resolve_route(task)
        if request is None:
            request = LLMRequest(model=default_model, **kwargs)  # type: ignore[arg-type]
        ctx = _ctx_for_task(task)
        try:
            provider = self._providers[default_provider]
            response = await provider.generate(
                request.model_copy(update={"model": default_model})
            )
        except Exception:
            provider = self._providers[fallback_provider]
            response = await provider.generate(
                request.model_copy(update={"model": fallback_model})
            )
        await record_usage(response, ctx=ctx)
        return response


async def _resolve_route(task: Task) -> tuple[str, str, str, str]:
    """Resolve effective (provider, model) for default + fallback.

    Checks app_settings for model.<task>.<default|fallback> overrides (set via
    the Settings UI). Falls back to the spec §7.2 routing table baked into
    ROUTES. If the settings DB is unreachable (e.g. in unit tests), the spec
    defaults are returned silently — overrides are a runtime convenience, not
    load-bearing.
    """
    base = ROUTES[task]
    default_provider, default_model = base.default_provider, base.default_model
    fallback_provider, fallback_model = base.fallback_provider, base.fallback_model
    try:
        from app.settings_store import get as _get_setting

        if override := await _get_setting(f"model.{task}.default"):
            if "/" in override:
                default_provider, default_model = override.split("/", 1)
        if override := await _get_setting(f"model.{task}.fallback"):
            if "/" in override:
                fallback_provider, fallback_model = override.split("/", 1)
    except Exception:  # noqa: BLE001 — overrides degrade gracefully
        pass
    return default_provider, default_model, fallback_provider, fallback_model


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
