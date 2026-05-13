from __future__ import annotations

from app.config import Settings
from app.profile import UserProfile

from .adzuna import AdzunaScraper
from .base import BaseScraper
from .reed import ReedScraper


def build_enabled_scrapers(settings: Settings, profile: UserProfile) -> list[BaseScraper]:
    """Return scrapers whose source is enabled in the profile AND has credentials.

    Sources without credentials are silently skipped (rather than failing) so the
    pipeline degrades gracefully — e.g. add a Reed key later without touching code.
    """
    scrapers: list[BaseScraper] = []

    adz = profile.sources.get("adzuna")
    if adz and adz.enabled and settings.adzuna_app_id and settings.adzuna_app_key:
        scrapers.append(AdzunaScraper(settings.adzuna_app_id, settings.adzuna_app_key))

    reed = profile.sources.get("reed")
    if reed and reed.enabled and settings.reed_api_key:
        scrapers.append(ReedScraper(settings.reed_api_key))

    return scrapers
