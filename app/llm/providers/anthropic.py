from __future__ import annotations

import time

from anthropic import AsyncAnthropic

from app.llm.cost import estimate_eur
from app.llm.types import LLMRequest, LLMResponse


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        response = await self._client.messages.create(
            model=request.model,
            system=request.system,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            metadata=request.metadata or None,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = response.usage
        prompt_tokens = usage.input_tokens
        completion_tokens = usage.output_tokens
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            provider=self.name,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_eur=estimate_eur(
                request.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached,
            ),
            raw_finish_reason=response.stop_reason or "stop",
        )
