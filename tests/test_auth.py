"""Tests for the password + session-cookie auth library.

These don't go through the DB store — settings_store.get/put are async and
need a session. We test the pure-logic pieces here: bcrypt verification,
session serializer round-trip, the whitelist constant, cookie kwargs.
"""
from __future__ import annotations

import bcrypt
import pytest
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app import auth


def test_bcrypt_round_trip_matches_what_auth_uses() -> None:
    password = "correct-horse-battery-staple"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    assert bcrypt.checkpw(password.encode(), hashed.encode())
    assert not bcrypt.checkpw(b"wrong", hashed.encode())


def test_signed_session_round_trip() -> None:
    s = URLSafeTimedSerializer("test-secret", salt="careeros.auth.session")
    token = s.dumps({"u": "admin"})
    assert s.loads(token) == {"u": "admin"}


def test_signed_session_rejects_tampered_token() -> None:
    s = URLSafeTimedSerializer("test-secret", salt="careeros.auth.session")
    token = s.dumps({"u": "admin"})
    tampered = token[:-3] + "XXX"
    with pytest.raises(BadSignature):
        s.loads(tampered)


def test_whitelist_prefixes_include_essentials() -> None:
    # Things that MUST be public so the app boots and stays observable.
    must_be_public = ("/healthz", "/metrics", "/api/auth/", "/api/captures", "/ui/login")
    for path in must_be_public:
        assert any(path.startswith(p) or p == path for p in auth.WHITELIST_PREFIXES), (
            f"{path} not in whitelist"
        )


def test_cookie_kwargs_are_safe_defaults() -> None:
    k = auth.cookie_kwargs()
    assert k["httponly"] is True
    assert k["samesite"] == "lax"
    assert k["max_age"] == auth.SESSION_TTL_SECONDS
    assert k["path"] == "/"
    # Secure should be False in local/test env (so cookies work over http://)
    assert k["secure"] is False
