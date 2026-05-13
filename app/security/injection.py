from __future__ import annotations

import re
from dataclasses import dataclass

# Regex pre-filter for known injection patterns. The runtime classifier wraps this with an
# LLM call (added in week 3), but the regex layer is fast, deterministic, and CI-testable.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_previous", re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)", re.I)),
    ("system_prompt_reveal", re.compile(r"(?:reveal|show|print|leak)\s+(?:the\s+)?system\s*prompt", re.I)),
    ("exfiltrate", re.compile(r"(?:send|post|exfiltrate|upload).*?(?:http|attacker|webhook)", re.I)),
    ("role_override", re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.I)),
    ("disregard_safety", re.compile(r"disregard\s+(?:safety|guidelines|rules)", re.I)),
    ("dan_jailbreak", re.compile(r"\b(?:DAN|do\s+anything\s+now)\b", re.I)),
    ("instruction_injection", re.compile(r"new\s+instructions\s*:", re.I)),
    ("delimiter_break", re.compile(r"</?(?:system|jd|fetched|user|assistant)>", re.I)),
    ("base64_payload", re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2})")),
    ("data_uri", re.compile(r"data:\s*text/(?:plain|html)\s*[;,]", re.I)),
]


@dataclass(frozen=True)
class InjectionScan:
    flags: list[str]
    is_quarantined: bool


def scan(text: str) -> InjectionScan:
    flags = [name for name, pattern in _RULES if pattern.search(text)]
    return InjectionScan(flags=flags, is_quarantined=bool(flags))
