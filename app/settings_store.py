"""Encrypted key/value store backed by app_settings.

Values are encrypted with AES-GCM using a 32-byte key derived from
PII_ENCRYPTION_KEY (env). If the env var is empty on first call we generate
a new key, persist it to .env on disk, and reuse it from then on so the
user doesn't have to bootstrap manually.

This module is the single source of truth for runtime-editable config:
- API keys (openai, anthropic, tavily, adzuna, reed)
- Per-task model overrides
- Budget caps
- Admin password hash
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AppSetting
from app.db.session import get_sessionmaker
from app.observability.log import get_logger

_log = get_logger(__name__)

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_ENV_FILE: Final = _REPO_ROOT / ".env"

_KEY_CACHE: bytes | None = None


def _get_or_create_master_key() -> bytes:
    """Return the 32-byte AES-GCM master key.

    Loading order:
      1. PII_ENCRYPTION_KEY env var (base64) → decode to 32 bytes
      2. If missing/invalid, generate a new one, persist to .env, return it
    """
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE

    raw = get_settings().pii_encryption_key.strip()
    if raw:
        try:
            key = base64.b64decode(raw)
            if len(key) == 32:
                _KEY_CACHE = key
                return key
        except Exception:  # noqa: BLE001
            pass
        _log.warning("settings_store.invalid_pii_key", reason="not 32-byte base64; regenerating")

    new_key = AESGCM.generate_key(bit_length=256)
    encoded = base64.b64encode(new_key).decode("ascii")
    _persist_master_key_to_env(encoded)
    # Refresh the Settings cache so subsequent reads see the new value.
    get_settings.cache_clear()
    os.environ["PII_ENCRYPTION_KEY"] = encoded
    _KEY_CACHE = new_key
    return new_key


def _persist_master_key_to_env(encoded: str) -> None:
    """Update PII_ENCRYPTION_KEY=... in .env, append if absent. Best-effort —
    if the file is read-only (e.g. baked into a container image) we just keep
    the key in memory and ask the user to set it explicitly next time."""
    if not _ENV_FILE.exists():
        return
    try:
        text = _ENV_FILE.read_text(encoding="utf-8")
        if re.search(r"^PII_ENCRYPTION_KEY=", text, flags=re.M):
            text = re.sub(
                r"^PII_ENCRYPTION_KEY=.*$",
                f"PII_ENCRYPTION_KEY={encoded}",
                text,
                flags=re.M,
            )
        else:
            sep = "" if text.endswith("\n") else "\n"
            text = f"{text}{sep}PII_ENCRYPTION_KEY={encoded}\n"
        _ENV_FILE.write_text(text, encoding="utf-8")
        _log.info("settings_store.master_key_persisted")
    except Exception as e:  # noqa: BLE001
        _log.warning("settings_store.master_key_persist_failed", error=str(e))


def _encrypt(plaintext: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ct = AESGCM(_get_or_create_master_key()).encrypt(nonce, plaintext, associated_data=None)
    return ct, nonce


def _decrypt(ct: bytes, nonce: bytes) -> bytes:
    return AESGCM(_get_or_create_master_key()).decrypt(nonce, ct, associated_data=None)


async def put(key: str, value: str, *, is_secret: bool = True) -> None:
    """Insert-or-update a setting. Empty value deletes the row."""
    if value == "":
        await delete(key)
        return
    async with get_sessionmaker()() as session:
        await _put(session, key, value, is_secret=is_secret)
        await session.commit()


async def _put(session: AsyncSession, key: str, value: str, *, is_secret: bool) -> None:
    ct, nonce = _encrypt(value.encode("utf-8"))
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(
            AppSetting(key=key, encrypted_value=ct, nonce=nonce, is_secret=is_secret)
        )
    else:
        row.encrypted_value = ct
        row.nonce = nonce
        row.is_secret = is_secret


async def get(key: str, default: str | None = None) -> str | None:
    """Return the decrypted setting or ``default`` if not set."""
    async with get_sessionmaker()() as session:
        row = await session.get(AppSetting, key)
        if row is None:
            return default
        try:
            return _decrypt(row.encrypted_value, row.nonce).decode("utf-8")
        except Exception as e:  # noqa: BLE001
            _log.warning("settings_store.decrypt_failed", key=key, error=str(e))
            return default


async def delete(key: str) -> None:
    async with get_sessionmaker()() as session:
        row = await session.get(AppSetting, key)
        if row is not None:
            await session.delete(row)
            await session.commit()


async def list_keys() -> list[str]:
    async with get_sessionmaker()() as session:
        res = await session.execute(select(AppSetting.key))
        return [r[0] for r in res.all()]


# -- High-level helpers used by router / providers / scrapers -----------------


async def effective_secret(key: str, env_value: str) -> str:
    """Return the DB value if set (priority), else the env value, else ''."""
    db = await get(key)
    return db if db else env_value
