// Background service worker. Receives capture requests from the popup,
// makes sure the right content script is injected into the active tab,
// asks it to extract the JD, then POSTs to the configured backend.
// No background scraping — the popup must trigger.

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

function scriptForUrl(url) {
  if (url.includes("linkedin.com/jobs/")) return "src/content/linkedin.js";
  if (url.includes("indeed.com/viewjob") || url.includes("indeed.com/jobs"))
    return "src/content/indeed.js";
  return null;
}

async function sendExtract(tabId) {
  // Try messaging an already-injected content script first.
  try {
    return await chrome.tabs.sendMessage(tabId, { type: "EXTRACT_JD" });
  } catch (e) {
    // "Receiving end does not exist" → no content script in this tab yet.
    // (Happens on tabs opened before the extension was loaded, or on a
    // reload-without-navigation after the extension was updated.)
    return null;
  }
}

async function injectAndExtract(tabId, file) {
  await chrome.scripting.executeScript({
    target: { tabId },
    files: [file],
  });
  // Give the script a tick to register its onMessage listener.
  await new Promise((resolve) => setTimeout(resolve, 50));
  return await chrome.tabs.sendMessage(tabId, { type: "EXTRACT_JD" });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "CAPTURE_ACTIVE_TAB") {
    handleCapture()
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ ok: false, error: String(err?.message || err) }));
    return true;
  }
  return false;
});

async function handleCapture() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id || !tab.url) {
    return { ok: false, error: "No active tab" };
  }
  const file = scriptForUrl(tab.url);
  if (!file) {
    return {
      ok: false,
      error: "Not on a LinkedIn or Indeed job page. Open a job posting first.",
    };
  }

  // Try the already-injected listener; if it's not there, inject on demand.
  let extracted = await sendExtract(tab.id);
  if (!extracted) {
    try {
      extracted = await injectAndExtract(tab.id, file);
    } catch (e) {
      return {
        ok: false,
        error: `Could not inject content script: ${e?.message || String(e)}`,
      };
    }
  }
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

  let result;
  try {
    result = await postCapture(payload, config);
  } catch (e) {
    return {
      ok: false,
      error:
        `Network error posting to ${config.backendUrl}: ${e?.message || String(e)}. ` +
        `Is the backend running? Check the URL in the popup settings.`,
    };
  }
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
