from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

PiiKind = Literal["EMAIL", "PHONE", "ADDRESS", "PPSN", "DOC_NUMBER", "CANDIDATE_NAME"]


@dataclass(frozen=True)
class PiiFinding:
    kind: PiiKind
    original: str
    placeholder: str
    start: int
    end: int


_PATTERNS: list[tuple[PiiKind, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("PHONE", re.compile(r"\+?\d[\d\s().-]{7,}\d")),
    ("PPSN", re.compile(r"\b\d{7}[A-Za-z]{1,2}\b")),
    ("DOC_NUMBER", re.compile(r"\b[A-Z]{2}\d{6,9}\b")),
    (
        "ADDRESS",
        re.compile(
            r"\b\d{1,4}\s+[A-Z][a-zA-Z']*(?:\s+[A-Z][a-zA-Z']*){0,3}\s+"
            r"(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Lane|Ln\.?|Way|Drive|Dr\.?)\b",
        ),
    ),
]


def redact(text: str, *, candidate_names: list[str] | None = None) -> tuple[str, list[PiiFinding]]:
    """Replace PII spans with typed placeholders. Returns (redacted_text, findings).

    Order matters: longer/more-specific patterns first so a phone-like number inside an
    address line is caught by the address rule.
    """
    findings: list[PiiFinding] = []
    redacted = text

    if candidate_names:
        for name in sorted(set(candidate_names), key=len, reverse=True):
            if not name.strip():
                continue
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            redacted, name_findings = _apply(pattern, "CANDIDATE_NAME", redacted)
            findings.extend(name_findings)

    for kind, pattern in _PATTERNS:
        redacted, new = _apply(pattern, kind, redacted)
        findings.extend(new)

    return redacted, findings


def _apply(pattern: re.Pattern[str], kind: PiiKind, text: str) -> tuple[str, list[PiiFinding]]:
    findings: list[PiiFinding] = []
    placeholder = f"[{kind}]"

    def _replace(m: re.Match[str]) -> str:
        findings.append(
            PiiFinding(
                kind=kind,
                original=m.group(0),
                placeholder=placeholder,
                start=m.start(),
                end=m.end(),
            )
        )
        return placeholder

    redacted = pattern.sub(_replace, text)
    return redacted, findings
