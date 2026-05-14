// Dashboard — pulls /api/stats/dashboard and renders KPIs + bars + tables.

const fmt = {
  int: (n) => new Intl.NumberFormat().format(Math.round(Number(n || 0))),
  pct: (n) => `${(Number(n || 0) * 100).toFixed(0)}%`,
  fit: (n) => (n == null ? "—" : Math.round(Number(n)).toString()),
  date: (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: "numeric", month: "short" }) : "—"),
  when: (iso) => (iso ? new Date(iso).toLocaleDateString([], { dateStyle: "medium" }) : "—"),
};

async function api(path) {
  const r = await fetch(path, { credentials: "same-origin" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// Display order for the status bars — pipeline left-to-right.
const STATUS_ORDER = [
  "bookmarked",
  "applied",
  "screening",
  "interview",
  "offer",
  "accepted",
  "rejected",
  "ghosted",
  "withdrawn",
  "not_applying",
  "untriaged",
];

function render(data) {
  document.getElementById("total-jobs").textContent = fmt.int(data.total_jobs);
  document.getElementById("open-pipeline").textContent = fmt.int(data.open_pipeline);

  const rr = document.getElementById("response-rate");
  const rrDetail = document.getElementById("response-rate-detail");
  if (data.response_rate == null) {
    rr.textContent = "—";
    rrDetail.textContent = "no applications yet";
  } else {
    rr.textContent = fmt.pct(data.response_rate);
    rrDetail.textContent = `${fmt.int(data.responded_total)} responded of ${fmt.int(data.applied_total)}`;
  }

  document.getElementById("avg-fit").textContent = fmt.fit(data.avg_fit_applied);

  // Status bars
  const bars = document.getElementById("status-bars");
  const max = Math.max(1, ...Object.values(data.by_status || {}));
  const entries = STATUS_ORDER
    .map((s) => [s, (data.by_status || {})[s] || 0])
    .filter(([_, n]) => n > 0 || ["bookmarked", "applied", "interview", "offer", "rejected"].includes(_));
  if (entries.every(([, n]) => n === 0)) {
    bars.innerHTML = '<div class="empty-row muted small">No jobs tracked yet. Set a status from the Inbox.</div>';
  } else {
    bars.innerHTML = entries
      .map(([s, n]) => `
        <div class="status-bar">
          <span class="status-bar-label">${s.replace(/_/g, " ")}</span>
          <span class="status-bar-track"><span class="status-bar-fill ${s}" style="width:${(n / max) * 100}%"></span></span>
          <span class="status-bar-count">${n}</span>
        </div>`)
      .join("");
  }

  // Weekly bar chart
  const chart = document.getElementById("weekly-chart");
  const weeks = data.applied_per_week || [];
  if (weeks.length === 0) {
    chart.innerHTML = '<div class="empty-row muted small">No applications dated yet.</div>';
  } else {
    const maxW = Math.max(1, ...weeks.map((w) => w.count));
    chart.innerHTML = weeks
      .map((w) => `
        <div class="chart-col">
          <span class="chart-value">${w.count}</span>
          <div class="chart-bar" style="height:${(w.count / maxW) * 160}px"></div>
          <span class="chart-label">${fmt.date(w.week_start)}</span>
        </div>`)
      .join("");
  }

  // Top companies
  const tc = document.getElementById("top-companies");
  if (!data.top_companies_applied?.length) {
    tc.innerHTML = '<tr><td colspan="2" class="empty-row muted small">None yet.</td></tr>';
  } else {
    tc.innerHTML = data.top_companies_applied
      .map((c) => `<tr><td>${escapeHtml(c.company || "—")}</td><td class="num">${c.count}</td></tr>`)
      .join("");
  }

  // Stale follow-ups
  const stale = document.getElementById("stale-followups");
  if (!data.stale_followups?.length) {
    stale.innerHTML = '<tr><td colspan="4" class="empty-row muted small">Nothing waiting on response &gt; 14 days. 👍</td></tr>';
  } else {
    stale.innerHTML = data.stale_followups
      .map((s) => `
        <tr>
          <td><a href="/ui/?job=${s.id}">${escapeHtml(s.title || "—")}</a></td>
          <td>${escapeHtml(s.company || "—")}</td>
          <td><span class="app-status-pill ${s.status}">${s.status}</span></td>
          <td class="num">${fmt.when(s.status_updated_at)}</td>
        </tr>`)
      .join("");
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
}

async function load() {
  try {
    const data = await api("/api/stats/dashboard");
    render(data);
  } catch (e) {
    document.getElementById("total-jobs").textContent = "error";
    document.getElementById("status-bars").innerHTML = `<div class="empty-row muted small">Error: ${e.message}</div>`;
  }
}

document.getElementById("refresh").addEventListener("click", load);
load();
