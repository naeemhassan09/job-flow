"""Agentic research loop.

Plan → act → observe → replan → stop. The planner is an LLM call that decides
the next tool call given the running notes; tools are ``web_search`` (Tavily)
and ``fetch_url``. The synthesizer is a final LLM call that turns the
observations into a structured ``CompanyBrief``.

The loop is exposed as an async generator that yields ``ResearchEvent`` objects
so the API layer can stream the agent's thinking to the UI in real time.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

from app.graph.context import WorkflowContext
from app.llm import prompts
from app.llm.json_utils import parse_json
from app.llm.types import LLMRequest, Message
from app.llm.usage import CallContext, set_call_context
from app.observability.log import get_logger

from .tools import (
    SearchHit,
    fetch_to_payload,
    fetch_url,
    search_to_payload,
    web_search,
)

_log = get_logger(__name__)

MAX_ITERATIONS = 6
MAX_TOTAL_NOTES = 14  # cap context size


@dataclass
class Note:
    iteration: int
    kind: Literal["search", "fetch", "plan", "error"]
    summary: str           # what the LLM sees on the next turn
    payload: dict[str, Any] = field(default_factory=dict)  # full content (for trace storage)


@dataclass
class ResearchEvent:
    kind: Literal["plan", "tool_result", "synthesize", "final", "error"]
    data: dict[str, Any]


@dataclass
class CompanyBrief:
    summary: str
    what_they_do: str
    tech_stack_signals: list[str]
    recent_news: list[dict[str, Any]]
    culture_signals: list[dict[str, Any]]
    red_flags: list[dict[str, Any]]
    sources: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "what_they_do": self.what_they_do,
            "tech_stack_signals": self.tech_stack_signals,
            "recent_news": self.recent_news,
            "culture_signals": self.culture_signals,
            "red_flags": self.red_flags,
            "sources": self.sources,
        }


async def run_research(
    *,
    ctx: WorkflowContext,
    company: str,
    role: str,
    workflow_id: str | None = None,
) -> AsyncIterator[ResearchEvent]:
    """Yield events as the agent runs. Final event has the structured brief."""
    workflow_id = workflow_id or str(uuid.uuid4())
    set_call_context(
        CallContext(
            workflow_id=workflow_id,
            node_name="research",
            application_id=None,
            task="research_step",
        )
    )

    plan_prompt = prompts.load("research_plan")
    notes: list[Note] = []
    seen_queries: set[str] = set()
    seen_urls: set[str] = set()

    for iteration in range(1, MAX_ITERATIONS + 1):
        # --- Plan: ask the LLM what to do next -----------------------------
        notes_view = [
            {"kind": n.kind, "summary": n.summary[:600]}
            for n in notes[-MAX_TOTAL_NOTES:][::-1]
        ]
        user_content = plan_prompt.render_user(
            company=company,
            role=role,
            iteration=iteration,
            max_iterations=MAX_ITERATIONS,
            notes_so_far=notes_view,
        )
        try:
            response = await ctx.router.route(
                "research_step",
                LLMRequest(
                    system=plan_prompt.system,
                    messages=[Message(role="user", content=user_content)],
                    model="placeholder",
                    temperature=0.2,
                    max_tokens=300,
                ),
            )
            plan = parse_json(response.text)
        except Exception as e:  # noqa: BLE001
            yield ResearchEvent(kind="error", data={"detail": f"planner failed: {e}"})
            return

        action = str(plan.get("action") or "stop").lower()
        reason = str(plan.get("reason") or "")
        yield ResearchEvent(
            kind="plan",
            data={
                "iteration": iteration,
                "action": action,
                "query": plan.get("query"),
                "url": plan.get("url"),
                "reason": reason,
                "cost_eur": float(response.estimated_cost_eur),
            },
        )

        if action == "stop":
            break

        # --- Act + observe -------------------------------------------------
        if action == "search":
            query = str(plan.get("query") or "").strip()
            if not query or query.lower() in seen_queries:
                notes.append(
                    Note(
                        iteration=iteration,
                        kind="error",
                        summary=f"planner suggested a duplicate or empty query: {query!r}",
                    )
                )
                yield ResearchEvent(
                    kind="error",
                    data={"iteration": iteration, "detail": "duplicate/empty query — moving on"},
                )
                continue
            seen_queries.add(query.lower())
            result = await web_search(query)
            payload = search_to_payload(result)
            summary = _summarise_search(result.query, result.hits, result.error)
            notes.append(
                Note(iteration=iteration, kind="search", summary=summary, payload=payload)
            )
            yield ResearchEvent(
                kind="tool_result",
                data={
                    "iteration": iteration,
                    "tool": "web_search",
                    "query": query,
                    "hits": payload["hits"],
                    "error": result.error,
                },
            )
        elif action == "fetch":
            url = str(plan.get("url") or "").strip()
            if not url or url in seen_urls:
                notes.append(
                    Note(
                        iteration=iteration,
                        kind="error",
                        summary=f"planner suggested a duplicate or empty url: {url!r}",
                    )
                )
                yield ResearchEvent(
                    kind="error",
                    data={"iteration": iteration, "detail": "duplicate/empty url — moving on"},
                )
                continue
            seen_urls.add(url)
            result = await fetch_url(url)
            payload = fetch_to_payload(result)
            summary = _summarise_fetch(result.url, result.title, result.text, result.error)
            notes.append(
                Note(iteration=iteration, kind="fetch", summary=summary, payload=payload)
            )
            yield ResearchEvent(
                kind="tool_result",
                data={
                    "iteration": iteration,
                    "tool": "fetch_url",
                    "url": url,
                    "title": result.title,
                    "status": result.status,
                    "error": result.error,
                    "excerpt": result.text[:600],
                },
            )
        else:
            # Unknown action — log and stop.
            yield ResearchEvent(
                kind="error",
                data={"iteration": iteration, "detail": f"unknown action: {action!r}"},
            )
            break

    # --- Synthesize ----------------------------------------------------------
    syn_prompt = prompts.load("research_synthesize")
    observations = [
        {"iteration": n.iteration, "kind": n.kind, "summary": n.summary[:1200]}
        for n in notes
    ]
    yield ResearchEvent(
        kind="synthesize",
        data={"iterations": len(notes), "starting_brief": True},
    )
    syn_content = syn_prompt.render_user(
        company=company, role=role, observations=observations
    )
    try:
        syn_response = await ctx.router.route(
            "research_step",
            LLMRequest(
                system=syn_prompt.system,
                messages=[Message(role="user", content=syn_content)],
                model="placeholder",
                temperature=0.1,
                max_tokens=1000,
            ),
        )
        raw = parse_json(syn_response.text)
        brief = CompanyBrief(
            summary=str(raw.get("summary", "")),
            what_they_do=str(raw.get("what_they_do", "")),
            tech_stack_signals=[str(x) for x in (raw.get("tech_stack_signals") or [])][:10],
            recent_news=list(raw.get("recent_news") or [])[:5],
            culture_signals=list(raw.get("culture_signals") or [])[:5],
            red_flags=list(raw.get("red_flags") or [])[:3],
            sources=list(raw.get("sources") or []),
        )
    except Exception as e:  # noqa: BLE001
        yield ResearchEvent(kind="error", data={"detail": f"synthesizer failed: {e}"})
        return

    trace = [
        {
            "iteration": n.iteration,
            "kind": n.kind,
            "summary": n.summary[:1200],
            **(
                {"query": n.payload.get("query")}
                if n.kind == "search" and n.payload
                else {}
            ),
            **(
                {"url": n.payload.get("url"), "title": n.payload.get("title")}
                if n.kind == "fetch" and n.payload
                else {}
            ),
        }
        for n in notes
    ]
    yield ResearchEvent(
        kind="final",
        data={
            "brief": brief.to_dict(),
            "trace": trace,
            "iterations": len(notes),
            "synth_cost_eur": float(syn_response.estimated_cost_eur),
        },
    )


def _summarise_search(query: str, hits: list[SearchHit], error: str | None) -> str:
    if error:
        return f"search query={query!r} failed: {error}"
    if not hits:
        return f"search query={query!r} returned 0 hits"
    head = "\n".join(
        f"- {h.title} <{h.url}>: {h.snippet[:180]}" for h in hits[:5]
    )
    return f"search query={query!r} →\n{head}"


def _summarise_fetch(url: str, title: str | None, text: str, error: str | None) -> str:
    if error:
        return f"fetch {url} failed: {error}"
    return f"fetched {title or url} <{url}>:\n{text[:1500]}"
