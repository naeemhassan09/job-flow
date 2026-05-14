// Usage page — pulls from /api/usage/* and renders summary cards + tables.

const fmt = {
  eur: (n) =>
    new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: n < 1 ? 4 : 2,
      maximumFractionDigits: 4,
    }).format(Number(n || 0)),
  int: (n) => new Intl.NumberFormat().format(Math.round(Number(n || 0))),
  pct: (n) => `${(Number(n || 0) * 100).toFixed(1)}%`,
  when: (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    const today = new Date();
    const sameDay = d.toDateString() === today.toDateString();
    return sameDay
      ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : d.toLocaleString([], { dateStyle: "short", timeStyle: "short" });
  },
  monthLabel: (iso) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString([], { month: "long", day: "numeric" });
  },
};

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function loadMonthly() {
  try {
    const s = await api("/api/usage/monthly");
    document.getElementById("mtd-spend").textContent = fmt.eur(s.spend_eur);
    document.getElementById("mtd-cap").textContent = `of ${fmt.eur(s.monthly_cap_eur)} cap`;
    const meter = document.getElementById("mtd-meter");
    const pct = Math.min(100, Math.max(0, s.spent_pct));
    meter.style.width = `${pct}%`;
    meter.classList.remove("warn", "err");
    if (s.spent_pct >= 100) meter.classList.add("err");
    else if (s.spent_pct >= 70) meter.classList.add("warn");

    document.getElementById("mtd-calls").textContent = fmt.int(s.calls);
    document.getElementById("month-start").textContent = fmt.monthLabel(s.month_start);

    document.getElementById("mtd-tokens").textContent = fmt.int(s.total_tokens);
    document.getElementById("mtd-cached").textContent = fmt.int(s.cached_tokens);
    document.getElementById("mtd-cache-rate").textContent = fmt.pct(s.cache_hit_rate);
  } catch (e) {
    document.getElementById("mtd-spend").textContent = "error";
  }
}

async function loadByModel() {
  const tbody = document.getElementById("by-model-rows");
  try {
    const rows = await api("/api/usage/by-model");
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-row">No calls yet this month.</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
        <tr>
          <td><span class="provider-pill">${r.provider}</span></td>
          <td class="model">${r.model}</td>
          <td class="num">${fmt.int(r.calls)}</td>
          <td class="num">${fmt.int(r.tokens)}</td>
          <td class="num">${fmt.eur(r.spend_eur)}</td>
        </tr>`,
      )
      .join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Error: ${e.message}</td></tr>`;
  }
}

async function loadByNode() {
  const tbody = document.getElementById("by-node-rows");
  try {
    const rows = await api("/api/usage/by-node");
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-row">No calls yet this month.</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
        <tr>
          <td><strong>${r.node}</strong></td>
          <td class="num">${fmt.int(r.calls)}</td>
          <td class="num">${fmt.int(r.tokens)}</td>
          <td class="num">${fmt.eur(r.spend_eur)}</td>
          <td class="num">${fmt.int(r.avg_latency_ms)}</td>
        </tr>`,
      )
      .join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Error: ${e.message}</td></tr>`;
  }
}

async function loadRecent() {
  const tbody = document.getElementById("recent-rows");
  try {
    const rows = await api("/api/usage/recent?limit=30");
    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="empty-row">No calls recorded yet. Score or generate something.</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
        <tr>
          <td class="when">${fmt.when(r.created_at)}</td>
          <td>${r.node || "—"}</td>
          <td class="model">${r.model}</td>
          <td class="num">${fmt.int(r.total_tokens)}</td>
          <td class="num">${fmt.eur(r.cost_eur)}</td>
          <td class="num">${fmt.int(r.latency_ms)}</td>
        </tr>`,
      )
      .join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">Error: ${e.message}</td></tr>`;
  }
}

function loadAll() {
  loadMonthly();
  loadByModel();
  loadByNode();
  loadRecent();
}

document.getElementById("refresh").addEventListener("click", loadAll);
loadAll();
