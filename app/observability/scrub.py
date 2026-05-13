from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_PPSN_RE = re.compile(r"\b\d{7}[A-Za-z]{1,2}\b")


def scrub_pii(value: Any) -> Any:
    """Recursively scrub email/phone/PPSN patterns from log payloads.

    This is a defence-in-depth layer: the primary boundary is the preprocess node, which
    replaces PII with typed placeholders. Anything reaching the logger should already be
    redacted; this catches accidents.
    """
    if isinstance(value, str):
        s = _EMAIL_RE.sub("[EMAIL]", value)
        s = _PHONE_RE.sub("[PHONE]", s)
        s = _PPSN_RE.sub("[PPSN]", s)
        return s
    if isinstance(value, dict):
        return {k: scrub_pii(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_pii(v) for v in value]
    return value
