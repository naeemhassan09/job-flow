from __future__ import annotations

from dataclasses import dataclass
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
class UserProfile:
    candidate: CandidateProfile
    cv_path: Path
    linkedin_url: str
    indeed_url: str
    cover_letter_tone: str
    cover_letter_must_mention: list[str]
    cover_letter_forbid_phrases: list[str]

    def load_cv_text(self) -> str:
        return self.cv_path.read_text(encoding="utf-8")


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
    )
