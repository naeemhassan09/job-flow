from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import BaseModel

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


class LLMRequest(BaseModel):
    system: str
    messages: list[Message]
    model: str
    max_tokens: int = 1024
    temperature: float = 0.2
    metadata: dict[str, Any] = {}
    stream: bool = False


class LLMResponse(BaseModel):
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0
    total_tokens: int
    latency_ms: int
    estimated_cost_eur: Decimal
    raw_finish_reason: str = "stop"


class StreamDelta(BaseModel):
    """One token-batch yielded by a streaming LLM call."""

    text: str


class LLMProvider(Protocol):
    name: str

    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    async def stream_text(self, request: LLMRequest):  # AsyncIterator
        """Yield StreamDelta(text=...) for each token batch, then finish with a
        single LLMResponse carrying real usage stats. The router awaits the
        final yield to record llm_usage_events."""
        ...
        yield StreamDelta(text="")  # pragma: no cover — Protocol contract only
