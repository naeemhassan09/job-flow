// Login + first-run setup page. If the server reports no admin yet, render
// the setup form (asks for new username + password twice); otherwise render
// the standard login form.

const els = {
  form: document.getElementById("auth-form"),
  username: document.getElementById("username"),
  password: document.getElementById("password"),
  confirm: document.getElementById("confirm"),
  confirmField: document.getElementById("confirm-field"),
  submit: document.getElementById("submit"),
  status: document.getElementById("status"),
  subtitle: document.getElementById("auth-subtitle"),
  footer: document.getElementById("auth-footer"),
};

let mode = "login"; // or "init"

async function api(path, init) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...init,
  });
  const text = await r.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = text; }
  if (!r.ok) {
    const detail = typeof body === "object" && body && body.detail ? body.detail : text;
    throw new Error(detail);
  }
  return body;
}

function setStatus(text, kind) {
  els.status.textContent = text;
  els.status.className = `status ${kind || ""}`;
}

async function detectMode() {
  try {
    const s = await api("/api/auth/status");
    mode = s.initialised ? "login" : "init";
  } catch {
    mode = "login";
  }

  if (mode === "init") {
    els.subtitle.textContent = "Set up the admin account";
    els.confirmField.style.display = "";
    els.password.setAttribute("autocomplete", "new-password");
    els.submit.textContent = "Create account & sign in";
    els.username.value = "admin";
    els.footer.textContent = "First-time setup — these credentials only work on this local install.";
  } else {
    els.subtitle.textContent = "Sign in to continue";
    els.confirmField.style.display = "none";
    els.password.setAttribute("autocomplete", "current-password");
    els.submit.textContent = "Sign in";
    els.footer.textContent = "Local single-user system — no signups, no password resets via email.";
  }
}

async function handleSubmit(e) {
  e.preventDefault();
  const username = els.username.value.trim();
  const password = els.password.value;

  if (!username || !password) {
    setStatus("Both fields are required.", "err");
    return;
  }
  if (mode === "init") {
    if (password.length < 8) {
      setStatus("Password must be at least 8 characters.", "err");
      return;
    }
    if (password !== els.confirm.value) {
      setStatus("Passwords do not match.", "err");
      return;
    }
  }

  els.submit.disabled = true;
  setStatus(mode === "init" ? "Creating account…" : "Signing in…", "");
  try {
    const path = mode === "init" ? "/api/auth/init" : "/api/auth/login";
    await api(path, { method: "POST", body: JSON.stringify({ username, password }) });
    setStatus("Success. Redirecting…", "ok");
    const next = new URLSearchParams(location.search).get("next") || "/ui/";
    window.location.replace(next);
  } catch (err) {
    setStatus(err.message || "Sign-in failed.", "err");
  } finally {
    els.submit.disabled = false;
  }
}

els.form.addEventListener("submit", handleSubmit);
detectMode();
