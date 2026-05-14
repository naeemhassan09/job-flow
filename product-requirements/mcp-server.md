# MCP Server — Claude Desktop Wiring

CareerOS AI exposes its workflow as five Model Context Protocol (MCP) tools that Claude Desktop can call directly. This means you can sit in a Claude Desktop conversation and ask things like:

> *"Score this JD against my profile, then research the company"*

…and Claude will chain the `score_fit` and `research_company` tool calls, render the structured results inline, and reason over them. No copy-paste.

## Tool catalogue

| Tool | Returns |
|---|---|
| `analyze_jd(raw_jd)` | Structured JD parse: title, company, required_skills, etc. PII-redacts + injection-screens the JD before parsing. |
| `score_fit(raw_jd)` | `fit_score` (0–100), `decision` (apply/maybe/skip), `decision_reason`, `score_breakdown`. Runs preprocess + matcher only. |
| `generate_cover_letter(raw_jd)` | Full pipeline: preprocess + matcher + generator. Returns `cover_letter` + `bullets` when matcher returns `apply`. Below-threshold roles need `?force=true` via the HTTP API. |
| `research_company(company, role?)` | Runs the agentic research loop: plans queries, calls web_search + fetch_url, synthesises a grounded brief. ~6 iterations max, ~€0.002–0.005 per run. |
| `list_applications(status?, limit?)` | Browse the CareerOS inbox: fit_score, decision, application_status, applied_at. Filter by status (`bookmarked`, `applied`, `interview`, …). |

All tools return **structured JSON** as `TextContent`. Claude Desktop parses it and renders the payload — no prose wrapping, no hallucination surface.

## Wire it into Claude Desktop

### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`. Add this block (merge with any existing `mcpServers` entries):

```json
{
  "mcpServers": {
    "careeros": {
      "command": "/Users/YOU/path/to/Job-flow/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/Users/YOU/path/to/Job-flow"
    }
  }
}
```

Quit Claude Desktop fully (⌘Q — not just close) and reopen. The CareerOS tools should appear in the tool picker.

### In-container (alternative)

If you prefer running the MCP server inside the live `careeros-app` container — the upside is a single source of dependency truth, the downside is Claude Desktop now depends on `docker compose exec` succeeding:

```json
{
  "mcpServers": {
    "careeros": {
      "command": "/usr/local/bin/docker",
      "args": [
        "compose",
        "-f", "/Users/YOU/path/to/Job-flow/docker-compose.yml",
        "exec", "-T", "app",
        "python", "-m", "app.mcp_server"
      ]
    }
  }
}
```

Make sure the container is up (`docker compose up -d`) before opening Claude Desktop. The native-venv path is recommended for simplicity.

## What it uses

The MCP server is the same process boundary as the HTTP app's underpinnings — it imports the same `app.graph.runtime.get_context()`, the same `app.llm.router`, the same `app.settings_store`. Model overrides set via the Settings UI, encrypted API keys, and budget caps all apply to MCP calls too.

| Concern | Behaviour |
|---|---|
| API keys | Resolved via `settings_store.effective_secret(name, env)` — DB value if set, else `.env`, else default. |
| Cost tracking | Each LLM call writes a row to `llm_usage_events` with `node_name="mcp.<tool>"` — visible in `/ui/usage.html`. |
| PII redaction | `analyze_jd` / `score_fit` / `generate_cover_letter` redact the JD before any LLM sees it. |
| Injection defence | Same regex scanner runs upfront; quarantined JDs short-circuit with `quarantined=true`. |
| Logs | Stderr only — stdout is the MCP transport and must stay clean. |

## Try it from the command line

```bash
.venv/bin/python -c "
import asyncio, json
async def main():
    proc = await asyncio.create_subprocess_exec(
        '.venv/bin/python', '-m', 'app.mcp_server',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    msgs = [
        {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'cli','version':'0'}}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'list_applications','arguments':{'limit':5}}},
    ]
    for m in msgs:
        proc.stdin.write((json.dumps(m) + '\n').encode())
        await proc.stdin.drain()
    await asyncio.sleep(8)
    proc.stdin.close()
    out, _ = await proc.communicate()
    for line in out.decode().splitlines():
        try:
            j = json.loads(line)
            if j.get('id') == 2:
                print(j['result']['content'][0]['text'])
        except Exception:
            pass

asyncio.run(main())
"
```

You'll get a JSON dump of your inbox.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Tools don't appear in Claude Desktop | Config not reloaded — fully quit Claude (⌘Q), wait 3s, reopen. |
| `list_applications` returns `count: 0` | DB is empty or DB connection failed. Test natively: `.venv/bin/python -m app.mcp_server` should print nothing to stdout and block on stdin. |
| `score_fit` returns `quarantined: true` | The JD tripped the injection classifier. Inspect the raw_jd; if it's legitimately benign, [open an issue against the regex set](.claude/skills/security-redact-check/SKILL.md). |
| Tools fail with `no API key configured` | Set keys via the Settings UI at `/ui/settings.html` or in `.env`. The MCP server reads from the same settings_store as the HTTP app. |

## Non-goals

- No mutation tools — the MCP server is read-only on the lifecycle. Status updates, approvals, and deletes are HTTP-only (see auth model in spec Section 25.4).
- No streaming tools — MCP is request/response. Use the HTTP SSE endpoints for live cover-letter / research streaming in the inbox UI.
- No prompts catalogue — the prompts live in the HTTP app; MCP exposes the *outputs* of the existing nodes, not new prompt surfaces.
