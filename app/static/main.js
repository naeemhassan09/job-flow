// Inbox UI — single page, no framework. Fetches from /api/*.

const API = ""; // same origin
const els = {
  list: document.getElementById("list"),
  detail: document.getElementById("detail"),
  filterStatus: document.getElementById("filter-status"),
  filterSource: document.getElementById("filter-source"),
  refresh: document.getElementById("refresh"),
  count: document.getElementById("count"),
  rowTpl: document.getElementById("row-template"),
  detailTpl: document.getElementById("detail-template"),
};

const state = {
  jobs: [],
  selectedId: null,
};

// -- fetch helpers --

async function api(path, init) {
  const r = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
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

async function loadList() {
  const status = els.filterStatus.value || "all";
  const source = els.filterSource.value || "";
  const params = new URLSearchParams({ status, limit: "200" });
  if (source) params.set("source", source);
  els.list.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const jobs = await api(`/api/jobs?${params.toString()}`);
    state.jobs = jobs;
    renderList();
    if (state.selectedId && jobs.find((j) => j.id === state.selectedId)) {
      loadDetail(state.selectedId);
    } else if (jobs.length) {
      loadDetail(jobs[0].id);
    } else {
      els.detail.innerHTML = '<div class="empty">No jobs match the current filters.</div>';
    }
  } catch (e) {
    els.list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

function bandClass(score, decision) {
  if (decision === "apply") return "apply";
  if (decision === "maybe") return "maybe";
  if (decision === "skip") return "skip";
  if (score == null) return "";
  if (score >= 70) return "apply";
  if (score >= 50) return "maybe";
  return "skip";
}

function renderList() {
  els.list.innerHTML = "";
  els.count.textContent = `${state.jobs.length} job${state.jobs.length === 1 ? "" : "s"}`;
  if (!state.jobs.length) {
    els.list.innerHTML = '<div class="empty">No jobs yet. Capture one from the extension.</div>';
    return;
  }
  for (const job of state.jobs) {
    const node = els.rowTpl.content.firstElementChild.cloneNode(true);
    node.dataset.id = job.id;
    node.querySelector(".title").textContent = job.title || "(no title)";
    node.querySelector(".company").textContent = job.company || "—";
    node.querySelector(".location").textContent = job.location || "—";
    const score = node.querySelector(".score");
    if (job.fit_score == null) {
      score.textContent = "—";
    } else {
      score.textContent = Math.round(job.fit_score);
      score.classList.add(bandClass(job.fit_score, job.decision));
    }
    node.querySelector(".source-pill").textContent = job.source;
    node.querySelector(".status-pill").textContent = job.triage_status;
    const appPill = node.querySelector(".app-status-pill");
    if (job.application_status) {
      appPill.textContent = job.application_status.replace(/_/g, " ");
      appPill.classList.add(job.application_status);
    }
    if (job.id === state.selectedId) node.classList.add("active");
    node.addEventListener("click", () => loadDetail(job.id));
    els.list.appendChild(node);
  }
}

async function loadDetail(jobId) {
  state.selectedId = jobId;
  document.querySelectorAll(".row").forEach((n) =>
    n.classList.toggle("active", n.dataset.id === jobId)
  );
  els.detail.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const job = await api(`/api/jobs/${jobId}`);
    renderDetail(job);
  } catch (e) {
    els.detail.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

function renderDetail(job) {
  const node = els.detailTpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".job-title").textContent = job.title || "(no title)";
  node.querySelector(".job-company").textContent = job.company || "—";
  node.querySelector(".job-location").textContent = job.location || "—";

  const link = node.querySelector(".job-url");
  link.href = job.url || "#";
  if (!job.url) link.classList.add("hidden");

  node.querySelector(".job-source-pill").textContent = job.source;
  node.querySelector(".job-status-pill").textContent = job.triage_status;
  const jobAppPill = node.querySelector(".job-app-status-pill");
  if (job.application_status) {
    jobAppPill.textContent = job.application_status.replace(/_/g, " ");
    jobAppPill.classList.add(job.application_status);
  } else {
    jobAppPill.remove();
  }
  if (job.scraped_at) {
    node.querySelector(".job-captured").textContent =
      `captured ${new Date(job.scraped_at).toLocaleString()}`;
  }

  // Delete button
  node.querySelector('[data-action="delete-job"]').addEventListener("click", async () => {
    const label = `${job.title || "this job"} @ ${job.company || "—"}`;
    if (!confirm(`Delete "${label}" from the inbox?\n\nThis cannot be undone.`)) return;
    try {
      const r = await fetch(`/api/jobs/${job.id}`, {
        method: "DELETE",
        credentials: "same-origin",
      });
      if (!r.ok) {
        const body = await r.text();
        let detail = body;
        try { detail = JSON.parse(body).detail || body; } catch { /* not JSON */ }
        alert(`Delete failed: HTTP ${r.status} — ${detail}`);
        return;
      }
      state.selectedId = null;
      await loadList();
    } catch (e) {
      alert(`Delete failed: ${e.message}`);
    }
  });

  // Score block
  const scoreNum = node.querySelector(".score-num");
  const decisionPill = node.querySelector(".decision-pill");
  const decisionReason = node.querySelector(".decision-reason");
  if (job.fit_score != null) {
    scoreNum.textContent = Math.round(job.fit_score);
    const band = bandClass(job.fit_score, job.decision);
    scoreNum.classList.add(band);
    decisionPill.classList.add(band);
    decisionPill.textContent = job.decision || band;
    decisionReason.textContent = job.decision_reason || "";
  } else {
    scoreNum.textContent = "—";
    decisionPill.textContent = "unscored";
    decisionReason.textContent = "Click Score now to run preprocess + matcher against this JD.";
  }

  // Breakdown bars
  const bars = node.querySelector(".breakdown-bars");
  const breakdown = job.score_breakdown || {};
  const keys = Object.keys(breakdown);
  if (keys.length === 0) {
    node.querySelector(".breakdown").style.display = "none";
  } else {
    for (const k of keys) {
      const v = Number(breakdown[k]);
      const row = document.createElement("div");
      row.className = "bar";
      row.innerHTML = `
        <span class="bar-label">${k.replace(/_/g, " ")}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${Math.max(0, Math.min(100, v))}%"></span></span>
        <span class="bar-value">${Math.round(v)}</span>
      `;
      bars.appendChild(row);
    }
  }

  // Score now button
  node.querySelector('[data-action="score"]').addEventListener("click", async (e) => {
    e.target.disabled = true;
    e.target.textContent = "Scoring…";
    try {
      await api(`/api/jobs/${job.id}/score`, { method: "POST", body: "{}" });
      await loadList();
    } catch (err) {
      alert(`Score failed: ${err.message}`);
    } finally {
      e.target.disabled = false;
      e.target.textContent = "Score now";
    }
  });

  // Research section
  wireResearch(node, job);

  // Cover-letter section
  wireCoverLetter(node, job);

  // Lifecycle section
  const lcStatus = node.querySelector("#lifecycle-status");
  const lcAppliedAt = node.querySelector("#lifecycle-applied-at");
  const lcNote = node.querySelector("#lifecycle-note");
  const lcMsg = node.querySelector(".lifecycle-status-msg");
  if (lcStatus) {
    lcStatus.value = job.application_status || "";
    if (job.applied_at) {
      lcAppliedAt.value = job.applied_at.slice(0, 10);
    }
    const renderHistory = () => {
      const list = node.querySelector(".status-history-list");
      const counter = node.querySelector(".status-history-count");
      const items = (job.status_history || []).slice().reverse();
      counter.textContent = String(items.length);
      list.innerHTML = items
        .map(
          (h) => `
          <li>
            <span class="h-when">${new Date(h.at).toLocaleString()}</span>
            <span class="h-status">${(h.status || "").replace(/_/g, " ")}</span>
            <span class="h-note">${h.note ? escapeHtml(h.note) : "<span class=\"muted\">(no note)</span>"}</span>
          </li>`,
        )
        .join("");
    };
    renderHistory();

    node.querySelector('[data-action="save-status"]').addEventListener("click", async (e) => {
      const status = lcStatus.value;
      if (!status) {
        lcMsg.textContent = "Pick a status first.";
        lcMsg.className = "lifecycle-status-msg err small";
        return;
      }
      const payload = {
        status,
        applied_at: lcAppliedAt.value
          ? new Date(lcAppliedAt.value + "T12:00:00Z").toISOString()
          : null,
        note: lcNote.value || null,
      };
      e.target.disabled = true;
      lcMsg.textContent = "Saving…";
      lcMsg.className = "lifecycle-status-msg muted small";
      try {
        const res = await api(`/api/jobs/${job.id}/status`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        job.application_status = res.application_status;
        job.applied_at = res.applied_at;
        job.status_history = res.status_history;
        lcMsg.textContent = "Saved.";
        lcMsg.className = "lifecycle-status-msg ok small";
        lcNote.value = "";
        renderHistory();
        // Refresh the list so the new pill shows up.
        await loadList();
      } catch (err) {
        lcMsg.textContent = err.message;
        lcMsg.className = "lifecycle-status-msg err small";
      } finally {
        e.target.disabled = false;
      }
    });
  }

  // Feedback section
  const fb = job.human_feedback || {};
  const thumbBtns = node.querySelectorAll(".thumb");
  thumbBtns.forEach((btn) => {
    if (fb.thumb && btn.dataset.thumb === fb.thumb) btn.classList.add("active");
    btn.addEventListener("click", () => {
      thumbBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  const scoreCorrection = node.querySelector('[data-field="score_correction"]');
  scoreCorrection.value = fb.score_correction ?? "";

  const decisionOverride = node.querySelector('[data-field="decision_override"]');
  decisionOverride.value = fb.decision_override ?? "";

  const notes = node.querySelector('[data-field="notes"]');
  notes.value = fb.notes ?? "";

  const fbStatus = node.querySelector(".feedback-status");
  node.querySelector('[data-action="save-feedback"]').addEventListener("click", async (e) => {
    const active = node.querySelector(".thumb.active");
    const payload = {
      thumb: active ? active.dataset.thumb : null,
      score_correction: scoreCorrection.value === "" ? null : Number(scoreCorrection.value),
      decision_override: decisionOverride.value || null,
      notes: notes.value || null,
    };
    e.target.disabled = true;
    fbStatus.textContent = "Saving…";
    fbStatus.className = "feedback-status muted small";
    try {
      await api(`/api/jobs/${job.id}/feedback`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      fbStatus.textContent = "Saved.";
      fbStatus.className = "feedback-status ok small";
    } catch (err) {
      fbStatus.textContent = `Error: ${err.message}`;
      fbStatus.className = "feedback-status err small";
    } finally {
      e.target.disabled = false;
    }
  });

  // Parsed JSON + raw text
  node.querySelector(".parsed-json").textContent =
    Object.keys(job.parsed_job || {}).length
      ? JSON.stringify(job.parsed_job, null, 2)
      : "(no parsed JD yet — click Score now)";
  node.querySelector(".raw-text").textContent = job.description || "(no description)";

  els.detail.innerHTML = "";
  els.detail.appendChild(node);
}

// -- wire events --

function wireCoverLetter(node, job) {
  const textarea = node.querySelector("#cl-text");
  const bullets = node.querySelector("#cl-bullets");
  const stateP = node.querySelector(".cl-state-pill");
  const costEl = node.querySelector(".cl-cost");
  const statusEl = node.querySelector(".cl-status");
  const btnGen = node.querySelector('[data-action="cl-generate"]');
  const btnRegen = node.querySelector('[data-action="cl-regenerate"]');
  const btnSave = node.querySelector('[data-action="cl-save"]');
  const btnApprove = node.querySelector('[data-action="cl-approve"]');
  const btnUnapprove = node.querySelector('[data-action="cl-unapprove"]');

  let approved = !!job.cover_letter_approved;
  let generations = job.cover_letter_generations || 0;
  let cumulativeCost = job.cover_letter_total_cost_eur || 0;

  function renderBullets(list) {
    if (!list || list.length === 0) {
      bullets.innerHTML = '<li class="muted small empty-row">No bullets yet.</li>';
      return;
    }
    bullets.innerHTML = list.map((b) => `<li>${escapeHtml(b)}</li>`).join("");
  }

  function fmtCost(eur) {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: eur < 1 ? 4 : 2,
      maximumFractionDigits: 4,
    }).format(Number(eur || 0));
  }

  function setState(state, label) {
    stateP.dataset.state = state || "";
    stateP.textContent = label;
  }

  function refreshCost() {
    if (generations > 0) {
      costEl.textContent = `${generations} generation${generations === 1 ? "" : "s"} · ${fmtCost(
        cumulativeCost,
      )} total`;
    } else {
      costEl.textContent = "";
    }
  }

  function setStatus(text, kind) {
    statusEl.textContent = text || "";
    statusEl.className = `cl-status muted small ${kind || ""}`;
  }

  function reflectApproved() {
    btnApprove.disabled = approved;
    btnUnapprove.disabled = !approved;
    if (approved) setState("approved", "Approved");
    else if (textarea.value.trim()) setState("draft", "Draft saved");
    else setState("", "No draft yet");
  }

  // Initial state from the job payload
  textarea.value = job.cover_letter || "";
  renderBullets(job.cover_letter_bullets);
  refreshCost();
  reflectApproved();

  async function streamGenerate({ force = false } = {}) {
    if (!force && approved) {
      if (!confirm("This cover letter is already approved. Overwrite the draft?")) return;
      force = true;
    }
    btnGen.disabled = true;
    btnRegen.disabled = true;
    btnSave.disabled = true;
    btnApprove.disabled = true;
    textarea.disabled = true;
    textarea.value = "";
    renderBullets(null);
    setState("streaming", "Streaming…");
    setStatus("Connecting to generator…");

    const url = `/api/jobs/${job.id}/generate${force ? "?force=true" : ""}`;
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      });
    } catch (e) {
      setState("error", "Failed");
      setStatus(`Network error: ${e.message}`, "err");
      finishGenerate();
      return;
    }
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (body.detail) detail = body.detail;
      } catch { /* not json */ }
      setState("error", "Failed");
      setStatus(detail, "err");
      finishGenerate();
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "message";
    let plainText = "";

    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          currentEvent = "message";
          let dataStr = "";
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) currentEvent = line.slice(6).trim();
            else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
          }
          if (!dataStr) continue;
          let payload = null;
          try { payload = JSON.parse(dataStr); } catch { /* not json */ }
          if (!payload) continue;

          if (currentEvent === "meta") {
            setStatus(`Streaming via ${payload.model}…`);
          } else if (currentEvent === "delta") {
            plainText += payload.text;
            // While streaming, show raw text (we don't know if it'll be JSON
            // until the end). Cheap heuristic: try to extract the cover_letter
            // field once we see a closing brace at the end.
            textarea.value = plainText;
            textarea.scrollTop = textarea.scrollHeight;
          } else if (currentEvent === "final") {
            textarea.value = payload.full_text || plainText;
            renderBullets(payload.bullets);
            generations = payload.generations;
            cumulativeCost = payload.total_cost_eur;
            refreshCost();
            approved = false;
            setState("draft", "Draft (unsaved)");
            setStatus(
              `Done. ${payload.prompt_tokens + payload.completion_tokens} tokens · ${fmtCost(payload.cost_eur)} this run.`,
              "ok",
            );
          } else if (currentEvent === "error") {
            setState("error", "Failed");
            setStatus(payload.detail || "Unknown error", "err");
          }
        }
      }
    } catch (e) {
      setState("error", "Failed");
      setStatus(`Stream error: ${e.message}`, "err");
    } finally {
      finishGenerate();
    }
  }

  function finishGenerate() {
    btnGen.disabled = false;
    btnRegen.disabled = !textarea.value;
    btnSave.disabled = false;
    btnApprove.disabled = approved;
    textarea.disabled = false;
  }

  async function save({ approve = false }) {
    const text = textarea.value.trim();
    if (!text) {
      setStatus("Cover letter is empty.", "err");
      return;
    }
    btnSave.disabled = true;
    btnApprove.disabled = true;
    setStatus(approve ? "Approving…" : "Saving draft…");
    try {
      const r = await api(`/api/jobs/${job.id}/cover-letter`, {
        method: "PUT",
        body: JSON.stringify({
          cover_letter: text,
          approved,
        }),
      });
      approved = r.approved;
      setStatus(approve ? "Approved." : "Draft saved.", "ok");
      reflectApproved();
    } catch (e) {
      setStatus(e.message, "err");
    } finally {
      btnSave.disabled = false;
      btnApprove.disabled = approved;
    }
  }

  async function unapprove() {
    btnUnapprove.disabled = true;
    setStatus("Unapproving…");
    try {
      const r = await api(`/api/jobs/${job.id}/cover-letter/unapprove`, { method: "POST" });
      approved = r.approved;
      setStatus("Unapproved.", "ok");
      reflectApproved();
    } catch (e) {
      setStatus(e.message, "err");
    }
  }

  btnGen.addEventListener("click", () => streamGenerate({}));
  btnRegen.addEventListener("click", () => streamGenerate({ force: true }));
  btnSave.addEventListener("click", () => save({ approve: false }));
  btnApprove.addEventListener("click", () => save({ approve: true }));
  btnUnapprove.addEventListener("click", () => unapprove());

  // Toggle Regenerate visibility once we have any text
  textarea.addEventListener("input", () => {
    btnRegen.disabled = !textarea.value;
    if (!approved) setState("draft", "Draft (unsaved)");
  });
}

