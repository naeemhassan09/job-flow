from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)


@dataclass(frozen=True)
class PromptFile:
    name: str
    version: int
    task: str
    system: str
    user_template: str

    def render_user(self, **vars: Any) -> str:
        return _env.from_string(self.user_template).render(**vars)


_HEADER = re.compile(r"^#\s*(\w+)\s*:\s*(.+)$", re.M)


@lru_cache(maxsize=32)
def load(name: str) -> PromptFile:
    path = PROMPTS_DIR / f"{name}.md"
    raw = path.read_text(encoding="utf-8")

    headers = dict(_HEADER.findall(raw.split("\n\n", 1)[0]))
    version = int(headers.get("version", "1"))
    task = headers.get("task", name)

    body = raw.split("## System", 1)[1] if "## System" in raw else raw
    system_part, _, user_part = body.partition("## User template")
    return PromptFile(
        name=name,
        version=version,
        task=task,
        system=system_part.strip(),
        user_template=user_part.strip(),
    )
