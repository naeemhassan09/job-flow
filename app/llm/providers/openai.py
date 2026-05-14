from __future__ import annotations

import time
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import get_settings
from app.llm.cost import estimate_eur
from app.llm.types import LLMRequest, LLMResponse, StreamDelta


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str) -> None:
        # Fallback to env at construction time; ``generate`` checks for a fresher
        # value in app_settings before each call so a UI edit takes effect
        # without restarting the app.
        self._env_key = api_key
        self._client = AsyncOpenAI(api_key=api_key or "placeholder")
        self._current_key = api_key

    async def _ensure_client(self) -> None:
        try:
            from app.settings_store import effective_secret

            resolved = await effective_secret(
                "openai_api_key", self._env_key or get_settings().openai_api_key
            )
        except Exception:  # noqa: BLE001 — fall back to construction-time key
            return
        if resolved and resolved != self._current_key:
            self._client = AsyncOpenAI(api_key=resolved)
            self._current_key = resolved

    async def generate(self, request: LLMRequest) -> LLMResponse:
        await self._ensure_client()
        started = time.perf_counter()
        completion = await self._client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system},
                *[{"role": m.role, "content": m.content} for m in request.messages],
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
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

    async def stream_text(
        self, request: LLMRequest
    ) -> AsyncIterator[StreamDelta | LLMResponse]:
        await self._ensure_client()
        started = time.perf_counter()
        chunks: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        finish_reason = "stop"

        # stream_options.include_usage gives us real token counts in the final
        # event so cost recording stays accurate without tiktoken on the wire.
        stream = await self._client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system},
                *[{"role": m.role, "content": m.content} for m in request.messages],
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for event in stream:
            if event.usage:
                prompt_tokens = event.usage.prompt_tokens or 0
                completion_tokens = event.usage.completion_tokens or 0
            if event.choices:
                choice = event.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta.content
                if delta:
                    chunks.append(delta)
                    yield StreamDelta(text=delta)

        latency_ms = int((time.perf_counter() - started) * 1000)
        yield LLMResponse(
            text="".join(chunks),
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
            raw_finish_reason=finish_reason,
        )
