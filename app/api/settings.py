"""Settings API.

GET  /api/settings              → full settings tree, secrets masked
PUT  /api/settings/{key}        → upsert a single setting
POST /api/settings/test/{name}  → ping a provider with current creds

All routes require a session cookie (default-deny middleware in main.py).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import auth, settings_store
from app.config import get_settings
from app.llm.router import ROUTES

router = APIRouter(prefix="/api/settings", tags=["settings"])

# ---------------------------------------------------------------------------
# Setting registry — defines what the UI can edit and how each value is
# displayed. Keys map 1:1 to rows in app_settings.
# ---------------------------------------------------------------------------

API_KEY_FIELDS: list[dict[str, str]] = [
    {"key": "openai_api_key", "label": "OpenAI API key", "env": "OPENAI_API_KEY", "placeholder": "sk-..."},
    {"key": "anthropic_api_key", "label": "Anthropic API key", "env": "ANTHROPIC_API_KEY", "placeholder": "sk-ant-..."},
    {"key": "tavily_api_key", "label": "Tavily API key (research loop)", "env": "TAVILY_API_KEY", "placeholder": "tvly-..."},
    {"key": "adzuna_app_id", "label": "Adzuna app ID", "env": "ADZUNA_APP_ID", "placeholder": ""},
    {"key": "adzuna_app_key", "label": "Adzuna app key", "env": "ADZUNA_APP_KEY", "placeholder": ""},
    {"key": "reed_api_key", "label": "Reed API key", "env": "REED_API_KEY", "placeholder": ""},
    {"key": "extension_api_token", "label": "Chrome extension bearer token", "env": "EXTENSION_API_TOKEN", "placeholder": ""},
    {"key": "langsmith_api_key", "label": "LangSmith API key (optional)", "env": "LANGSMITH_API_KEY", "placeholder": "lsv2_..."},
]

BUDGET_FIELDS: list[dict[str, str]] = [
    {"key": "monthly_budget_eur", "label": "Monthly budget (EUR)", "env": "MONTHLY_BUDGET_EUR", "placeholder": "15.00"},
    {"key": "per_workflow_budget_eur", "label": "Per-workflow soft cap (EUR)", "env": "PER_WORKFLOW_BUDGET_EUR", "placeholder": "0.50"},
]

# Models the UI offers per task. Keep aligned with app/llm/cost.py PRICING.
MODEL_CHOICES: list[dict[str, str]] = [
    {"provider": "openai", "model": "gpt-4.1-mini"},
    {"provider": "openai", "model": "gpt-4.1"},
    {"provider": "anthropic", "model": "claude-haiku-4-5"},
    {"provider": "anthropic", "model": "claude-sonnet-4-6"},
]


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "•" * len(value)
    return f"{value[:3]}{'•' * 6}{value[-3:]}"


def _is_set_marker(db_value: str | None, env_value: str) -> dict[str, Any]:
    """Returns the public-safe representation of a secret-shaped setting."""
    if db_value:
        return {"set": True, "source": "db", "preview": _mask(db_value)}
    if env_value:
        return {"set": True, "source": "env", "preview": _mask(env_value)}
    return {"set": False, "source": None, "preview": ""}


@router.get("")
async def get_settings_tree(
    _user: auth.SessionUser = Depends(auth.require_session),
) -> dict[str, Any]:
    env = get_settings()

    api_keys: list[dict[str, Any]] = []
    for f in API_KEY_FIELDS:
        db_value = await settings_store.get(f["key"])
        env_value = str(getattr(env, f["env"].lower(), "") or "")
        api_keys.append(
            {
                "key": f["key"],
                "label": f["label"],
                "env": f["env"],
                "placeholder": f["placeholder"],
                **_is_set_marker(db_value, env_value),
            }
        )

    budgets: list[dict[str, Any]] = []
    for f in BUDGET_FIELDS:
        db_value = await settings_store.get(f["key"])
        env_value = str(getattr(env, f["env"].lower(), "") or "")
        budgets.append(
            {
                "key": f["key"],
                "label": f["label"],
                "env": f["env"],
                "placeholder": f["placeholder"],
                "value": db_value or env_value,
                "source": "db" if db_value else ("env" if env_value else None),
            }
        )

    models: dict[str, Any] = {"tasks": [], "choices": MODEL_CHOICES}
    for task, route in ROUTES.items():
        override_default = await settings_store.get(f"model.{task}.default")
        override_fallback = await settings_store.get(f"model.{task}.fallback")
        models["tasks"].append(
            {
                "task": task,
                "default": {
                    "value": override_default
                    or f"{route.default_provider}/{route.default_model}",
                    "is_override": bool(override_default),
                    "spec_default": f"{route.default_provider}/{route.default_model}",
                },
                "fallback": {
                    "value": override_fallback
                    or f"{route.fallback_provider}/{route.fallback_model}",
                    "is_override": bool(override_fallback),
                    "spec_default": f"{route.fallback_provider}/{route.fallback_model}",
                },
            }
        )

    return {"api_keys": api_keys, "budgets": budgets, "models": models}


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------

_ALLOWED_BARE_KEYS = {f["key"] for f in API_KEY_FIELDS} | {f["key"] for f in BUDGET_FIELDS}
_ALLOWED_TASKS = set(ROUTES.keys())
_ALLOWED_MODEL_PROVIDERS = {c["provider"] for c in MODEL_CHOICES}


class PutRequest(BaseModel):
    value: str = Field(default="", description="Plaintext value (empty deletes the setting)")
    is_secret: bool = True


def _validate_key(key: str) -> None:
    if key in _ALLOWED_BARE_KEYS:
        return
    # model.<task>.<default|fallback>
    parts = key.split(".")
    if (
        len(parts) == 3
        and parts[0] == "model"
        and parts[1] in _ALLOWED_TASKS
        and parts[2] in {"default", "fallback"}
    ):
        return
    raise HTTPException(status_code=400, detail=f"setting key not allowed: {key}")


def _validate_value(key: str, value: str) -> None:
    if value == "":
        return
    if key.startswith("model."):
        if "/" not in value:
            raise HTTPException(
                status_code=400, detail="model value must be 'provider/model'"
            )
        provider, model = value.split("/", 1)
        if provider not in _ALLOWED_MODEL_PROVIDERS:
            raise HTTPException(status_code=400, detail=f"unknown provider: {provider}")
        if not any(c["provider"] == provider and c["model"] == model for c in MODEL_CHOICES):
            raise HTTPException(status_code=400, detail=f"unknown model: {value}")
    if key.endswith("_eur"):
        try:
            float(value)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="budget must be numeric") from e


@router.put("/{key:path}")
async def put_setting(
    key: str,
    req: PutRequest,
    _user: auth.SessionUser = Depends(auth.require_session),
) -> dict[str, Any]:
    _validate_key(key)
    _validate_value(key, req.value)
    await settings_store.put(key, req.value, is_secret=req.is_secret)
    return {"key": key, "stored": bool(req.value), "is_secret": req.is_secret}


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post("/test/{name}")
async def test_provider(
    name: str,
    _user: auth.SessionUser = Depends(auth.require_session),
) -> dict[str, Any]:
    if name == "openai":
        return await _test_openai()
    if name == "anthropic":
        return await _test_anthropic()
    if name == "adzuna":
        return await _test_adzuna()
    if name == "reed":
        return await _test_reed()
    if name == "tavily":
        return await _test_tavily()
    raise HTTPException(status_code=400, detail=f"unknown provider: {name}")


async def _resolved(env_attr: str, db_key: str) -> str:
    env_value = getattr(get_settings(), env_attr, "") or ""
    return await settings_store.effective_secret(db_key, env_value)


async def _test_openai() -> dict[str, Any]:
    key = await _resolved("openai_api_key", "openai_api_key")
    if not key:
        return {"ok": False, "detail": "no API key configured"}
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        return {"ok": r.status_code == 200, "status": r.status_code, "detail": r.reason_phrase}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}


async def _test_anthropic() -> dict[str, Any]:
    key = await _resolved("anthropic_api_key", "anthropic_api_key")
    if not key:
        return {"ok": False, "detail": "no API key configured"}
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
        # 200 OK on success; 401 / 403 on bad key. We accept anything <500 as
        # "auth path reachable" since the user might lack quota.
        return {"ok": r.status_code < 500, "status": r.status_code, "detail": r.reason_phrase}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}


async def _test_adzuna() -> dict[str, Any]:
    app_id = await _resolved("adzuna_app_id", "adzuna_app_id")
    app_key = await _resolved("adzuna_app_key", "adzuna_app_key")
    if not app_id or not app_key:
        return {"ok": False, "detail": "missing app_id or app_key"}
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                "https://api.adzuna.com/v1/api/jobs/ie/categories",
                params={"app_id": app_id, "app_key": app_key},
            )
        return {"ok": r.status_code == 200, "status": r.status_code, "detail": r.reason_phrase}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}


async def _test_reed() -> dict[str, Any]:
    import base64

    key = await _resolved("reed_api_key", "reed_api_key")
    if not key:
        return {"ok": False, "detail": "no API key configured"}
    import httpx

    try:
        auth_b64 = base64.b64encode(f"{key}:".encode()).decode()
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                "https://www.reed.co.uk/api/1.0/search",
                params={"resultsToTake": 1},
                headers={"Authorization": f"Basic {auth_b64}"},
            )
        return {"ok": r.status_code == 200, "status": r.status_code, "detail": r.reason_phrase}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}


async def _test_tavily() -> dict[str, Any]:
    key = await _resolved("tavily_api_key", "tavily_api_key")
    if not key:
        return {"ok": False, "detail": "no API key configured"}
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": "ping", "max_results": 1},
            )
        return {"ok": r.status_code == 200, "status": r.status_code, "detail": r.reason_phrase}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}
