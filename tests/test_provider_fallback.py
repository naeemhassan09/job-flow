from __future__ import annotations

from decimal import Decimal

import pytest

from app.llm.router import Router
from app.llm.types import LLMRequest, LLMResponse, Message


class _FakeProvider:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self._fail = fail
        self.calls = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self._fail:
            raise RuntimeError(f"{self.name} is down")
        return LLMResponse(
            text=f"hello from {self.name}",
            provider=self.name,
            model=request.model,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=12,
            estimated_cost_eur=Decimal("0.0001"),
        )


@pytest.mark.asyncio
async def test_router_uses_default_provider() -> None:
    openai = _FakeProvider("openai")
    anthropic = _FakeProvider("anthropic")
    router = Router({"openai": openai, "anthropic": anthropic})

    response = await router.route(
        "jd_parsing",
        LLMRequest(system="s", messages=[Message(role="user", content="hi")], model="placeholder"),
    )
    assert response.provider == "openai"
    assert response.model == "gpt-4.1-mini"
    assert openai.calls == 1
    assert anthropic.calls == 0


@pytest.mark.asyncio
async def test_router_falls_back_when_default_fails() -> None:
    openai = _FakeProvider("openai", fail=True)
    anthropic = _FakeProvider("anthropic")
    router = Router({"openai": openai, "anthropic": anthropic})

    response = await router.route(
        "jd_parsing",
        LLMRequest(system="s", messages=[Message(role="user", content="hi")], model="placeholder"),
    )
    assert response.provider == "anthropic"
    assert response.model == "claude-haiku-4-5"
    assert openai.calls == 1
    assert anthropic.calls == 1


@pytest.mark.asyncio
async def test_router_cover_letter_prefers_claude() -> None:
    openai = _FakeProvider("openai")
    anthropic = _FakeProvider("anthropic")
    router = Router({"openai": openai, "anthropic": anthropic})

    response = await router.route(
        "cover_letter",
        LLMRequest(system="s", messages=[Message(role="user", content="hi")], model="placeholder"),
    )
    assert response.provider == "anthropic"
    assert response.model == "claude-sonnet-4-6"
