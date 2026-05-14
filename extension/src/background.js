// Background service worker. Receives capture requests from the popup,
// asks the active tab's content script to extract the JD, then POSTs to the
// configured backend. No background scraping happens — the popup must trigger.

const DEFAULTS = {
  backendUrl: "http://127.0.0.1:8000",
  token: "",
};

async function getConfig() {
  const stored = await chrome.storage.local.get(["backendUrl", "token"]);
  return {
    backendUrl: stored.backendUrl || DEFAULTS.backendUrl,
    token: stored.token || DEFAULTS.token,
  };
}

async function postCapture(payload, { backendUrl, token }) {
  const url = `${backendUrl.replace(/\/+$/, "")}/api/captures`;
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const r = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  const body = await r.text();
  let json = null;
  try {
    json = JSON.parse(body);
  } catch {
    /* not JSON */
  }
  return { status: r.status, ok: r.ok, body: json || body };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "CAPTURE_ACTIVE_TAB") {
    handleCapture()
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  return false;
});

async function handleCapture() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id || !tab.url) {
    return { ok: false, error: "No active tab" };
  }
  const isLinkedIn = tab.url.includes("linkedin.com/jobs/");
  const isIndeed = tab.url.includes("indeed.com/viewjob") || tab.url.includes("indeed.com/jobs");
  if (!isLinkedIn && !isIndeed) {
    return {
      ok: false,
      error: "Not on a LinkedIn or Indeed job page. Open a job posting first.",
    };
  }

  const extracted = await chrome.tabs.sendMessage(tab.id, { type: "EXTRACT_JD" });
  if (!extracted || !extracted.ok || !extracted.payload) {
    return { ok: false, error: "Could not extract JD from the page DOM." };
  }
  const { payload } = extracted;
  if (!payload.raw_jd || payload.raw_jd.length < 100) {
    return {
      ok: false,
      error: "JD text was too short to capture. Scroll the description into view and retry.",
    };
  }

  const config = await getConfig();
  if (!config.backendUrl) {
    return { ok: false, error: "Backend URL not configured. Open the popup options." };
  }

  const result = await postCapture(payload, config);
  if (!result.ok) {
    return {
      ok: false,
      error: `Backend rejected capture (HTTP ${result.status}): ${
        typeof result.body === "string" ? result.body : JSON.stringify(result.body)
      }`,
    };
  }
  return { ok: true, response: result.body, captured: payload };
}