function wireResearch(node, job) {
  const btnGo = node.querySelector('[data-action="research-go"]');
  const stateP = node.querySelector(".research-state-pill");
  const statusEl = node.querySelector(".research-status");
  const costEl = node.querySelector(".research-cost");
  const traceBlock = node.querySelector("#research-trace-block");
  const traceList = node.querySelector("#research-trace");
  const briefBlock = node.querySelector("#research-brief-block");

  function fmtCost(eur) {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: eur < 1 ? 4 : 2,
      maximumFractionDigits: 4,
    }).format(Number(eur || 0));
  }
  function setState(s, label) { stateP.dataset.state = s || ""; stateP.textContent = label; }
  function setStatus(t, k) { statusEl.textContent = t || ""; statusEl.className = `research-status muted small ${k || ""}`; }

  const existingBrief = job.company_brief || {};
  const existingTrace = job.research_trace || [];
  const existingIters = job.research_iterations || 0;
  const existingCost = job.research_total_cost_eur || 0;

  function renderBrief(brief, sources) {
    if (!brief || !brief.summary) {
      briefBlock.style.display = "none";
      return;
    }
    briefBlock.style.display = "";
    briefBlock.querySelector(".brief-summary").textContent = brief.summary;
    briefBlock.querySelector(".brief-what").textContent = brief.what_they_do || "—";
    briefBlock.querySelector(".brief-tech").innerHTML =
      (brief.tech_stack_signals || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("") ||
      '<li class="muted">No signals.</li>';
    const srcArr = (brief.sources && brief.sources.length) ? brief.sources : (sources || []);
    const linkify = (sourceIndex) => {
      const src = srcArr[sourceIndex];
      if (!src) return "";
      return ` <a href="${escapeHtml(src.url)}" target="_blank" rel="noreferrer">${escapeHtml(src.title || src.url)}</a>`;
    };
    briefBlock.querySelector(".brief-news").innerHTML =
      (brief.recent_news || []).map((n) => `<li>${escapeHtml(n.title)}${linkify(n.source_index)}</li>`).join("") ||
      '<li class="muted">None.</li>';
    briefBlock.querySelector(".brief-culture").innerHTML =
      (brief.culture_signals || []).map((c) => `<li>${escapeHtml(c.text)}${linkify(c.source_index)}</li>`).join("") ||
      '<li class="muted">None.</li>';
    const flagsList = brief.red_flags || [];
    const flagsSection = briefBlock.querySelector(".brief-red-flags");
    if (flagsList.length) {
      flagsSection.style.display = "";
      briefBlock.querySelector(".brief-flags").innerHTML =
        flagsList.map((f) => `<li>${escapeHtml(f.text)}${linkify(f.source_index)}</li>`).join("");
    } else {
      flagsSection.style.display = "none";
    }
    briefBlock.querySelector(".brief-sources").innerHTML = srcArr
      .map((s) => `<li><a href="${escapeHtml(s.url)}" target="_blank" rel="noreferrer">${escapeHtml(s.title || s.url)}</a></li>`)
      .join("");
  }

  function appendTraceItem(item) {
    traceBlock.style.display = "";
    const li = document.createElement("li");
    const action = (item.action || item.tool || item.kind || "").toString();
    const cls = ({
      plan: "plan", stop: "plan", search: "search", web_search: "search",
      fetch: "fetch", fetch_url: "fetch", synthesize: "synthesize", error: "error",
    })[action] || "plan";
    li.innerHTML = `
      <span class="t-iter">${item.iteration ?? ""}</span>
      <span class="t-action ${cls}">${escapeHtml(action)}</span>
      <span class="t-body">${item.body || ""}</span>
    `;
    traceList.appendChild(li);
    traceList.scrollIntoView({ block: "nearest" });
  }

  function renderExistingTrace(trace) {
    traceList.innerHTML = "";
    if (!trace.length) { traceBlock.style.display = "none"; return; }
    traceBlock.style.display = "";
    for (const t of trace) {
      const body =
        t.kind === "search" ? `query <code>${escapeHtml(t.query || "")}</code>` :
        t.kind === "fetch"  ? `<a href="${escapeHtml(t.url || "")}" target="_blank" rel="noreferrer">${escapeHtml(t.title || t.url || "")}</a>` :
        escapeHtml((t.summary || "").slice(0, 240));
      appendTraceItem({ iteration: t.iteration, action: t.kind, body });
    }
  }

  // Hydrate from existing data on row load
  if (existingIters > 0 || (existingBrief && existingBrief.summary)) {
    setState("ready", `Brief from ${new Date(job.research_at).toLocaleString()}`);
    costEl.textContent = `${existingIters} iter${existingIters === 1 ? "" : "s"} · ${fmtCost(existingCost)} total`;
    renderExistingTrace(existingTrace);
    renderBrief(existingBrief);
    btnGo.textContent = "Re-research";
  }

  btnGo.addEventListener("click", async () => {
    btnGo.disabled = true;
    setState("thinking", "Planning…");
    setStatus("Connecting to agent…");
    traceList.innerHTML = "";
    briefBlock.style.display = "none";
    traceBlock.style.display = "";

    let response;
    try {
      response = await fetch(`/api/jobs/${job.id}/research`, {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "text/event-stream" },
      });
    } catch (e) {
      setState("error", "Failed");
      setStatus(`Network error: ${e.message}`, "err");
      btnGo.disabled = false;
      return;
    }
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try { const b = await response.json(); if (b.detail) detail = b.detail; } catch {}
      setState("error", "Failed");
      setStatus(detail, "err");
      btnGo.disabled = false;
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let runningCost = 0;
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          let eventName = "message";
          let dataStr = "";
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
          }
          if (!dataStr) continue;
          let payload = null;
          try { payload = JSON.parse(dataStr); } catch { continue; }

          if (eventName === "meta") {
            setStatus(`Researching ${payload.company}…`);
          } else if (eventName === "plan") {
            runningCost += Number(payload.cost_eur || 0);
            costEl.textContent = `${payload.iteration} iter · ${fmtCost(runningCost)} so far`;
            setState("thinking", `Iteration ${payload.iteration}: ${payload.action}`);
            const body = `<em>${escapeHtml(payload.reason || "(no reason given)")}</em>` +
              (payload.action === "search" && payload.query ? ` — query <code>${escapeHtml(payload.query)}</code>` : "") +
              (payload.action === "fetch" && payload.url ? ` — <a href="${escapeHtml(payload.url)}" target="_blank" rel="noreferrer">${escapeHtml(payload.url)}</a>` : "");
            appendTraceItem({ iteration: payload.iteration, action: payload.action, body });
          } else if (eventName === "tool_result") {
            setState("acting", `Acting (${payload.tool})…`);
            let body;
            if (payload.tool === "web_search") {
              const top = (payload.hits || []).slice(0, 3).map((h) =>
                `<div><a href="${escapeHtml(h.url)}" target="_blank" rel="noreferrer">${escapeHtml(h.title || h.url)}</a></div>`,
              ).join("");
              body = (payload.error ? `<span class="muted">${escapeHtml(payload.error)}</span>` : top) ||
                '<span class="muted">No hits.</span>';
            } else {
              const link = `<a href="${escapeHtml(payload.url)}" target="_blank" rel="noreferrer">${escapeHtml(payload.title || payload.url)}</a>`;
              body = payload.error ? `${link} — <span class="muted">${escapeHtml(payload.error)}</span>` : link;
            }
            appendTraceItem({ iteration: payload.iteration, action: payload.tool, body });
          } else if (eventName === "synthesize") {
            setState("thinking", "Synthesising brief…");
            appendTraceItem({
              iteration: payload.iterations + 1,
              action: "synthesize",
              body: `Combining ${payload.iterations} observations into a structured brief.`,
            });
          } else if (eventName === "final") {
            runningCost = payload.total_cost_eur ?? (runningCost + (payload.cost_eur || 0));
            setState("ready", "Brief ready");
            setStatus(`Done. ${payload.iterations} iterations · ${fmtCost(payload.cost_eur)} this run.`, "ok");
            costEl.textContent = `${payload.iterations} iter · ${fmtCost(runningCost)} total`;
            renderBrief(payload.brief);
            btnGo.textContent = "Re-research";
          } else if (eventName === "error") {
            setState("error", "Failed");
            setStatus(payload.detail || "Unknown error", "err");
          }
        }
      }
    } catch (e) {
      setState("error", "Failed");
      setStatus(`Stream error: ${e.message}`, "err");
    } finally {
      btnGo.disabled = false;
    }
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
}

els.filterStatus.addEventListener("change", loadList);
els.filterSource.addEventListener("change", loadList);
els.refresh.addEventListener("click", loadList);

loadList();
