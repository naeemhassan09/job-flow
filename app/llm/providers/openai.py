from __future__ import annotations

import time

from openai import AsyncOpenAI

from app.llm.cost import estimate_eur
from app.llm.types import LLMRequest, LLMResponse


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        completion = await self._client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system},
                *[{"role": m.role, "content": m.content} for m in request.messages],
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            metadata=request.metadata or None,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = completion.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        text = completion.choices[0].message.content or ""
        return LLMResponse(
            text=text,
            provider=self.name,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_eur=estimate_eur(
                request.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            raw_finish_reason=completion.choices[0].finish_reason or "stop",
        )
