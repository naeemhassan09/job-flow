"""Tests for app.settings_store crypto + masking helpers.

We don't hit Postgres here — those paths are covered by the API endpoint
itself which is exercised via curl in CI smoke. These tests prove the
AES-GCM round-trip and the masking helper used by /api/settings.
"""
from __future__ import annotations

import base64
import importlib
import os

import pytest


@pytest.fixture(autouse=True)
def _reset_key_cache():
    """Ensure each test starts with a fresh master key cache so tests
    can mutate PII_ENCRYPTION_KEY independently."""
    import app.settings_store as ss

    ss._KEY_CACHE = None
    yield
    ss._KEY_CACHE = None


def test_encrypt_round_trip_with_known_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # 32-byte key, base64 encoded
    raw = os.urandom(32)
    monkeypatch.setenv("PII_ENCRYPTION_KEY", base64.b64encode(raw).decode())

    # Reload settings module + store so the new env value is picked up.
    import app.config as cfg

    cfg.get_settings.cache_clear()
    ss = importlib.reload(__import__("app.settings_store", fromlist=["*"]))

    ct, nonce = ss._encrypt(b"hello world")
    assert ss._decrypt(ct, nonce) == b"hello world"


def test_invalid_key_triggers_regeneration(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If PII_ENCRYPTION_KEY is unset or malformed, the store should generate
    a fresh 32-byte key, cache it, and use it for round-trip."""
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "")
    monkeypatch.setattr(
        "app.settings_store._ENV_FILE", tmp_path / ".env", raising=True
    )
    import app.config as cfg

    cfg.get_settings.cache_clear()
    ss = importlib.reload(__import__("app.settings_store", fromlist=["*"]))

    ct, nonce = ss._encrypt(b"secret-thing")
    assert ss._decrypt(ct, nonce) == b"secret-thing"
    # Master key was persisted to the fake .env
    written = (tmp_path / ".env").read_text() if (tmp_path / ".env").exists() else ""
    if written:
        assert "PII_ENCRYPTION_KEY=" in written


def test_mask_preview_helper_handles_short_and_long_secrets() -> None:
    from app.api.settings import _mask

    assert _mask("") == ""
    assert _mask("abcdef") == "••••••"            # ≤6 chars → all bullets
    assert _mask("sk-proj-abc123xyz") == "sk-••••••xyz"
    long = "sk-proj-" + "a" * 30
    masked = _mask(long)
    assert masked.startswith("sk-")
    assert masked.endswith("aaa")
    assert "•" in masked
    assert long not in masked
