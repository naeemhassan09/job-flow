"""Tools the research agent can call.

Each tool returns a small dict the loop can JSON-serialise into the agent's
notes. Tools are pure async functions; the agent decides when to call them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from app import settings_store
from app.config import get_settings
from app.observability.log import get_logger

_log = get_logger(__name__)

# Hard caps so a runaway agent can't burn the budget or get rate-limited.
MAX_FETCH_BYTES = 350_000        # ~350 KB per page
MAX_FETCH_TEXT_CHARS = 12_000    # trim extracted text before showing to the LLM
FETCH_TIMEOUT_S = 12.0
SEARCH_TIMEOUT_S = 15.0


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: list[SearchHit]
    error: str | None = None


@dataclass(frozen=True)
class FetchResult:
    url: str
    title: str | None
    text: str
    status: int
    error: str | None = None


# ---------------------------------------------------------------------------
# web_search via Tavily
# ---------------------------------------------------------------------------


async def web_search(query: str, *, max_results: int = 5) -> SearchResult:
    """Run a web search via Tavily and return top hits.

    Returns SearchResult.error set when the API key is missing or the call
    fails; the agent treats a failed search as an observation, not a crash.
    """
    key = await settings_store.effective_secret("tavily_api_key", get_settings().tavily_api_key)
    if not key:
        return SearchResult(query=query, hits=[], error="no Tavily API key configured")

    payload = {
        "api_key": key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT_S) as c:
            r = await c.post("https://api.tavily.com/search", json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        return SearchResult(query=query, hits=[], error=f"tavily error: {e!s}")

    hits = [
        SearchHit(
            title=str(h.get("title", "")).strip(),
            url=str(h.get("url", "")).strip(),
            snippet=str(h.get("content") or h.get("snippet") or "").strip()[:600],
        )
        for h in (data.get("results") or [])
    ]
    return SearchResult(query=query, hits=hits)


# ---------------------------------------------------------------------------
# fetch_url
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_REMAINING_TAGS_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def _html_to_text(html: str) -> tuple[str | None, str]:
    """Crude HTML→text; good enough for the agent's note-taking. We strip
    script/style entirely, then drop remaining tags, then collapse whitespace.
    """
    title = None
    if m := _TITLE_RE.search(html):
        title = re.sub(r"\s+", " ", m.group(1)).strip() or None
    cleaned = _HTML_TAG_RE.sub(" ", html)
    cleaned = _REMAINING_TAGS_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return title, cleaned


async def fetch_url(url: str) -> FetchResult:
    """Fetch a URL with strict size/time limits and return extracted text.

    HTML-only by content-type. Binary content / oversized responses / non-2xx
    are surfaced as ``error`` so the agent can move on.
    """
    if not url.startswith(("http://", "https://")):
        return FetchResult(url=url, title=None, text="", status=0, error="non-http URL")
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "CareerOS-AI-Research/0.1"})
    except httpx.HTTPError as e:
        return FetchResult(url=url, title=None, text="", status=0, error=str(e))

    if r.status_code >= 400:
        return FetchResult(
            url=url, title=None, text="", status=r.status_code, error=f"HTTP {r.status_code}"
        )
    ctype = r.headers.get("content-type", "").lower()
    if not ("html" in ctype or "text/plain" in ctype):
        return FetchResult(
            url=url,
            title=None,
            text="",
            status=r.status_code,
            error=f"unsupported content-type {ctype}",
        )
    if len(r.content) > MAX_FETCH_BYTES:
        return FetchResult(
            url=url,
            title=None,
            text="",
            status=r.status_code,
            error=f"response too large ({len(r.content)} bytes)",
        )
    title, text = _html_to_text(r.text)
    return FetchResult(
        url=url,
        title=title,
        text=text[:MAX_FETCH_TEXT_CHARS],
        status=r.status_code,
    )


# ---------------------------------------------------------------------------
# Serialisation helpers — used by the agent to feed observations back to LLM
# ---------------------------------------------------------------------------


def search_to_payload(res: SearchResult) -> dict[str, Any]:
    return {
        "query": res.query,
        "error": res.error,
        "hits": [
            {"title": h.title, "url": h.url, "snippet": h.snippet} for h in res.hits
        ],
    }


def fetch_to_payload(res: FetchResult) -> dict[str, Any]:
    return {
        "url": res.url,
        "title": res.title,
        "status": res.status,
        "error": res.error,
        "text": res.text,
    }
