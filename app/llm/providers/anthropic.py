from __future__ import annotations

import time
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.config import get_settings
from app.llm.cost import estimate_eur
from app.llm.types import LLMRequest, LLMResponse, StreamDelta


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._env_key = api_key
        self._client = AsyncAnthropic(api_key=api_key or "placeholder")
        self._current_key = api_key

    async def _ensure_client(self) -> None:
        try:
            from app.settings_store import effective_secret

            resolved = await effective_secret(
                "anthropic_api_key", self._env_key or get_settings().anthropic_api_key
            )
        except Exception:  # noqa: BLE001 — fall back to construction-time key
            return
        if resolved and resolved != self._current_key:
            self._client = AsyncAnthropic(api_key=resolved)
            self._current_key = resolved

    async def generate(self, request: LLMRequest) -> LLMResponse:
        await self._ensure_client()
        started = time.perf_counter()
        response = await self._client.messages.create(
            model=request.model,
            system=request.system,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
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

    async def stream_text(
        self, request: LLMRequest
    ) -> AsyncIterator[StreamDelta | LLMResponse]:
        await self._ensure_client()
        started = time.perf_counter()
        chunks: list[str] = []

        async with self._client.messages.stream(
            model=request.model,
            system=request.system,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    chunks.append(text)
                    yield StreamDelta(text=text)
            final = await stream.get_final_message()

        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = final.usage
        prompt_tokens = usage.input_tokens
        completion_tokens = usage.output_tokens
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        yield LLMResponse(
            text="".join(chunks),
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
            raw_finish_reason=final.stop_reason or "stop",
        )
