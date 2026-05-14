from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "dev", "prod", "test"] = "local"
    app_log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://careeros:careeros@localhost:5432/careeros"

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    langsmith_api_key: str = ""
    langsmith_project: str = "careeros-dev"
    langsmith_tracing: bool = False

    monthly_budget_eur: Decimal = Field(default=Decimal("15.00"))
    per_workflow_budget_eur: Decimal = Field(default=Decimal("0.50"))

    pii_encryption_key: str = ""

    extension_jwt_secret: str = "change-me"
    extension_jwt_ttl_seconds: int = 86400

    # Chrome extension bearer token. Stored in chrome.storage.local via the popup
    # and sent on every POST to /api/captures. Empty means the endpoint is open
    # locally (useful for dev); set a long random value in real deployments.
    extension_api_token: str = ""

    # CORS origins allowed by the API. The MV3 extension's origin is its
    # chrome-extension://<ID> URL; add the actual ID after first load.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Job-discovery API credentials (optional — if unset, the scraper is disabled).
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    reed_api_key: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
