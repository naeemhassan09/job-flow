# CareerOS AI — Chrome Extension Companion

Sends the JD from the LinkedIn or Indeed tab you are viewing to your local CareerOS AI backend. Manual click only — no background scraping, no automated apply, no message sending.

## What it does (and does not)

| Behaviour | Status |
|---|---|
| Reads the JD from the page DOM when you click "Send JD to CareerOS" | yes |
| POSTs the JD to your configured backend's `/api/captures` | yes |
| Stores the result in the discovered-jobs inbox (`triage_status: pending`) | yes |
| Reads pages in the background | **no** |
| Sends messages or applies on your behalf | **no** |
| Scrapes search-result pages or recruiter inboxes | **no** |
| Triggers LLM cost on capture | **no** (auto-scoring is a separate step) |

Scope is limited by the manifest's `host_permissions` and `content_scripts.matches` — the extension can only run on URLs matching `https://*.linkedin.com/jobs/*` and `https://*.indeed.com/viewjob*` / `https://*.indeed.com/jobs*`.

## Load it unpacked in Chrome

1. **Start the backend** locally:
   ```bash
   .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. **Set a token** in `.env`:
   ```
   EXTENSION_API_TOKEN=any-long-random-string
   ```
   Restart uvicorn after changing.

3. **Load the extension**:
   - Open `chrome://extensions`
   - Toggle **Developer mode** on (top right)
   - Click **Load unpacked**
   - Select the `extension/` directory of this repo
   - Note the extension's ID (you'll need it for CORS)

4. **Allow CORS for the extension**. Add the extension's chrome-extension URL to `.env`:
   ```
   CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,chrome-extension://<your-id>
   ```
   (The backend also allows any `chrome-extension://` origin via a regex, so this is belt-and-braces.)

5. **Configure the extension**. Click the puzzle-piece in Chrome → CareerOS AI → set:
   - **Backend URL**: `http://127.0.0.1:8000`
   - **Bearer token**: the same value as `EXTENSION_API_TOKEN`

## Use it

1. Open a LinkedIn job posting (e.g. `https://www.linkedin.com/jobs/view/4123456789`) or an Indeed one (`https://www.indeed.com/viewjob?jk=abc123`).
2. Click the CareerOS AI extension icon.
3. Click **Send JD to CareerOS**.
4. Verify it landed in your inbox:
   ```bash
   curl http://127.0.0.1:8000/api/jobs?source=linkedin | jq .
   ```

The job goes in with `triage_status: pending`. To score everything pending, run:

```bash
curl -X POST http://127.0.0.1:8000/api/discover -H 'Content-Type: application/json' -d '{}'
```

(In a future iteration there will be a per-row "Score now" button.)

## Files

```
extension/
├── manifest.json           # MV3, scoped to LI/Indeed job URLs
├── src/
│   ├── background.js       # Service worker: routes popup → tab → backend
│   ├── popup.html / .js / .css
│   ├── options.html        # Same form as popup, for chrome://extensions
│   └── content/
│       ├── linkedin.js     # DOM extractor for LinkedIn JD pages
│       └── indeed.js       # DOM extractor for Indeed JD pages
└── README.md               # this file
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Not on a LinkedIn or Indeed job page" | You clicked on a non-job tab. Open the JD page first. |
| "JD text was too short to capture" | The page hasn't fully rendered. Scroll the description into view and retry. LinkedIn lazy-loads the long body. |
| `HTTP 401: invalid bearer token` | Token mismatch. Re-copy from `.env` into the popup → Save. |
| `HTTP 0` / network error | Backend not running, or CORS blocks the chrome-extension origin. Check `CORS_ORIGINS` in `.env` and restart uvicorn. |
| Capture says "(already in inbox — refreshed)" | The same URL was captured before. The backend updates the JD text in place rather than duplicating. |

## Selector maintenance

LinkedIn and Indeed change their DOM occasionally; the extractors fall back through a small list of selectors. If extraction breaks:

1. Open the JD page, right-click the title → Inspect.
2. Find a stable selector (prefer `data-testid` over class names).
3. Add it to the top of the relevant array in `src/content/linkedin.js` or `indeed.js`.

## Privacy and ToS

- The extension reads only when you click. There is no background page read, beacon, or telemetry.
- It POSTs only to the backend URL you configured.
- It does not interact with LinkedIn / Indeed beyond reading the DOM of the tab you are viewing — no clicks, form fills, scroll injection, or background fetches against those sites.

This is the path the spec explicitly designates for LinkedIn and Indeed (see `product-requirements/linkedin-indeed-integration.md`). The Adzuna and Reed scrapers in `app/scrapers/` are the authorised path for proactive discovery on ToS-permitting sources.
