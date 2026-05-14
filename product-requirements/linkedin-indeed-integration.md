# LinkedIn / Indeed Integration

## Why not scrape

The spec bans automated scraping of LinkedIn and Indeed (§3.3, §22). LinkedIn's User Agreement §8.2 and Indeed's ToS both prohibit scripted access. Direct scrapers are a portfolio liability, not an asset. The authorised paths for proactive discovery are the **Adzuna** and **Reed** official APIs (see [ARCHITECTURE.md](ARCHITECTURE.md)). For LinkedIn and Indeed specifically, we use a **Chrome extension companion**.

## What's shipped (V1, 2026-05-14)

`extension/` is a Manifest V3 Chrome extension. See [`extension/README.md`](../extension/README.md) for the load-unpacked walkthrough. Flow:

```
User on linkedin.com/jobs/view/4123456789
        │
        │  clicks the extension icon → "Send JD to CareerOS"
        ▼
  extension/src/popup.js
        │  asks the background SW
        ▼
  extension/src/background.js
        │  messages the active tab's content script
        ▼
  extension/src/content/linkedin.js (or indeed.js)
        │  extracts title, company, location, full JD text from the page DOM
        │  using a small fallback chain of selectors
        │  returns {source, url, title, company, location, raw_jd, captured_at}
        ▼
  extension/src/background.js
        │  POSTs to {backendUrl}/api/captures with
        │  Authorization: Bearer {EXTENSION_API_TOKEN}
        ▼
  FastAPI app/api/captures.py
        │  validates bearer token
        │  derives external_id from URL (LinkedIn jobId, Indeed jk)
        │  upserts a discovered_jobs row (triage_status="pending")
        │  returns {discovered_job_id, deduped}
        ▼
  User runs POST /api/discover (or future per-row "Score now")
        to fan out preprocess + matcher and decide apply/skip
```

## What the extension does NOT do

- No background page reads. Acts only on explicit popup click.
- No automated apply, message-send, connection-request, scroll, or form fill.
- No DOM mutation that could violate the site's interactive contract.
- No keystroke or mouse capture.
- No off-site beaconing — POSTs only to the configured CareerOS backend URL.
- No LLM cost on capture (auto-scoring is a separate explicit step).

## Manifest scope

```jsonc
"host_permissions": [
  "https://*.linkedin.com/jobs/*",
  "https://*.indeed.com/viewjob*",
  "https://*.indeed.com/jobs*",
  "http://127.0.0.1:8000/*",
  "http://localhost:8000/*"
],
"content_scripts": [
  {
    "matches": [
      "https://*.linkedin.com/jobs/view/*",
      "https://*.linkedin.com/jobs/collections/*",
      "https://*.linkedin.com/jobs/search/*"
    ],
    "js": ["src/content/linkedin.js"],
    "run_at": "document_idle"
  },
  {
    "matches": [
      "https://*.indeed.com/viewjob*",
      "https://*.indeed.com/jobs*"
    ],
    "js": ["src/content/indeed.js"],
    "run_at": "document_idle"
  }
]
```

Anything outside these patterns: the content script does not inject.

## Auth (V1 minimal)

- Single shared bearer token in `EXTENSION_API_TOKEN`. Extension stores it in `chrome.storage.local` via the popup → Save.
- Backend rejects POSTs without a valid token (401) when the env var is set. If unset, the endpoint is open (intended for first-run local dev only).
- **V2 follow-up**: replace with a short-lived JWT minted by a "Pair extension" page in the UI. Not needed at single-user scale.

## Backend contract

```
POST /api/captures
Authorization: Bearer <EXTENSION_API_TOKEN>
Content-Type: application/json

{
  "source": "linkedin" | "indeed",
  "url": "https://www.linkedin.com/jobs/view/4123456789",
  "title": "Senior AI Engineer",
  "company": "ExampleCo",
  "location": "Dublin, Ireland",
  "raw_jd": "About the job ...",
  "captured_at": "2026-05-14T10:15:00Z"
}

→ 201
{
  "discovered_job_id": "uuid",
  "source": "linkedin",
  "external_id": "4123456789",
  "deduped": false
}
```

Re-capturing the same URL **updates** the existing row (refreshes `raw_jd`, `title`, `company`, `location`, `scraped_at`) and returns `deduped: true`. This is intentional — JDs sometimes get edited.

## Failure modes

| Scenario | Handling |
|---|---|
| User clicks but on a non-job tab | Popup shows "Not on a LinkedIn or Indeed job page." No request sent. |
| Content script fails to find description selector | Popup shows "JD text was too short to capture." User scrolls description into view and retries. |
| Backend 401 (bad/missing token) | Popup shows the error verbatim. User re-pastes token, clicks Save. |
| Backend 5xx | Popup surfaces the body. No automatic retry. |
| Captured JD matches injection regex | Stored as normal; triage_status stays `pending`. When discovery scoring runs, the preprocess node sets `quarantined=true` and the workflow halts. |

## Out of scope for V1

- Firefox / Safari ports
- Chrome Web Store publication (sideload only — `chrome://extensions` → Load unpacked)
- Auto-fill of application forms (explicitly banned)
- Reading recruiter messages, InMail, or any page outside `linkedin.com/jobs/*` and `indeed.com/viewjob*`
- Per-row "Score now" button — for now use `POST /api/discover` to auto-score all pending captures

## Selector maintenance note

LinkedIn and Indeed change their DOM occasionally. The extractors use a fallback chain so a single class rename doesn't break us. If extraction breaks: inspect the page, find a stable selector (prefer `data-testid` over class names), and prepend it to the appropriate array in `extension/src/content/linkedin.js` or `indeed.js`. No backend changes needed.
