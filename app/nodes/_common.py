from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from app.graph.context import WorkflowContext


def context_from(config: RunnableConfig) -> WorkflowContext:
    """Extracts the WorkflowContext we inject into every LangGraph invocation."""
    configurable = config.get("configurable") if config else None
    if not configurable or "context" not in configurable:
        raise RuntimeError("WorkflowContext missing from RunnableConfig.configurable['context']")
    ctx = configurable["context"]
    if not isinstance(ctx, WorkflowContext):
        raise TypeError(f"expected WorkflowContext, got {type(ctx).__name__}")
    return ctx
