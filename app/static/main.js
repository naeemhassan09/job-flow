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

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
}

els.filterStatus.addEventListener("change", loadList);
els.filterSource.addEventListener("change", loadList);
els.refresh.addEventListener("click", loadList);

loadList();
