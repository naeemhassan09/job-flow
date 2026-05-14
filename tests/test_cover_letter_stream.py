"""Unit tests for the streaming-router fallback + provider stream contract.

The end-to-end SSE path is exercised by the smoke run in CI/curl; here we
just lock in the contract every provider must honour: ``stream_text`` yields
StreamDelta events for token batches and terminates with one LLMResponse.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.llm.router import Router
from app.llm.types import LLMRequest, LLMResponse, StreamDelta


class _StubStreamProvider:
    def __init__(self, name: str, deltas: list[str], fail: bool = False) -> None:
        self.name = name
        self._deltas = deltas
        self._fail = fail
        self.calls = 0

    async def generate(self, request):  # not used here
        raise NotImplementedError

    async def stream_text(self, request: LLMRequest):
        self.calls += 1
        if self._fail:
            raise RuntimeError(f"{self.name} stream init failed")
        for d in self._deltas:
            yield StreamDelta(text=d)
        yield LLMResponse(
            text="".join(self._deltas),
            provider=self.name,
            model=request.model,
            prompt_tokens=10,
            completion_tokens=len("".join(self._deltas).split()),
            total_tokens=10 + len("".join(self._deltas).split()),
            latency_ms=1,
            estimated_cost_eur=Decimal("0.0001"),
        )


# Spec routing table: cover_letter → default anthropic/sonnet, fallback openai/mini.


@pytest.mark.asyncio
async def test_route_stream_yields_deltas_then_final_from_default() -> None:
    anthropic = _StubStreamProvider("anthropic", ["Hello, ", "world!"])
    openai = _StubStreamProvider("openai", ["unused"])
    router = Router({"openai": openai, "anthropic": anthropic})

    events: list = []
    async for ev in router.route_stream(
        "cover_letter",
        LLMRequest(system="s", messages=[], model="placeholder"),
    ):
        events.append(ev)

    deltas = [e for e in events if isinstance(e, StreamDelta)]
    finals = [e for e in events if isinstance(e, LLMResponse)]
    assert [d.text for d in deltas] == ["Hello, ", "world!"]
    assert len(finals) == 1
    assert finals[0].provider == "anthropic"
    assert anthropic.calls == 1
    assert openai.calls == 0


@pytest.mark.asyncio
async def test_route_stream_falls_back_when_default_fails_before_emitting() -> None:
    anthropic = _StubStreamProvider("anthropic", [], fail=True)
    openai = _StubStreamProvider("openai", ["Fallback ", "wins."])
    router = Router({"openai": openai, "anthropic": anthropic})

    deltas: list[str] = []
    final_provider: str | None = None
    async for ev in router.route_stream(
        "cover_letter",
        LLMRequest(system="s", messages=[], model="placeholder"),
    ):
        if isinstance(ev, StreamDelta):
            deltas.append(ev.text)
        elif isinstance(ev, LLMResponse):
            final_provider = ev.provider

    assert deltas == ["Fallback ", "wins."]
    assert final_provider == "openai"
    assert anthropic.calls == 1   # tried default
    assert openai.calls == 1      # used fallback
