from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal

from app.db.models import LLMUsageEvent
from app.db.session import get_sessionmaker
from app.llm.types import LLMResponse
from app.observability.log import get_logger

_log = get_logger(__name__)


@dataclass(frozen=True)
class CallContext:
    """Lightweight per-LLM-call breadcrumb. Set by the workflow before
    dispatching to the provider; read by the usage recorder. Threading via
    contextvars lets nodes set it once without changing every signature.
    """

    workflow_id: str
    node_name: str
    application_id: uuid.UUID | None = None
    step_name: str | None = None
    task: str | None = None


_current: ContextVar[CallContext | None] = ContextVar("careeros_llm_call_context", default=None)


def set_call_context(ctx: CallContext | None) -> None:
    _current.set(ctx)


def get_call_context() -> CallContext | None:
    return _current.get()


async def record_usage(response: LLMResponse, *, ctx: CallContext | None = None) -> None:
    """Persist a single llm_usage_events row. Errors here are logged but do not
    interrupt the workflow — observability must not break user-visible flow.
    """
    ctx = ctx or get_call_context()
    if ctx is None:
        # Some calls happen outside a workflow (e.g. healthchecks). Skip silently.
        return
    try:
        async with get_sessionmaker()() as session:
            session.add(
                LLMUsageEvent(
                    application_id=ctx.application_id,
                    workflow_id=ctx.workflow_id,
                    node_name=ctx.node_name,
                    step_name=ctx.step_name,
                    provider=response.provider,
                    model=response.model,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    cached_tokens=response.cached_tokens,
                    total_tokens=response.total_tokens,
                    estimated_cost_eur=Decimal(response.estimated_cost_eur),
                    latency_ms=response.latency_ms,
                    cache_hit=response.cached_tokens > 0,
                    status="ok",
                )
            )
            await session.commit()
    except Exception as e:  # noqa: BLE001 — observability must not crash workflow
        _log.warning("usage.record_failed", error=str(e))
