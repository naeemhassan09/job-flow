"""Tests for the agentic research loop.

The end-to-end run is exercised in CI/curl against the live container.
Here we lock in: tools are exception-tolerant, the agent loop honours
the iteration cap, and the dedupe sets work.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.research import agent as agent_mod
from app.research.tools import FetchResult, SearchHit, SearchResult, fetch_to_payload, search_to_payload


def test_search_payload_round_trip() -> None:
    res = SearchResult(
        query="acme corp",
        hits=[SearchHit(title="Acme", url="https://acme.example", snippet="They make things.")],
    )
    p = search_to_payload(res)
    assert p["query"] == "acme corp"
    assert p["hits"][0]["url"] == "https://acme.example"
    assert p["error"] is None


def test_fetch_payload_includes_error_when_present() -> None:
    res = FetchResult(url="https://x.example", title=None, text="", status=0, error="boom")
    p = fetch_to_payload(res)
    assert p["error"] == "boom"
    assert p["text"] == ""


@pytest.mark.asyncio
async def test_fetch_url_rejects_non_http() -> None:
    from app.research.tools import fetch_url

    out = await fetch_url("ftp://something.example")
    assert out.error == "non-http URL"
    assert out.status == 0


def test_html_to_text_strips_scripts_and_collapses_whitespace() -> None:
    from app.research.tools import _html_to_text

    html = """
    <html><head><title>  Hello World  </title></head>
    <body><script>evil()</script><p>Hello   there\nfriend.</p><style>.x{}</style></body></html>
    """
    title, text = _html_to_text(html)
    assert title == "Hello World"
    assert "evil()" not in text
    assert "Hello there friend." in text


@pytest.mark.asyncio
async def test_agent_stops_at_max_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the planner keeps choosing 'search' forever, the loop must still
    terminate cleanly via MAX_ITERATIONS and a final synthesizer event."""

    # Stub the planner to always say 'search' with a unique query, and the
    # synthesizer to return a tiny valid brief.
    class FakeRouter:
        def __init__(self):
            self.plan_calls = 0
            self.synth_calls = 0
            self._providers = {}

        @property
        def providers(self):
            return self._providers

        async def route(self, task, request=None, **kwargs):
            from app.llm.types import LLMResponse

            text = request.messages[0].content if request else ""
            self.plan_calls += 1
            # planner prompt mentions 'Decide the next action'; synthesizer asks for the brief
            if "structured brief" in (request.system or "") if request else False:
                self.synth_calls += 1
                return LLMResponse(
                    text='{"summary":"s","what_they_do":"w","tech_stack_signals":[],"recent_news":[],"culture_signals":[],"red_flags":[],"sources":[]}',
                    provider="stub",
                    model="stub",
                    prompt_tokens=1,
                    completion_tokens=1,
                    total_tokens=2,
                    latency_ms=1,
                    estimated_cost_eur=Decimal("0.0001"),
                )
            return LLMResponse(
                text=(
                    '{"action":"search","query":"q-' + str(self.plan_calls) + '","reason":"keep searching"}'
                ),
                provider="stub",
                model="stub",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                latency_ms=1,
                estimated_cost_eur=Decimal("0.0001"),
            )

    async def stub_search(query, *, max_results=5):
        return SearchResult(query=query, hits=[])

    class StubCtx:
        def __init__(self):
            self.router = FakeRouter()

    monkeypatch.setattr(agent_mod, "web_search", stub_search)

    events = []
    async for ev in agent_mod.run_research(ctx=StubCtx(), company="Acme", role="Engineer"):
        events.append(ev)

    plan_events = [e for e in events if e.kind == "plan"]
    final_events = [e for e in events if e.kind == "final"]
    # The loop must hit MAX_ITERATIONS and still produce a final brief.
    assert len(plan_events) == agent_mod.MAX_ITERATIONS
    assert len(final_events) == 1
    assert "summary" in final_events[0].data["brief"]


@pytest.mark.asyncio
async def test_agent_dedupes_repeated_searches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Planner that suggests the same query twice should be redirected by
    the dedupe set; we expect an 'error' event for the duplicate, not a real
    tool call."""

    plan_count = {"i": 0}

    class FakeRouter:
        def __init__(self):
            self._providers = {}

        @property
        def providers(self):
            return self._providers

        async def route(self, task, request=None, **kwargs):
            from app.llm.types import LLMResponse

            plan_count["i"] += 1
            if "structured brief" in (request.system or "") if request else False:
                return LLMResponse(
                    text='{"summary":"s","what_they_do":"","tech_stack_signals":[],"recent_news":[],"culture_signals":[],"red_flags":[],"sources":[]}',
                    provider="stub", model="stub",
                    prompt_tokens=1, completion_tokens=1, total_tokens=2,
                    latency_ms=1, estimated_cost_eur=Decimal("0.0001"),
                )
            if plan_count["i"] == 1:
                return LLMResponse(
                    text='{"action":"search","query":"dup-query","reason":"first"}',
                    provider="stub", model="stub",
                    prompt_tokens=1, completion_tokens=1, total_tokens=2,
                    latency_ms=1, estimated_cost_eur=Decimal("0.0001"),
                )
            if plan_count["i"] == 2:
                return LLMResponse(
                    text='{"action":"search","query":"dup-query","reason":"repeat"}',
                    provider="stub", model="stub",
                    prompt_tokens=1, completion_tokens=1, total_tokens=2,
                    latency_ms=1, estimated_cost_eur=Decimal("0.0001"),
                )
            return LLMResponse(
                text='{"action":"stop","reason":"done"}',
                provider="stub", model="stub",
                prompt_tokens=1, completion_tokens=1, total_tokens=2,
                latency_ms=1, estimated_cost_eur=Decimal("0.0001"),
            )

    async def stub_search(query, *, max_results=5):
        return SearchResult(query=query, hits=[SearchHit(title="x", url="https://x", snippet="")])

    class StubCtx:
        def __init__(self):
            self.router = FakeRouter()

    monkeypatch.setattr(agent_mod, "web_search", stub_search)

    events = []
    async for ev in agent_mod.run_research(ctx=StubCtx(), company="Acme", role="Engineer"):
        events.append(ev)

    errors = [e for e in events if e.kind == "error"]
    tool_results = [e for e in events if e.kind == "tool_result"]
    # First search ran, second was dedupe-rejected with an error event, third planning was 'stop'.
    assert len(tool_results) == 1
    assert any("duplicate" in (e.data.get("detail") or "") for e in errors)
