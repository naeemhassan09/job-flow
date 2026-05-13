from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.graph.context import WorkflowContext
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.router import Router
from app.profile import load_profile


@lru_cache(maxsize=1)
def get_context() -> WorkflowContext:
    settings = get_settings()
    return WorkflowContext(
        router=Router(
            {
                "openai": OpenAIProvider(settings.openai_api_key),
                "anthropic": AnthropicProvider(settings.anthropic_api_key),
            }
        ),
        profile=load_profile(),
    )


def runnable_config(workflow_id: str, *, context: WorkflowContext | None = None) -> dict:
    ctx = context or get_context()
    return {
        "configurable": {
            "thread_id": workflow_id,
            "context": ctx,
        }
    }
