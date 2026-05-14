"""CareerOS AI — MCP stdio server.

Exposes the workflow as tools that Claude Desktop (or any MCP client) can
call. Run via:

    python -m app.mcp_server                        # native, from the repo dir
    docker compose exec -T careeros-app python -m app.mcp_server   # in-container

Wire into Claude Desktop by editing
``~/Library/Application Support/Claude/claude_desktop_config.json``:

    {
      "mcpServers": {
        "careeros": {
          "command": "/abs/path/to/.venv/bin/python",
          "args": ["-m", "app.mcp_server"],
          "cwd": "/abs/path/to/Job-flow"
        }
      }
    }

Tools return structured JSON (per spec Section 25.9) — Claude Desktop renders the
payload and can chain follow-up calls without needing to re-parse prose.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from app.graph.runtime import get_context
from app.mcp import tool_handlers

# MCP uses stdout as its transport — every log line must go to stderr so it
# doesn't corrupt the protocol stream.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("careeros.mcp")

server = Server("careeros-ai")


# ---------------------------------------------------------------------------
# Tool catalogue
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="analyze_jd",
            description=(
                "Parse a job description into structured fields (title, company, "
                "required_skills, etc.). PII-redacts and injection-screens the JD "
                "before the parse. Returns {parsed_job, quarantined, ok, cost_eur}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "raw_jd": {
                        "type": "string",
                        "description": "Full text of the job posting.",
                    },
                },
                "required": ["raw_jd"],
            },
        ),
        types.Tool(
            name="score_fit",
            description=(
                "Score how well the JD matches the configured candidate profile "
                "(see config/profile.yml). Returns {fit_score (0-100), decision "
                "(apply|maybe|skip), decision_reason, score_breakdown, cost_eur}. "
                "Runs preprocess + matcher (no generator)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "raw_jd": {"type": "string", "description": "Full text of the job posting."}
                },
                "required": ["raw_jd"],
            },
        ),
        types.Tool(
            name="generate_cover_letter",
            description=(
                "Full pipeline: preprocess + matcher + generator. Only generates "
                "when the matcher returns 'apply' (fit_score >= 70). Returns "
                "{cover_letter, bullets, fit_score, decision, decision_reason, "
                "cost_eur}. For below-threshold roles use the HTTP API with "
                "?force=true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "raw_jd": {"type": "string", "description": "Full text of the job posting."}
                },
                "required": ["raw_jd"],
            },
        ),
        types.Tool(
            name="research_company",
            description=(
                "Run the agentic research loop against a company name. Plans "
                "queries, calls web_search (Tavily) + fetch_url, synthesises a "
                "grounded brief. Capped at 6 iterations. Returns {brief, trace, "
                "iterations, cost_eur}. Typical cost EUR 0.002-0.005."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name."},
                    "role": {
                        "type": "string",
                        "description": "Role title (helps the planner pick relevant searches).",
                        "default": "",
                    },
                },
                "required": ["company"],
            },
        ),
        types.Tool(
            name="list_applications",
            description=(
                "Browse the CareerOS inbox: discovered + captured jobs with their "
                "fit_score, decision, application_status, applied_at. Sorted by "
                "scraped_at desc. Filter by application_status (e.g. 'applied', "
                "'interview')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": ["string", "null"],
                        "description": (
                            "Application lifecycle filter: bookmarked, applied, "
                            "screening, interview, offer, accepted, rejected, "
                            "ghosted, withdrawn, not_applying. Omit for all."
                        ),
                        "default": None,
                    },
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                },
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def _json_response(payload: dict[str, Any]) -> list[types.TextContent]:
    return [
        types.TextContent(
            type="text",
            text=json.dumps(payload, default=str, indent=2),
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    logger.info("call_tool %s args=%s", name, list(arguments.keys()))
    try:
        if name == "analyze_jd":
            return _json_response(
                await tool_handlers.analyze_jd(get_context(), str(arguments["raw_jd"]))
            )
        if name == "score_fit":
            return _json_response(
                await tool_handlers.score_fit(get_context(), str(arguments["raw_jd"]))
            )
        if name == "generate_cover_letter":
            return _json_response(
                await tool_handlers.generate_cover_letter(
                    get_context(), str(arguments["raw_jd"])
                )
            )
        if name == "research_company":
            return _json_response(
                await tool_handlers.research_company(
                    get_context(),
                    str(arguments["company"]),
                    str(arguments.get("role") or ""),
                )
            )
        if name == "list_applications":
            return _json_response(
                await tool_handlers.list_applications(
                    status=arguments.get("status"),
                    limit=int(arguments.get("limit") or 20),
                )
            )
        return _json_response({"ok": False, "detail": f"unknown tool: {name}"})
    except Exception as exc:  # noqa: BLE001
        logger.exception("call_tool.failed name=%s", name)
        return _json_response({"ok": False, "detail": str(exc)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
