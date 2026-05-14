---
name: auth-and-secrets
description: Use BEFORE adding any new API endpoint, UI page, secret-reading code, or any change to auth/login/session/cookies/CORS/bearer-token in CareerOS AI. Enforces the spec §25.4 invariants — default-deny auth, settings_store precedence, never hardcode keys, never log secrets.
---

# auth-and-secrets — CareerOS AI session + settings invariants

CareerOS AI ships a single-user session-auth model + an encrypted settings store (spec §25.4). Three invariants must hold across the codebase.

## Invariant 1 — New endpoints are auth-gated by default

The middleware in `app/main.py` requires a valid session cookie on every `/api/*` and `/ui/*` URL **except** those in `auth.WHITELIST_PREFIXES`. When adding a new endpoint:

- Do **not** disable the middleware.
- Do **not** add a public bypass without justification.
- If the endpoint truly needs to be public (e.g. healthcheck, machine-to-machine via bearer token), append its prefix to `auth.WHITELIST_PREFIXES` with a one-line comment explaining why, in the same commit.

## Invariant 2 — Secrets and overridable config go through `settings_store`

Read order for any API key, model name, or budget cap:

1. `app.settings_store.get(name)` — DB value if user has set it via the Settings UI
2. environment variable
3. hardcoded default

Helper: `app.settings_store.effective_secret(name, env_value)` does steps 1+2 in one call. Use it from `app/llm/providers/*`, `app/llm/router.py`, `app/scrapers/registry.py`, etc.

**Never** read directly from `os.environ` or `get_settings()` for things the user can edit at runtime. That makes UI overrides require a restart, which defeats the point.

## Invariant 3 — Secrets never appear in logs, traces, or responses

- Log line that includes any user-supplied string must pass through `app.observability.scrub.scrub_pii`.
- API responses that list settings (`GET /api/settings`) must **mask** values (`is_secret: true` → return `••••••••` or last-4 only, never the cleartext).
- LangSmith metadata explicitly excludes auth headers.
- A test (`tests/test_logs_no_pii.py`) asserts the scrubber works; add cases when you add new secret-shaped fields.

## When you touch auth/settings code

- Re-read [spec §25.4](../../product-requirements/CareerOS_AI_Product_Spec_v2.md) before changing the cookie TTL, the whitelist, or the encryption scheme.
- Bcrypt rounds is currently 12 — don't lower without raising a separate flag.
- Cookie attributes (`HttpOnly`, `SameSite=lax`, `Secure` in prod) come from `auth.cookie_kwargs()` — keep that the only seam.
- The bearer-token path for `/api/captures` is **separate** from session auth on purpose; don't try to unify them.

## Quick verification before commit

```bash
# Auth flow end-to-end
curl -sS http://127.0.0.1:8000/api/auth/status     # {"initialised":true}
curl -sS -c /tmp/c.cookies -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"..."}'
curl -sS -b /tmp/c.cookies http://127.0.0.1:8000/api/auth/me

# New endpoint should 401 without cookie
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/your-new-route   # expect 401

# New endpoint should 200 with cookie
curl -sS -b /tmp/c.cookies -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/your-new-route
```

If a new endpoint returns 200 without a cookie and isn't on the whitelist for a good reason, **stop and fix the middleware wiring** before merging.
