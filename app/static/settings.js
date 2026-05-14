// Settings page — keys, models, budgets, change password.

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
    throw new Error(`HTTP ${r.status} — ${detail}`);
  }
  return body;
}

function sourcePill(source) {
  if (source === "db") return { text: "saved in db", cls: "db" };
  if (source === "env") return { text: "from .env", cls: "env" };
  return { text: "not set", cls: "unset" };
}

function setStatus(el, text, kind) {
  el.textContent = text;
  el.className = `kv-status status small ${kind || ""}`;
}

// -- API keys -------------------------------------------------------------

function renderApiKeys(rows) {
  const tpl = document.getElementById("key-row-template");
  const container = document.getElementById("api-keys");
  container.innerHTML = "";

  for (const row of rows) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.querySelector(".kv-label").textContent = row.label;

    const input = node.querySelector(".kv-input");
    input.placeholder = row.set ? row.preview : (row.placeholder || `Set ${row.label}…`);

    const pill = node.querySelector(".kv-source-pill");
    const p = sourcePill(row.source);
    pill.textContent = p.text;
    pill.classList.add(p.cls);

    const showBtn = node.querySelector(".kv-show");
    showBtn.addEventListener("click", () => {
      input.type = input.type === "password" ? "text" : "password";
    });

    const status = node.querySelector(".kv-status");

    node.querySelector(".kv-save").addEventListener("click", async () => {
      const value = input.value;
      if (!value) {
        setStatus(status, "Type a value to save (use ↺ to revert to .env).", "err");
        return;
      }
      setStatus(status, "Saving…");
      try {
        await api(`/api/settings/${row.key}`, {
          method: "PUT",
          body: JSON.stringify({ value, is_secret: true }),
        });
        setStatus(status, "Saved.", "ok");
        input.value = "";
        await reload();
      } catch (e) {
        setStatus(status, e.message, "err");
      }
    });

    node.querySelector(".kv-clear").addEventListener("click", async () => {
      setStatus(status, "Reverting to .env…");
      try {
        await api(`/api/settings/${row.key}`, {
          method: "PUT",
          body: JSON.stringify({ value: "", is_secret: true }),
        });
        setStatus(status, "Cleared from DB.", "ok");
        input.value = "";
        await reload();
      } catch (e) {
        setStatus(status, e.message, "err");
      }
    });

    const testBtn = node.querySelector(".kv-test");
    // Map key to provider test endpoint
    const testTarget = {
      openai_api_key: "openai",
      anthropic_api_key: "anthropic",
      tavily_api_key: "tavily",
      adzuna_app_id: "adzuna",
      adzuna_app_key: "adzuna",
      reed_api_key: "reed",
    }[row.key];
    if (!testTarget) {
      testBtn.style.display = "none";
    } else {
      testBtn.addEventListener("click", async () => {
        setStatus(status, "Testing…");
        try {
          const result = await api(`/api/settings/test/${testTarget}`, { method: "POST" });
          if (result.ok) {
            setStatus(status, `Connected (HTTP ${result.status || "?"}).`, "ok");
          } else {
            setStatus(status, `Failed: ${result.detail || result.status}`, "err");
          }
        } catch (e) {
          setStatus(status, e.message, "err");
        }
      });
    }

    container.appendChild(node);
  }
}

// -- Models per task ------------------------------------------------------

