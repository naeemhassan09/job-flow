from __future__ import annotations

from app import settings_store
from app.config import Settings
from app.profile import UserProfile

from .adzuna import AdzunaScraper
from .base import BaseScraper
from .reed import ReedScraper


async def build_enabled_scrapers(settings: Settings, profile: UserProfile) -> list[BaseScraper]:
    """Return scrapers whose source is enabled in the profile AND has credentials.

    Reads keys via the settings_store (DB-first, env fallback) so UI edits take
    effect without a restart. Sources without credentials are silently skipped
    so the pipeline degrades gracefully.
    """
    scrapers: list[BaseScraper] = []

    adz = profile.sources.get("adzuna")
    if adz and adz.enabled:
        app_id = await settings_store.effective_secret("adzuna_app_id", settings.adzuna_app_id)
        app_key = await settings_store.effective_secret("adzuna_app_key", settings.adzuna_app_key)
        if app_id and app_key:
            scrapers.append(AdzunaScraper(app_id, app_key))

    reed = profile.sources.get("reed")
    if reed and reed.enabled:
        reed_key = await settings_store.effective_secret("reed_api_key", settings.reed_api_key)
        if reed_key:
            scrapers.append(ReedScraper(reed_key))

    return scrapers
