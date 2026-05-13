from __future__ import annotations

from app.security.pii import redact


def test_redacts_email_phone_ppsn() -> None:
    text = "Email me at jhonattan@example.com or call +353 87 123 4567. PPSN: 1234567TA."
    redacted, findings = redact(text)
    assert "[EMAIL]" in redacted
    assert "[PHONE]" in redacted
    assert "[PPSN]" in redacted
    assert "jhonattan@example.com" not in redacted
    kinds = {f.kind for f in findings}
    assert {"EMAIL", "PHONE", "PPSN"} <= kinds


def test_redacts_candidate_name_case_insensitive() -> None:
    text = "Jhonattan Naeem leads the platform team. JHONATTAN ships fast."
    redacted, _ = redact(text, candidate_names=["Jhonattan", "Jhonattan Naeem"])
    assert "Jhonattan" not in redacted
    assert "[CANDIDATE_NAME]" in redacted


def test_redacts_irish_address() -> None:
    text = "Visit us at 42 O Connell Street."
    redacted, findings = redact(text)
    assert "[ADDRESS]" in redacted
    assert any(f.kind == "ADDRESS" for f in findings)


def test_findings_preserve_original() -> None:
    text = "Contact: jhonattan@cityscapetechnology.com"
    _, findings = redact(text)
    emails = [f for f in findings if f.kind == "EMAIL"]
    assert emails[0].original == "jhonattan@cityscapetechnology.com"
    assert emails[0].placeholder == "[EMAIL]"


def test_idempotent_on_already_redacted_text() -> None:
    text = "Contact: [EMAIL]"
    redacted, findings = redact(text)
    assert redacted == text
    assert findings == []
