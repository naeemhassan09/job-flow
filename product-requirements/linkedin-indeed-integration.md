# LinkedIn / Indeed Integration

## Why not scrape

The spec explicitly bans automated scraping (§3.3, §22). LinkedIn's User Agreement §8.2 and Indeed's ToS both prohibit scripted access. Building a scraper would be a portfolio liability, not an asset.

## What we build instead — a Chrome companion extension

`extension/` is a small Manifest V3 Chrome extension. Flow:

```
User on linkedin.com/jobs/view/12345
        │
        │  clicks "Send to CareerOS" button injected by content script
        ▼
  extension/content-script.js
    reads visible JD elements from the DOM of the page the user is already viewing
        │
        ▼
  extension/background.js
    POSTs { source: "linkedin", url, raw_jd, captured_at } to
    https://careeros.example.com/api/applications
    with the user's short-lived UI session token
        │
        ▼
  FastAPI /api/applications
    creates application_id, queues workflow
        │
        ▼
  User sees the new row in the CareerOS tracker UI
```

## What the extension does NOT do

- No background page reads. Acts only on explicit click.
- No automated apply, message-send, or connection-request.
- No DOM mutation that could violate the site's interactive contract.
- No keystroke or mouse capture.
- No off-site beaconing — POSTs only to the configured CareerOS backend.

## Scope (URL match patterns)

```json
{
  "matches": [
    "https://www.linkedin.com/jobs/view/*",
    "https://www.linkedin.com/jobs/collections/*",
    "https://www.indeed.com/viewjob*",
    "https://*.indeed.com/viewjob*"
  ]
}
```

Anything outside these patterns: the content script does not inject.

## Auth

- User signs into the CareerOS UI (single-user mode in V1 means a long-lived API token from `.env`).
- UI exposes a "Pair extension" page that emits a short-lived JWT into a `chrome.storage.local` value via a one-time URL.
- Extension POSTs with `Authorization: Bearer <jwt>`; backend rejects expired tokens.

## Backend contract

```
POST /api/applications
Content-Type: application/json

{
  "source": "linkedin" | "indeed" | "paste",
  "url": "https://www.linkedin.com/jobs/view/12345",
  "raw_jd": "Senior AI Platform Engineer — Dublin ...",
  "captured_at": "2026-05-13T22:15:00Z"
}

→ 201
{
  "application_id": "...",
  "status": "queued"
}
```

`source: "paste"` is the UI fallback when the user copy-pastes a JD.

## Failure modes

| Scenario | Handling |
|---|---|
| User clicks but the page DOM has no recognisable JD selectors | Show a Chrome notification: "Couldn't find a JD on this page." Do nothing. |
| Backend 401 | Surface a "Pair extension again" notification. |
| Backend 5xx | Retry once with backoff, then notify the user. |
| Backend rejects on injection classifier | Application is created with `status: quarantined`; UI surfaces it for human review. |

## Out of scope for V1

- Firefox/Safari ports.
- Chrome Web Store publication (sideload only for V1).
- Auto-fill of application forms (explicitly banned).
- Reading recruiter messages or InMail.