function renderModels(models) {
  const tpl = document.getElementById("model-row-template");
  const container = document.getElementById("models-table");
  container.innerHTML = "";

  const options = models.choices
    .map((c) => `<option value="${c.provider}/${c.model}">${c.provider} / ${c.model}</option>`)
    .join("");

  for (const t of models.tasks) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.querySelector(".model-task").textContent = t.task;

    const selects = node.querySelectorAll(".model-select");
    const pills = node.querySelectorAll(".kv-source-pill");

    for (const [i, which] of ["default", "fallback"].entries()) {
      selects[i].innerHTML = options;
      selects[i].value = t[which].value;
      const pill = pills[i];
      if (t[which].is_override) {
        pill.textContent = "override";
        pill.classList.add("override");
      } else {
        pill.textContent = "spec default";
        pill.classList.add("spec");
      }
    }

    const status = node.querySelector(".kv-status");

    node.querySelector(".model-save").addEventListener("click", async () => {
      setStatus(status, "Saving…");
      try {
        for (const [i, which] of ["default", "fallback"].entries()) {
          const value = selects[i].value;
          const specDefault = t[which].spec_default;
          await api(`/api/settings/model.${t.task}.${which}`, {
            method: "PUT",
            body: JSON.stringify({
              value: value === specDefault ? "" : value, // save override only if different
              is_secret: false,
            }),
          });
        }
        setStatus(status, "Saved.", "ok");
        await reload();
      } catch (e) {
        setStatus(status, e.message, "err");
      }
    });

    node.querySelector(".model-reset").addEventListener("click", async () => {
      setStatus(status, "Resetting…");
      try {
        await api(`/api/settings/model.${t.task}.default`, {
          method: "PUT",
          body: JSON.stringify({ value: "", is_secret: false }),
        });
        await api(`/api/settings/model.${t.task}.fallback`, {
          method: "PUT",
          body: JSON.stringify({ value: "", is_secret: false }),
        });
        setStatus(status, "Back to spec defaults.", "ok");
        await reload();
      } catch (e) {
        setStatus(status, e.message, "err");
      }
    });

    container.appendChild(node);
  }
}

// -- Budgets --------------------------------------------------------------

function renderBudgets(rows) {
  const tpl = document.getElementById("budget-row-template");
  const container = document.getElementById("budgets");
  container.innerHTML = "";

  for (const row of rows) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.querySelector(".kv-label").textContent = row.label;
    const input = node.querySelector(".kv-input");
    input.value = row.value || "";
    input.placeholder = row.placeholder;

    const pill = node.querySelector(".kv-source-pill");
    const p = sourcePill(row.source);
    pill.textContent = p.text;
    pill.classList.add(p.cls);

    const status = node.querySelector(".kv-status");

    node.querySelector(".kv-save").addEventListener("click", async () => {
      setStatus(status, "Saving…");
      try {
        await api(`/api/settings/${row.key}`, {
          method: "PUT",
          body: JSON.stringify({ value: input.value, is_secret: false }),
        });
        setStatus(status, "Saved.", "ok");
        await reload();
      } catch (e) {
        setStatus(status, e.message, "err");
      }
    });

    node.querySelector(".kv-clear").addEventListener("click", async () => {
      setStatus(status, "Reverting to .env…");
      try {
        await api(`/api/settings/${row.key}`, {
          method: "PUT",
          body: JSON.stringify({ value: "", is_secret: false }),
        });
        setStatus(status, "Cleared from DB.", "ok");
        await reload();
      } catch (e) {
        setStatus(status, e.message, "err");
      }
    });

    container.appendChild(node);
  }
}

// -- Loader + password form -----------------------------------------------

async function reload() {
  try {
    const tree = await api("/api/settings");
    renderApiKeys(tree.api_keys);
    renderModels(tree.models);
    renderBudgets(tree.budgets);
  } catch (e) {
    document.getElementById("api-keys").innerHTML =
      `<div class="empty-row muted small">${e.message}</div>`;
  }
}

document.getElementById("pw-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const oldPw = document.getElementById("pw-old").value;
  const newPw = document.getElementById("pw-new").value;
  const status = document.getElementById("pw-status");
  status.textContent = "Changing…";
  status.className = "status small";
  try {
    await api("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
    });
    status.textContent = "Password changed.";
    status.className = "status small ok";
    document.getElementById("pw-old").value = "";
    document.getElementById("pw-new").value = "";
  } catch (err) {
    status.textContent = err.message;
    status.className = "status small err";
  }
});

document.getElementById("logout").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  window.location.href = "/ui/login.html";
});

reload();
