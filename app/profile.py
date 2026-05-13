from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class CandidateProfile:
    display_name: str
    email: str
    phone: str
    full_names: list[str]
    location: str
    work_authorisation: str


@dataclass(frozen=True)
class TargetTitles:
    primary: list[str]
    secondary: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[str]:
        return self.primary + self.secondary


@dataclass(frozen=True)
class Keywords:
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SearchLocation:
    name: str
    country: str           # ISO-2, e.g. "ie", "gb"
    remote_only: bool = False


@dataclass(frozen=True)
class SourceConfig:
    enabled: bool = True
    results_per_page: int = 50
    max_pages: int = 1
    max_age_days: int = 14


@dataclass(frozen=True)
class UserProfile:
    candidate: CandidateProfile
    cv_path: Path
    linkedin_url: str
    indeed_url: str
    cover_letter_tone: str
    cover_letter_must_mention: list[str]
    cover_letter_forbid_phrases: list[str]
    target_titles: TargetTitles
    keywords: Keywords
    red_flags: list[str]
    locations: list[SearchLocation]
    sources: dict[str, SourceConfig]

    def load_cv_text(self) -> str:
        return self.cv_path.read_text(encoding="utf-8")

    def has_red_flag(self, text: str) -> bool:
        lowered = text.lower()
        return any(flag.lower() in lowered for flag in self.red_flags)


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


@lru_cache(maxsize=4)
def load_profile(path: str | None = None) -> UserProfile:
    cfg_path = _resolve(path or "config/profile.yml")
    if not cfg_path.exists():
        cfg_path = _resolve("config/profile.example.yml")
    raw: dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cand = raw["candidate"]
    cl = raw.get("cover_letter", {})
    profiles = raw.get("profiles", {})

    titles_raw = raw.get("target_titles") or {}
    kw_raw = raw.get("keywords") or {}
    locs_raw = raw.get("locations") or []
    sources_raw = raw.get("sources") or {}

    return UserProfile(
        candidate=CandidateProfile(
            display_name=cand["display_name"],
            email=cand["email"],
            phone=cand.get("phone", ""),
            full_names=list(cand.get("full_names") or [cand["display_name"]]),
            location=cand.get("location", ""),
            work_authorisation=cand.get("work_authorisation", ""),
        ),
        cv_path=_resolve(raw["cv_path"]),
        linkedin_url=profiles.get("linkedin_url", ""),
        indeed_url=profiles.get("indeed_url", ""),
        cover_letter_tone=cl.get("tone", ""),
        cover_letter_must_mention=list(cl.get("must_mention") or []),
        cover_letter_forbid_phrases=list(cl.get("forbid_phrases") or []),
        target_titles=TargetTitles(
            primary=list(titles_raw.get("primary") or []),
            secondary=list(titles_raw.get("secondary") or []),
        ),
        keywords=Keywords(
            must_have=list(kw_raw.get("must_have") or []),
            nice_to_have=list(kw_raw.get("nice_to_have") or []),
        ),
        red_flags=list(raw.get("red_flags") or []),
        locations=[
            SearchLocation(
                name=loc["name"],
                country=loc.get("country", "ie"),
                remote_only=bool(loc.get("remote_only", False)),
            )
            for loc in locs_raw
        ],
        sources={
            name: SourceConfig(
                enabled=bool(cfg.get("enabled", True)),
                results_per_page=int(cfg.get("results_per_page", 50)),
                max_pages=int(cfg.get("max_pages", 1)),
                max_age_days=int(cfg.get("max_age_days", 14)),
            )
            for name, cfg in sources_raw.items()
        },
    )
