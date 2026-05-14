from __future__ import annotations

import uuid

from langchain_core.runnables import RunnableConfig

from app.graph.context import WorkflowContext
from app.graph.state import JobSearchState
from app.llm.usage import CallContext, set_call_context


def context_from(config: RunnableConfig) -> WorkflowContext:
    """Extracts the WorkflowContext we inject into every LangGraph invocation."""
    configurable = config.get("configurable") if config else None
    if not configurable or "context" not in configurable:
        raise RuntimeError("WorkflowContext missing from RunnableConfig.configurable['context']")
    ctx = configurable["context"]
    if not isinstance(ctx, WorkflowContext):
        raise TypeError(f"expected WorkflowContext, got {type(ctx).__name__}")
    return ctx


def stamp_call_context(state: JobSearchState, node_name: str) -> None:
    """Set the per-call breadcrumb the router reads to write llm_usage_events.

    Call at the top of every node before dispatching to ``ctx.router``. The
    ContextVar is async-safe; LangGraph runs each node in its own asyncio task.
    """
    app_id = state.get("application_id")
    application_id: uuid.UUID | None = None
    if isinstance(app_id, str):
        try:
            application_id = uuid.UUID(app_id)
        except ValueError:
            application_id = None
    elif isinstance(app_id, uuid.UUID):
        application_id = app_id
    set_call_context(
        CallContext(
            workflow_id=str(state.get("workflow_id") or ""),
            node_name=node_name,
            application_id=application_id,
        )
    )
