const captureBtn = document.getElementById("capture");
const saveBtn = document.getElementById("save");
const status = document.getElementById("status");
const backendUrlInput = document.getElementById("backendUrl");
const tokenInput = document.getElementById("token");

async function loadSettings() {
  const { backendUrl = "http://127.0.0.1:8000", token = "" } = await chrome.storage.local.get([
    "backendUrl",
    "token",
  ]);
  backendUrlInput.value = backendUrl;
  tokenInput.value = token;
}

function setStatus(text, kind) {
  status.textContent = text;
  status.className = `status ${kind || ""}`;
}

saveBtn.addEventListener("click", async () => {
  await chrome.storage.local.set({
    backendUrl: backendUrlInput.value.trim(),
    token: tokenInput.value,
  });
  setStatus("Settings saved.", "ok");
});

captureBtn.addEventListener("click", async () => {
  setStatus("Reading the page…");
  captureBtn.disabled = true;
  try {
    // chrome.runtime.sendMessage to the background SW. It opens the active tab,
    // asks the content script to extract, then POSTs.
    const result = await chrome.runtime.sendMessage({ type: "CAPTURE_ACTIVE_TAB" });
    if (!result) {
      setStatus("No response from background worker. Reload the extension.", "err");
      return;
    }
    if (!result.ok) {
      setStatus(result.error || "Capture failed.", "err");
      return;
    }
    const r = result.response || {};
    const deduped = r.deduped ? " (already in inbox — refreshed)" : "";
    setStatus(`Captured${deduped}. id=${r.discovered_job_id || "?"}`, "ok");
  } catch (e) {
    setStatus(`Error: ${e?.message || String(e)}`, "err");
  } finally {
    captureBtn.disabled = false;
  }
});

loadSettings();
