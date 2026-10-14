/* AI Data Quality Intelligence Platform — single-page dashboard (no external dependencies). */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const fmt = (n, d = 1) =>
    n == null || n === ""
      ? "—"
      : typeof n === "number"
        ? n.toLocaleString(undefined, { maximumFractionDigits: d })
        : esc(n);
  const NA = "Not available — insufficient data";
  const SEV = {
    LOW: "#0ea5e9",
    MEDIUM: "#f59e0b",
    HIGH: "#f97316",
    CRITICAL: "#dc2626",
  };
  const pill = (t, cls) =>
    `<span class="pill ${esc(cls || t)}">${esc(t)}</span>`;
  const state = {
    analysisId: null,
    result: null,
    uploaded: null,
    datasets: [],
    filterSev: "ALL",
  };

  /* ---------------------------------------------------------------- API */
  async function api(path, opts = {}) {
    const init = { method: opts.method || "GET", headers: {} };
    if (opts.json !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.json);
    }
    if (opts.form) init.body = opts.form;
    let res;
    try {
      res = await fetch(path, init);
    } catch (e) {
      throw new Error("Cannot reach the server. Is it running?");
    }
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      /* non-JSON */
    }
    if (!res.ok)
      throw new Error(
        (data && data.error && data.error.message) ||
          `Request failed (${res.status}).`,
      );
    return data;
  }
  function toast(msg, kind = "") {
    const t = document.createElement("div");
    t.className = "toast " + kind;
    t.textContent = msg;
    $("#toasts").appendChild(t);
    setTimeout(() => t.remove(), 4800);
  }
  const guard =
    (fn) =>
    async (...a) => {
      try {
        return await fn(...a);
      } catch (e) {
        toast(e.message, "bad");
        console.error(e);
      }
    };

  /* ------------------------------------------------------------- charts */
  function lineChart({
    labels,
    series,
    min = null,
    max = null,
    height = 210,
    band = null,
    minSpan = 0,
    clamp = null,
  }) {
    const W = 560,
      H = height,
      L = 38,
      R = 12,
      T = 12,
      B = 26;
    const all = series
      .flatMap((s) => s.values)
      .concat(band ? band.lower.concat(band.upper) : [])
      .filter((v) => v != null);
    if (!all.length) return `<div class="empty">${NA}</div>`;
    let lo = min ?? Math.min(...all),
      hi = max ?? Math.max(...all);
    if (hi - lo < minSpan) {
      const mid = (hi + lo) / 2;
      lo = mid - minSpan / 2;
      hi = mid + minSpan / 2;
    }
    if (lo === hi) {
      if (lo >= 0) {
        lo = 0;
        hi = Math.max(1, hi + 1);
      } else {
        lo -= 1;
        hi += 1;
      }
    }
    const pad = (hi - lo) * 0.08;
    if (min == null) lo -= pad;
    if (max == null) hi += pad;
    if (clamp) {
      lo = Math.max(lo, clamp[0]);
      hi = Math.min(hi, clamp[1]);
    }
    const n = labels.length,
      x = (i) => L + (n === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (n - 1));
    const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
    let g = "";
    for (let k = 0; k <= 4; k++) {
      const v = lo + ((hi - lo) * k) / 4,
        yy = y(v);
      g += `<line x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}" stroke="#e8edf5"/><text x="${L - 5}" y="${yy + 3}" text-anchor="end">${fmt(v, hi - lo < 10 ? 1 : 0)}</text>`;
    }
    const step = Math.ceil(n / 8);
    labels.forEach((l, i) => {
      if (i % step === 0 || i === n - 1)
        g += `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${esc(l)}</text>`;
    });
    if (band) {
      const up = band.upper
        .map((v, i) => (v == null ? null : `${x(i + band.offset)},${y(v)}`))
        .filter(Boolean);
      const dn = band.lower
        .map((v, i) => (v == null ? null : `${x(i + band.offset)},${y(v)}`))
        .filter(Boolean)
        .reverse();
      g += `<polygon points="${up.concat(dn).join(" ")}" fill="${band.color}" opacity=".15"/>`;
    }
    series.forEach((s) => {
      let d = "",
        pen = false;
      s.values.forEach((v, i) => {
        if (v == null) {
          pen = false;
          return;
        }
        d += `${pen ? "L" : "M"}${x(i + (s.offset || 0))},${y(v)}`;
        pen = true;
      });
      g += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.4" ${s.dash ? 'stroke-dasharray="6 5"' : ""} stroke-linejoin="round"/>`;
      s.values.forEach((v, i) => {
        if (v != null)
          g += `<circle cx="${x(i + (s.offset || 0))}" cy="${y(v)}" r="3.2" fill="${s.color}"><title>${esc(s.name)}: ${fmt(v, 2)}</title></circle>`;
      });
    });
    const legend =
      series.length > 1
        ? `<div class="legend">${series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}</div>`
        : "";
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img">${g}</svg>${legend}`;
  }
  function hbars(
    items,
    { max = 100, color = "var(--brand)", suffix = "" } = {},
  ) {
    if (!items.length) return `<div class="empty">${NA}</div>`;
    return items
      .map(
        (i) =>
          `<div class="hb"><span title="${esc(i.label)}">${esc(i.label)}</span><div class="bar"><i style="width:${Math.max(0, Math.min(100, (i.value / max) * 100))}%;background:${i.color || color}"></i></div><b>${fmt(i.value, 1)}${suffix}</b></div>`,
      )
      .join("");
  }
  function donut(items) {
    const total = items.reduce((a, i) => a + i.value, 0);
    if (!total)
      return `<div class="empty"><span class="big">✓</span>No anomalies reported</div>`;
    const R = 54,
      C = 2 * Math.PI * R;
    let off = 0;
    const arcs = items
      .filter((i) => i.value)
      .map((i) => {
        const len = (i.value / total) * C;
        const s = `<circle r="${R}" cx="70" cy="70" fill="none" stroke="${i.color}" stroke-width="22" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}" transform="rotate(-90 70 70)"><title>${esc(i.label)}: ${i.value}</title></circle>`;
        off += len;
        return s;
      })
      .join("");
    return `<div class="row" style="justify-content:center"><svg viewBox="0 0 140 140" width="150">${arcs}<text x="70" y="68" text-anchor="middle" style="font-size:22px;font-weight:800;fill:#17202e">${fmt(total, 0)}</text><text x="70" y="84" text-anchor="middle">anomalies</text></svg>
  <div class="legend" style="flex-direction:column">${items.map((i) => `<span><i style="background:${i.color}"></i>${esc(i.label)}: <b>${fmt(i.value, 0)}</b></span>`).join("")}</div></div>`;
  }
  function ring(score, label) {
    const R = 52,
      C = 2 * Math.PI * R,
      v = Math.max(0, Math.min(100, score || 0));
    const col =
      v >= 90
        ? "#4ade80"
        : v >= 75
          ? "#a3e635"
          : v >= 50
            ? "#fbbf24"
            : "#f87171";
    return `<svg class="gauge" viewBox="0 0 130 130" width="132"><circle cx="65" cy="65" r="${R}" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="12"/>
  <circle cx="65" cy="65" r="${R}" fill="none" stroke="${col}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${(v / 100) * C} ${C}" transform="rotate(-90 65 65)"/>
  <text x="65" y="66" text-anchor="middle" style="font-size:28px;font-weight:800;fill:#fff">${fmt(score, 1)}</text><text x="65" y="84" text-anchor="middle" style="fill:#c7d2fe;font-size:11px">${esc(label)}</text></svg>`;
  }
  function distChart(dist) {
    if (!dist) return "";
    const labels =
      dist.type === "numeric"
        ? dist.reference.map((_, i) => `${fmt(dist.edges[i], 2)}`)
        : dist.labels;
    const W = 560,
      H = 190,
      L = 34,
      B = 34,
      T = 10,
      n = labels.length,
      bw = (W - L - 8) / n;
    const mx = Math.max(...dist.reference, ...dist.current, 0.01);
    let g = "";
    labels.forEach((l, i) => {
      const h1 = (dist.reference[i] / mx) * (H - T - B),
        h2 = (dist.current[i] / mx) * (H - T - B),
        x0 = L + i * bw;
      g += `<rect x="${x0 + 2}" y="${H - B - h1}" width="${bw / 2 - 2}" height="${h1}" fill="#94a3b8"><title>reference ${(dist.reference[i] * 100).toFixed(1)}%</title></rect>
    <rect x="${x0 + bw / 2}" y="${H - B - h2}" width="${bw / 2 - 2}" height="${h2}" fill="#4f46e5"><title>current ${(dist.current[i] * 100).toFixed(1)}%</title></rect>
    <text x="${x0 + bw / 2}" y="${H - 20}" text-anchor="middle">${esc(String(l).slice(0, 9))}</text>`;
    });
    return `<svg class="chart" viewBox="0 0 ${W} ${H}">${g}</svg><div class="legend"><span><i style="background:#94a3b8"></i>Reference</span><span><i style="background:#4f46e5"></i>Current</span></div>`;
  }
  const empty = (icon, title, body, cta = "") =>
    `<div class="card empty"><span class="big">${icon}</span><h3>${esc(title)}</h3><p>${body}</p>${cta}</div>`;
  const table = (heads, rows, cls = "") =>
    `<div class="tablewrap"><table class="${cls}"><thead><tr>${heads.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;

  /* ------------------------------------------------------------- shell */
  const NAV = [
    [
      "Overview",
      [
        ["dashboard", "▦", "Dashboard"],
        ["datasets", "🗂", "Datasets"],
        ["upload", "⬆", "Upload Dataset"],
        ["analysis", "🧠", "Analysis"],
      ],
    ],
    [
      "Insights",
      [
        ["quality", "✔", "Data Quality"],
        ["anomalies", "⚠", "Anomalies"],
        ["explanations", "💡", "AI Explanations"],
        ["recommendations", "★", "Recommendations"],
        ["remediation", "🛠", "Remediation"],
      ],
    ],
    [
      "Monitoring",
      [
        ["drift", "≋", "Drift Monitoring"],
        ["alerts", "🔔", "Alerts"],
        ["trends", "📈", "Trends"],
        ["forecast", "🔮", "Forecast"],
        ["history", "🕘", "History"],
      ],
    ],
  ];
  const TITLES = {};
  function buildNav() {
    $("#nav").innerHTML = NAV.map(
      ([g, items]) =>
        `<div class="grp">${g}</div>` +
        items
          .map(([id, ic, label]) => {
            TITLES[id] = label;
            return `<a href="#/${id}" data-id="${id}"><span>${ic}</span>${label}<span class="badge hidden" id="badge-${id}"></span></a>`;
          })
          .join(""),
    ).join("");
  }
  async function refreshPicker() {
    const d = await api("/api/analysis?limit=100");
    const done = d.analyses.filter((a) => a.status === "COMPLETED");
    const sel = $("#analysisPicker");
    sel.innerHTML = done.length
      ? done
          .map(
            (a) =>
              `<option value="${a.id}">#${a.id} · ${esc(a.dataset)} · Q ${fmt(a.quality_score, 1)}</option>`,
          )
          .join("")
      : `<option value="">No analyses yet</option>`;
    if (done.length) {
      if (!state.analysisId || !done.find((a) => a.id === state.analysisId))
        state.analysisId = done[0].id;
      sel.value = state.analysisId;
    }
  }
  async function getResult(force = false) {
    if (!state.analysisId) return null;
    if (!force && state.result && state.result.analysis.id === state.analysisId)
      return state.result;
    state.result = await api(`/api/analysis/${state.analysisId}`);
    const b = $("#badge-alerts");
    if (b) {
      const n = (state.result.alerts || []).length;
      b.textContent = n;
      b.classList.toggle("hidden", !n);
    }
    return state.result;
  }
  const needAnalysis = () =>
    empty(
      "📊",
      "No analysis yet",
      "Upload a dataset and click <b>Analyze Dataset</b> to see results here.",
      `<p><a class="btn primary" href="#/upload">Upload a dataset</a></p>`,
    );

  async function router() {
    const id = (location.hash.replace(/^#\//, "") || "dashboard").split("?")[0];
    const view = VIEWS[id] ? id : "dashboard";
    document
      .querySelectorAll("#nav a")
      .forEach((a) => a.classList.toggle("active", a.dataset.id === view));
    $("#pageTitle").textContent = TITLES[view];
    $("#pageSub").textContent = "";
    $("#sidebar").classList.remove("open");
    const el = $("#view");
    el.innerHTML = `<div class="empty">Loading…</div>`;
    try {
      await VIEWS[view](el);
    } catch (e) {
      el.innerHTML = `<div class="notice bad"><b>Something went wrong.</b> ${esc(e.message)}</div>`;
    }
  }

  /* ---------------------------------------------------------- dashboard */
  const kpi = (label, value, sub, accent) =>
    `<div class="card kpi" style="--accent:${accent}"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub || ""}</div></div>`;
  const riskColor = (l) =>
    ({
      LOW: "#16a34a",
      MEDIUM: "#f59e0b",
      HIGH: "#f97316",
      CRITICAL: "#dc2626",
    })[l] || "#64748b";
  function trendChart(series, key, color, name, opts = {}) {
    const pts = series.filter((p) => p[key] != null);
    if (pts.length < 2)
      return `<div class="empty">${NA}<br><small>Needs at least 2 analyses of the same dataset series.</small></div>`;
    return lineChart({
      labels: series.map((p, i) => `#${p.analysis_id ?? i + 1}`),
      series: [{ name, color, values: series.map((p) => p[key]) }],
      ...opts,
    });
  }
  const VIEWS = {};
  VIEWS.dashboard = async (el) => {
    const d = await api(
      "/api/dashboard/summary" +
        (state.analysisId ? `?analysis_id=${state.analysisId}` : ""),
    );
    if (!d.has_data) {
      el.innerHTML = needAnalysis();
      return;
    }
    state.analysisId = d.analysis.id;
    $("#analysisPicker").value = state.analysisId;
    const h = d.health,
      p = d.profile,
      a = d.anomalies,
      dr = d.drift,
      m = d.monitoring,
      f = d.forecast,
      ch = d.charts;
    $("#pageSub").textContent =
      `${d.dataset.name} · analysis #${d.analysis.id}`;
    const b = $("#badge-alerts");
    if (b) {
      b.textContent = d.alerts.active;
      b.classList.toggle("hidden", !d.alerts.active);
    }
    const trendPill =
      m.trend && m.trend !== "INSUFFICIENT DATA"
        ? pill(m.trend)
        : `<span class="pill SKIPPED" title="${NA}">no history yet</span>`;
    el.innerHTML = `<div class="stack">
  <div class="card hero">${ring(h.quality_score, "QUALITY")}<div class="meta">
    <div class="row">${pill(h.overall_status, h.risk_level === "LOW" ? "HEALTHY" : h.risk_level)}<span class="pill">${esc(h.priority)}</span><span class="pill" title="Quality score grade; risk also weighs anomalies, drift and alerts">Data quality: ${esc(h.quality_grade)}</span></div>
    <h2>${esc(h.decision)}</h2><p>${esc(h.recommended_action)}</p>
    <p class="small">${h.main_drivers.length ? "Main drivers: " + h.main_drivers.map(esc).join(" · ") : "No risk drivers identified."}</p>
    <p class="small">${esc(h.automation)}</p></div></div>
  <div class="grid g4">
    ${kpi("Overall Quality Score", fmt(h.quality_score, 1) + "%", esc(h.quality_grade), "#4f46e5")}
    ${kpi("Risk Score", fmt(h.risk_score, 1), pill(h.risk_level), riskColor(h.risk_level))}
    ${kpi("Anomalies", fmt(a.total, 0), `${fmt(a.pct, 2)}% of rows` + (a.ml_status === "SKIPPED" ? " · ML skipped" : ""), "#f59e0b")}
    ${kpi("Critical Issues", fmt(a.critical, 0), `${fmt(a.high, 0)} high-severity`, "#dc2626")}
    ${kpi("Missing Values", fmt(p.missing_values, 0), `${fmt(p.rows, 0)} rows × ${p.columns} cols`, "#0ea5e9")}
    ${kpi("Duplicate Records", fmt(p.duplicate_rows, 0), `${fmt(p.invalid_rows, 0)} rows with invalid values`, "#8b5cf6")}
    ${kpi("Drifted Features", dr.available ? fmt(dr.drifted_features, 0) : "—", dr.available ? esc(dr.overall_status) : `<span title="${esc(dr.message)}">Not available</span>`, "#14b8a6")}
    ${kpi("Active Alerts", fmt(d.alerts.active, 0), '<a href="#/alerts">View alerts →</a>', "#ef4444")}
  </div>
  <div class="grid g3">
    <div class="card"><h3>Severity Distribution</h3>${donut(["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((k) => ({ label: k, value: ch.severity_distribution[k] || 0, color: SEV[k] })))}</div>
    <div class="card"><h3>Quality Dimensions</h3>${hbars(
      Object.entries(ch.dimensions).map(([k, v]) => ({ label: k, value: v })),
      { max: 100 },
    )}</div>
    <div class="card"><h3>Feature Quality <small>lowest first</small></h3>${hbars(
      [...ch.feature_quality]
        .sort((x, y) => x.score - y.score)
        .slice(0, 8)
        .map((c) => ({
          label: c.column,
          value: c.score,
          color:
            c.score >= 90 ? "#16a34a" : c.score >= 70 ? "#f59e0b" : "#dc2626",
        })),
    )}</div>
  </div>
  <div class="grid g3">
    <div class="card"><h3>Quality Trend ${trendPill}</h3>${trendChart(ch.trend_series, "quality_score", "#4f46e5", "Quality", { clamp: [0, 100], minSpan: 10 })}</div>
    <div class="card"><h3>Anomaly Trend</h3>${trendChart(ch.trend_series, "anomaly_count", "#f59e0b", "Anomalies")}</div>
    <div class="card"><h3>Risk Trend</h3>${trendChart(ch.trend_series, "risk_score", "#dc2626", "Risk", { clamp: [0, 100], minSpan: 10 })}</div>
  </div>
  <div class="grid g2">
    <div class="card"><h3>Drift Overview <small>PSI per feature</small></h3>${
      dr.available
        ? hbars(
            ch.drift_overview.map((x) => ({
              label: x.feature,
              value: x.psi,
              color:
                x.status === "NO DRIFT"
                  ? "#16a34a"
                  : x.status === "MODERATE DRIFT"
                    ? "#f59e0b"
                    : "#dc2626",
            })),
            { max: 0.5 },
          )
        : `<div class="empty">${esc(dr.message)}</div>`
    }</div>
    <div class="card"><h3>Forecast</h3>${f.available ? forecastBlock(f.series, ch.trend_series) : `<div class="empty">${esc(f.message || NA)}</div>`}</div>
  </div>
  <div class="grid g2">
    <div class="card"><h3>AI Insights</h3><ul class="list">${d.insights.map((i) => `<li>💡 ${esc(i)}</li>`).join("")}</ul>
      <p class="small muted">Monitoring: previous quality ${fmt(m.previous_quality, 1)} → current ${fmt(m.current_quality, 1)} · trend ${m.trend === "INSUFFICIENT DATA" ? "not available yet" : esc(m.trend)}. ${esc(m.message)}</p></div>
    <div class="card"><h3>Top Recommendations <a class="small" href="#/recommendations" style="margin-left:auto">All →</a></h3><ol class="list" style="padding-left:1.1rem">${d.top_recommendations.map((r) => `<li>${pill(r.priority, r.severity)} <b>${esc(r.target)}</b> — ${esc(r.recommendation)}</li>`).join("")}</ol></div>
  </div>
  <div class="grid g2">
    <div class="card"><h3>Remediation</h3><p class="muted">${d.remediation.safe_fixes.length ? d.remediation.safe_fixes.map((x) => `${esc(x.label)} (${fmt(x.affected, 0)} ${x.unit})`).join(" · ") : "No safe automated fixes needed."}</p>
      <div class="row"><a class="btn" href="#/remediation">Preview Changes</a><button class="btn primary" id="applySafe">Apply Safe Fixes</button><button class="btn" id="dlClean">Download Cleaned Dataset</button></div>
      <p class="small muted">Your original file is never modified — fixes are applied to a cleaned copy.</p></div>
    <div class="card"><h3>Reports</h3><div class="row">${d.reports.map((r) => `<a class="btn small" href="${r.url}">⬇ ${esc(r.name.replace(/_/g, " "))}</a>`).join("")}</div></div>
  </div></div>`;
    $("#applySafe").onclick = guard(async () => {
      const r = await api(`/api/analysis/${d.analysis.id}/remediation/apply`, {
        method: "POST",
        json: {},
      });
      toast(
        `Safe fixes applied: ${r.cells_changed} cells changed, ${r.rows_removed} rows removed. Quality ${fmt(r.before.quality_score, 1)} → ${fmt(r.after.quality_score, 1)}`,
        "ok",
      );
    });
    $("#dlClean").onclick = guard(async () => {
      const rem = await api(`/api/analysis/${d.analysis.id}/remediation`);
      if (!rem.applied)
        await api(`/api/analysis/${d.analysis.id}/remediation/apply`, {
          method: "POST",
          json: {},
        });
      location.href = `/api/analysis/${d.analysis.id}/remediation/download`;
    });
  };
  function forecastBlock(fc, series) {
    const hist = series.filter((p) => p.quality_score != null),
      n = hist.length,
      k = fc.quality_score.length;
    const labels = hist
      .map((p) => `#${p.analysis_id}`)
      .concat(fc.quality_score.map((p) => `+${p.period}`));
    const q = hist.map((p) => p.quality_score);
    const pad = Array(n - 1).fill(null);
    return (
      lineChart({
        labels,
        clamp: [0, 100],
        minSpan: 10,
        series: [
          { name: "Quality (history)", color: "#4f46e5", values: q },
          {
            name: "Quality (forecast)",
            color: "#4f46e5",
            dash: true,
            values: [q[n - 1], ...fc.quality_score.map((p) => p.value)],
            offset: n - 1,
          },
        ],
        band: {
          lower: [q[n - 1], ...fc.quality_score.map((p) => p.lower)],
          upper: [q[n - 1], ...fc.quality_score.map((p) => p.upper)],
          offset: n - 1,
          color: "#4f46e5",
        },
      }) +
      `<p class="small muted">Next ${k} runs · forecast quality <b>${fmt(fc.quality_score[k - 1].value, 1)}</b>${fc.risk_score ? ` · forecast risk <b>${fmt(fc.risk_score[k - 1].value, 1)}</b>` : ""}</p>`
    );
  }

  /* ------------------------------------------------------------- upload */
  async function startAnalysis(datasetId, referenceId) {
    const body = { auto_reference: true };
    if (referenceId) body.reference_dataset_id = Number(referenceId);
    const r = await api(`/api/analyze/${datasetId}`, {
      method: "POST",
      json: body,
    });
    const ov = $("#overlay");
    ov.classList.remove("hidden");
    $("#ovBar").style.width = "2%";
    $("#ovStep").textContent = "Queued…";
    for (;;) {
      await new Promise((r2) => setTimeout(r2, 450));
      const s = await api(`/api/analysis/${r.analysis_id}/status`);
      $("#ovBar").style.width = Math.max(3, s.progress) + "%";
      $("#ovStep").textContent =
        `${s.current_step || "Working"} (${s.progress}%)`;
      if (s.status === "FAILED") {
        ov.classList.add("hidden");
        throw new Error(s.error || "The analysis failed.");
      }
      if (s.status === "COMPLETED") break;
    }
    $("#overlay").classList.add("hidden");
    state.analysisId = r.analysis_id;
    state.result = null;
    await refreshPicker();
    toast("Analysis complete", "ok");
    location.hash = "#/dashboard";
  }
  VIEWS.upload = async (el) => {
    const ds = (await api("/api/datasets")).datasets;
    state.datasets = ds;
    el.innerHTML = `<div class="stack"><div class="card"><h3>Upload a dataset</h3>
    <label class="dropzone" id="drop" for="file" style="display:block"><span class="big">⬆</span><p><b>Drop a file here</b> or click to browse</p><p class="muted small">CSV · XLSX · XLS · PDF (with tables) — up to the server upload limit</p></label>
    <input type="file" id="file" accept=".csv,.xlsx,.xls,.pdf" class="hidden"><div id="upMsg"></div></div><div id="after"></div></div>`;
    const handle = guard(async (file) => {
      if (!file) return;
      $("#upMsg").innerHTML =
        `<p class="muted">Uploading and validating <b>${esc(file.name)}</b>…</p>`;
      const form = new FormData();
      form.append("file", file);
      let r;
      try {
        r = await api("/api/datasets/upload", { method: "POST", form });
      } catch (e) {
        $("#upMsg").innerHTML =
          `<div class="notice bad"><b>Upload failed.</b> ${esc(e.message)}</div>`;
        return;
      }
      state.uploaded = r;
      $("#upMsg").innerHTML = "";
      const v = r.validation,
        cands = (await api("/api/datasets")).datasets.filter(
          (x) => x.id !== r.dataset.id,
        );
      $("#after").innerHTML =
        `<div class="card"><h3>✅ File validated <small>${esc(r.dataset.name)} · ${esc(r.dataset.file_type.toUpperCase())}</small></h3>
      <div class="grid g4">${kpi("Rows", fmt(v.rows, 0), "", "#4f46e5")}${kpi("Columns", v.columns, "", "#0ea5e9")}${kpi("Missing cells", fmt(v.missing_values, 0), "", "#f59e0b")}${kpi("Duplicate rows", fmt(v.duplicate_rows, 0), "", "#8b5cf6")}</div>
      ${v.warnings.map((w) => `<div class="notice" style="margin-top:.7rem">⚠ ${esc(w)}</div>`).join("")}
      <h3 style="margin-top:1rem">Preview <small>first ${r.preview.rows.length} rows</small></h3>
      ${table(
        r.preview.columns,
        r.preview.rows.map(
          (row) =>
            `<tr>${row.map((c) => `<td>${c == null ? '<span class="muted">—</span>' : esc(c)}</td>`).join("")}</tr>`,
        ),
      )}
      <div class="row" style="margin-top:1rem"><label class="small muted">Reference dataset for drift (optional)<br>
        <select id="refSel"><option value="">Auto (previous upload of this file name, if any)</option>${cands.map((c) => `<option value="${c.id}">#${c.id} ${esc(c.name)} (${fmt(c.rows, 0)} rows)</option>`).join("")}</select></label>
        <button class="btn primary" id="goAnalyze" style="margin-left:auto">▶ Analyze Dataset</button></div></div>`;
      $("#goAnalyze").onclick = guard(async () => {
        $("#goAnalyze").disabled = true;
        try {
          await startAnalysis(r.dataset.id, $("#refSel").value);
        } finally {
          const b = $("#goAnalyze");
          if (b) b.disabled = false;
        }
      });
    });
    const drop = $("#drop");
    $("#file").onchange = (e) => handle(e.target.files[0]);
    ["dragenter", "dragover"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.add("drag");
      }),
    );
    ["dragleave", "drop"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.remove("drag");
      }),
    );
    drop.addEventListener("drop", (e) => handle(e.dataTransfer.files[0]));
  };
  VIEWS.datasets = async (el) => {
    const { datasets } = await api("/api/datasets");
    if (!datasets.length) {
      el.innerHTML = empty(
        "🗂",
        "No datasets yet",
        "Upload your first dataset to get started.",
        `<p><a class="btn primary" href="#/upload">Upload dataset</a></p>`,
      );
      return;
    }
    el.innerHTML = `<div class="card"><h3>Datasets <small>${datasets.length}</small></h3>${table(
      [
        "ID",
        "Name",
        "Type",
        "Rows × Cols",
        "Size",
        "Uploaded",
        "Latest analysis",
        "",
      ],
      datasets.map((d) => {
        const a = d.latest_analysis;
        return `<tr><td>#${d.id}</td><td><b>${esc(d.name)}</b></td><td>${esc(d.file_type.toUpperCase())}</td><td>${fmt(d.rows, 0)} × ${d.columns}</td><td>${fmt(d.size_bytes / 1024, 0)} KB</td><td>${esc(d.uploaded_at.replace("T", " ").replace("Z", ""))}</td>
    <td>${a ? (a.status === "COMPLETED" ? `${pill(a.risk_level)} Q ${fmt(a.quality_score, 1)}` : pill(a.status)) : '<span class="muted">not analyzed</span>'}</td>
    <td class="row"><button class="btn small primary" data-an="${d.id}">Analyze</button>${a && a.status === "COMPLETED" ? `<button class="btn small" data-open="${a.id}">Open</button>` : ""}<a class="btn small" href="/api/datasets/${d.id}/download">Original</a><button class="btn small danger" data-del="${d.id}">Delete</button></td></tr>`;
      }),
    )}</div>`;
    el.querySelectorAll("[data-an]").forEach(
      (b) => (b.onclick = guard(() => startAnalysis(b.dataset.an))),
    );
    el.querySelectorAll("[data-open]").forEach(
      (b) =>
        (b.onclick = () => {
          state.analysisId = Number(b.dataset.open);
          state.result = null;
          refreshPicker();
          location.hash = "#/dashboard";
        }),
    );
    el.querySelectorAll("[data-del]").forEach(
      (b) =>
        (b.onclick = guard(async () => {
          if (
            !confirm("Delete this dataset, its analyses and the stored file?")
          )
            return;
          await api(`/api/datasets/${b.dataset.del}`, { method: "DELETE" });
          state.result = null;
          state.analysisId = null;
          await refreshPicker();
          toast("Dataset deleted", "ok");
          router();
        })),
    );
  };

  /* ----------------------------------------------------------- analysis */
  VIEWS.analysis = async (el) => {
    const r = await getResult();
    if (!r) {
      el.innerHTML = needAnalysis();
      return;
    }
    const d = r.decision,
      p = r.profile,
      q = r.quality;
    $("#pageSub").textContent =
      `${r.dataset.name} · analysis #${r.analysis.id}`;
    el.innerHTML = `<div class="stack">
  <div class="card"><div class="row spread"><h3>Final decision</h3><button class="btn small" id="rerun">↻ Re-run analysis</button></div>
    <div class="row">${pill(d.overall_status, d.risk_level === "LOW" ? "HEALTHY" : d.risk_level)}${pill(d.risk_level)}<span class="pill">${esc(d.priority)}</span><b>${esc(d.decision)}</b></div>
    <p>${esc(d.recommended_action)}</p><p class="muted small">${esc(d.automation)}</p>
    ${d.floors_applied.length ? `<div class="notice info">${d.floors_applied.map(esc).join("<br>")}</div>` : ""}
    <h4 style="margin-top:1rem">Risk score ${fmt(d.risk_score, 1)} / 100 — how it was calculated</h4>
    ${hbars(
      d.components.map((c) => ({
        label: c.name,
        value: c.points,
        color: c.points ? "#f59e0b" : "#cbd5e1",
      })),
      { max: 35, suffix: " pts" },
    )}
    <p class="small muted">${d.components.map((c) => `<b>${esc(c.name)}</b>: ${esc(c.reason)}`).join(" · ")}</p>
    ${d.not_available.length ? `<p class="small muted">Not assessed (${d.not_available.map(esc).join("; ")}) — contributes 0 points rather than a guess.</p>` : ""}</div>
  <div class="grid g2"><div class="card"><h3>Dataset profile</h3><dl class="kv"><dt>Rows</dt><dd>${fmt(p.rows, 0)}</dd><dt>Columns</dt><dd>${p.columns}</dd>
    <dt>Numerical</dt><dd>${p.numerical_columns.map(esc).join(", ") || "—"}</dd><dt>Categorical</dt><dd>${p.categorical_columns.map(esc).join(", ") || "—"}</dd>
    <dt>Date</dt><dd>${p.date_columns.map(esc).join(", ") || "—"}</dd><dt>Constant</dt><dd>${p.constant_columns.map(esc).join(", ") || "none"}</dd>
    <dt>Missing / duplicates</dt><dd>${fmt(p.missing_values, 0)} cells (${p.missing_cells_pct}%) · ${p.duplicate_rows} duplicate rows</dd>
    <dt>File</dt><dd>${esc((p.load.file_type || "").toUpperCase())}${p.load.encoding ? " · " + esc(p.load.encoding) : ""}${p.load.dropped_empty_rows ? ` · ${p.load.dropped_empty_rows} empty rows ignored` : ""}</dd></dl>
    ${(p.load.warnings || []).map((w) => `<div class="notice">⚠ ${esc(w)}</div>`).join("")}</div>
  <div class="card"><h3>Insights</h3><ul class="list">${r.insights.map((i) => `<li>💡 ${esc(i)}</li>`).join("")}</ul></div></div>
  <div class="card"><h3>Descriptive statistics <small>numerical columns</small></h3>${
    Object.keys(p.descriptive_statistics).length
      ? table(
          ["Column", "Min", "Q1", "Median", "Mean", "Q3", "Max", "Std"],
          Object.entries(p.descriptive_statistics).map(
            ([c, s]) =>
              `<tr><td><b>${esc(c)}</b></td><td>${fmt(s.min, 2)}</td><td>${fmt(s.q1, 2)}</td><td>${fmt(s.median, 2)}</td><td>${fmt(s.mean, 2)}</td><td>${fmt(s.q3, 2)}</td><td>${fmt(s.max, 2)}</td><td>${fmt(s.std, 2)}</td></tr>`,
          ),
        )
      : `<div class="empty">No numerical columns in this dataset.</div>`
  }</div>
  <div class="card"><h3>Analysis pipeline <small>${r.pipeline.total_seconds}s total</small></h3><div class="steps">${r.pipeline.steps.map((s) => `<div class="step"><span>${esc(s.name)}</span><span>${pill(s.status)} <span class="muted">${s.seconds}s</span></span></div>`).join("")}</div>
  ${r.pipeline.failed_steps.length ? `<div class="notice" style="margin-top:.7rem">Some optional steps could not complete: ${r.pipeline.failed_steps.map(esc).join(", ")}. Other results are unaffected.</div>` : ""}</div></div>`;
    $("#rerun").onclick = guard(() => startAnalysis(r.dataset.id));
  };

  /* ------------------------------------------------------------ quality */
  VIEWS.quality = async (el) => {
    const r = await getResult();
    if (!r) {
      el.innerHTML = needAnalysis();
      return;
    }
    const q = r.quality;
    el.innerHTML = `<div class="stack">
  <div class="grid g2"><div class="card"><h3>Canonical quality score</h3><div class="row"><span style="font-size:42px;font-weight:800">${fmt(q.overall_score, 2)}</span>${pill(q.grade, q.grade === "Excellent" ? "GOOD" : q.grade === "Good" ? "STABLE" : q.grade === "Moderate" ? "MEDIUM" : "CRITICAL")}</div>
    <p class="small muted">${esc(q.formula)}. Grade is capped by the weakest dimension. Anomalies are scored separately in the risk score.</p>
    ${hbars(Object.entries(q.dimensions).map(([k, v]) => ({ label: `${k} (${v.weight * 100}%)`, value: v.score })))}
    <ul class="small muted">${Object.entries(q.dimensions)
      .map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(v.detail)}</li>`)
      .join("")}</ul>
    ${q.notes.map((n) => `<div class="notice">${esc(n)}</div>`).join("")}</div>
  <div class="card"><h3>Findings <small>${q.findings.length}</small></h3>${q.findings.length ? `<ul class="list">${q.findings.map((f) => `<li>${pill(f.severity)} ${esc(f.message)}</li>`).join("")}</ul>` : `<div class="empty"><span class="big">✓</span>No data-quality problems detected.</div>`}</div></div>
  <div class="card"><h3>Column quality</h3>${table(
    ["Column", "Type", "Score", "Missing", "Invalid", "Inconsistent", "Issues"],
    q.column_quality.map(
      (c) =>
        `<tr><td><b>${esc(c.column)}</b></td><td>${esc(c.kind)}</td><td style="min-width:140px"><div class="bar"><i style="width:${c.score}%;background:${c.score >= 90 ? "#16a34a" : c.score >= 70 ? "#f59e0b" : "#dc2626"}"></i></div> ${fmt(c.score, 1)}</td><td>${c.missing_pct}%</td><td>${c.invalid_pct}%</td><td>${c.inconsistent_pct}%</td><td>${c.issues.map(esc).join(", ") || '<span class="muted">none</span>'}</td></tr>`,
    ),
  )}</div>
  <div class="grid g2"><div class="card"><h3>Validity rules applied</h3>${
    Object.keys(q.validity.rules_applied).length
      ? `<ul class="list">${Object.entries(q.validity.rules_applied)
          .map(
            ([c, r2]) =>
              `<li><b>${esc(c)}</b>: ${r2.min ?? "−∞"} … ${r2.max ?? "∞"} <span class="muted small">(${esc(r2.source)})</span></li>`,
          )
          .join("")}</ul>`
      : `<div class="empty">No range rules apply to these columns.</div>`
  }</div>
  <div class="card"><h3>Suspicious / inconsistent categories</h3>${
    Object.keys(q.consistency.columns).length +
    Object.keys(q.consistency.suspicious_categories).length
      ? `<ul class="list">${Object.entries(q.consistency.columns)
          .map(
            ([c, d]) =>
              `<li><b>${esc(c)}</b>: ${d.variant_groups
                .map((g) =>
                  esc(
                    Object.entries(g.variants)
                      .map(([k, v]) => `'${k}'×${v}`)
                      .join(" / "),
                  ),
                )
                .join(
                  "; ",
                )}${d.whitespace_issues ? ` · ${d.whitespace_issues} with extra spaces` : ""}</li>`,
          )
          .join("")}${Object.entries(q.consistency.suspicious_categories)
          .map(
            ([c, items]) =>
              `<li><b>${esc(c)}</b> rare values: ${items.map((i) => `'${esc(i.value)}'×${i.count}`).join(", ")}</li>`,
          )
          .join("")}</ul>`
      : `<div class="empty">No inconsistent categories found.</div>`
  }</div></div></div>`;
  };

  /* ---------------------------------------------------------- anomalies */
  VIEWS.anomalies = async (el) => {
    const r = await getResult();
    if (!r) {
      el.innerHTML = needAnalysis();
      return;
    }
    const a = r.anomalies,
      s = a.summary,
      ev = r.evaluation,
      st = a.statistical,
      ml = a.machine_learning;
    const recs = a.records.filter(
      (x) => state.filterSev === "ALL" || x.severity === state.filterSev,
    );
    el.innerHTML = `<div class="stack">
  ${st.message ? `<div class="notice">${esc(st.message)}</div>` : ""}${ml.status !== "OK" && ml.message ? `<div class="notice info">🤖 ML detection: ${esc(ml.message)}</div>` : ""}
  <div class="grid g2"><div class="card"><h3>Summary</h3><div class="row" style="gap:1.4rem"><div><div class="kpi"><div class="value">${fmt(s.anomaly_count, 0)}</div><div class="sub">anomalous records (${s.anomaly_pct}%)</div></div></div>${donut(["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((k) => ({ label: k, value: s.severity_distribution[k] || 0, color: SEV[k] })))}</div>
    <p class="small muted">${esc(s.method_note || "")} A record is reported when it breaks a validity rule, is flagged by ≥ ${s.min_votes} detectors, or is flagged by one detector with an extreme deviation. ${fmt(s.weak_signal_count, 0)} weaker single-detector signals were not reported.</p>
    <p class="small">Evidence: ${
      Object.entries(s.evidence_distribution || {})
        .map(([k, v]) => `${pill(k)} ${v}`)
        .join(" ") || "—"
    }</p></div>
  <div class="card"><h3>Detectors</h3>${table(
    ["Detector", "Type", "Status", "Flagged", "Time"],
    a.detectors.map(
      (d) =>
        `<tr><td><b>${esc(d.model)}</b></td><td>${esc(d.type.replace("_", " "))}</td><td>${pill(d.status)}${d.message ? `<div class="small muted">${esc(d.message)}</div>` : ""}</td><td>${d.anomalies_flagged == null ? "—" : `${fmt(d.anomalies_flagged, 0)} (${d.anomaly_pct}%)`}</td><td>${d.execution_seconds ?? "—"}s</td></tr>`,
    ),
  )}
    <details style="margin-top:.7rem"><summary class="small">Features analysed (${st.features_used.length}) & excluded (${st.features_excluded.length})</summary><p class="small"><b>Used:</b> ${st.features_used.map(esc).join(", ") || "none"}${(st.log_scaled_features || []).length ? `<br><b>Analysed on log scale (skewed):</b> ${st.log_scaled_features.map(esc).join(", ")}` : ""}</p><p class="small muted"><b>Excluded:</b> ${st.features_excluded.map((e) => `${esc(e.feature)} (${esc(e.reason)})`).join("; ") || "none"}</p></details></div></div>
  <div class="card"><h3>Statistical detection per feature <small>IQR ×${st.thresholds ? st.thresholds.iqr_multiplier : ""} · Z &gt; ${st.thresholds ? st.thresholds.zscore_threshold : ""}</small></h3>${
    st.per_feature.length
      ? table(
          [
            "Feature",
            "IQR flagged",
            "Z-score flagged",
            "Records",
            "% rows",
            "Expected range (IQR)",
          ],
          st.per_feature.map(
            (f) =>
              `<tr><td><b>${esc(f.feature)}</b></td><td>${f.iqr_anomalies}</td><td>${f.zscore_anomalies}</td><td>${f.records_flagged}</td><td>${f.anomaly_pct}%</td><td>${f.lower_bound == null ? "—" : `${fmt(f.lower_bound, 2)} … ${fmt(f.upper_bound, 2)}`}</td></tr>`,
          ),
        )
      : `<div class="empty">No numerical features were suitable for statistical detection.</div>`
  }</div>
  <div class="card"><h3>Model comparison</h3>${evalBlock(ev)}</div>
  <div class="card"><div class="row spread"><h3>Anomalous records <small>${recs.length}${s.truncated ? " (top 1,000)" : ""}</small></h3><div class="row">${["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((k) => `<button class="btn small ${state.filterSev === k ? "primary" : ""}" data-sev="${k}">${k}</button>`).join("")}<a class="btn small" href="/api/analysis/${r.analysis.id}/reports/anomaly_report">⬇ CSV</a></div></div>
  ${
    recs.length
      ? table(
          [
            "Row",
            "Severity",
            "Evidence",
            "Detectors",
            "Feature",
            "Value",
            "Methods",
          ],
          recs
            .slice(0, 300)
            .map(
              (x) =>
                `<tr><td>${x.row}</td><td>${pill(x.severity)}</td><td>${pill(x.evidence_level)}</td><td>${x.support_count}/${x.available_detectors}</td><td><b>${esc(x.primary_feature || "—")}</b></td><td>${fmt(x.primary_value, 2)}</td><td class="small">${x.detectors.map(esc).join(", ")}</td></tr>`,
            ),
        )
      : `<div class="empty"><span class="big">✓</span>No anomalous records${state.filterSev !== "ALL" ? " at this severity" : ""}.</div>`
  }
  ${recs.length > 300 ? `<p class="small muted">Showing 300 of ${recs.length}. Download the anomaly report for all.</p>` : ""}</div></div>`;
    el.querySelectorAll("[data-sev]").forEach(
      (b) =>
        (b.onclick = () => {
          state.filterSev = b.dataset.sev;
          VIEWS.anomalies(el);
        }),
    );
  };
  function evalBlock(ev) {
    const gt = ev.ground_truth,
      ag = ev.agreement;
    let h = `<p class="small muted"><b>Model-generated detection</b> (always available): counts and agreement between detectors. <b>Ground-truth evaluation</b> needs a labelled column.</p>`;
    h += `<div class="notice ${gt.available ? "ok" : "info"}">${gt.available ? `Ground-truth labels found in <b>${esc(gt.label_column)}</b> (${gt.actual_anomalies} labelled anomalies). Metrics below compare each detector with those labels.` : esc(gt.message)}</div>`;
    if (gt.available)
      h += table(
        [
          "Model",
          "Flagged",
          "Precision",
          "Recall",
          "F1",
          "Accuracy",
          "TP",
          "FP",
          "FN",
          "TN",
        ],
        gt.metrics.map(
          (m) =>
            `<tr><td><b>${esc(m.model)}</b></td><td>${m.anomalies_flagged}</td><td>${m.precision}</td><td>${m.recall}</td><td>${m.f1_score}</td><td>${m.accuracy}</td><td>${m.true_positive}</td><td>${m.false_positive}</td><td>${m.false_negative}</td><td>${m.true_negative}</td></tr>`,
        ),
      );
    if (ag.models && ag.models.length > 1)
      h += `<h4 style="margin-top:1rem">Agreement between detectors <small class="muted">Jaccard overlap of flagged records (1 = identical)</small></h4>${table(
        ["", ...ag.models],
        ag.models.map(
          (a) =>
            `<tr class="heat"><td style="text-align:left"><b>${esc(a)}</b></td>${ag.models
              .map((b) => {
                const v = ag.jaccard[a][b];
                return `<td style="background:rgba(79,70,229,${(v || 0) * 0.6})" title="${ag.percent_agreement[a][b]}% of rows agree">${v == null ? "—" : v}</td>`;
              })
              .join("")}</tr>`,
        ),
        "heat",
      )}`;
    else if (ag.message) h += `<p class="muted">${esc(ag.message)}</p>`;
    return h;
  }

  /* -------------------------------------------------------- explanations */
  VIEWS.explanations = async (el) => {
    const r = await getResult();
    if (!r) {
      el.innerHTML = needAnalysis();
      return;
    }
    const items = r.explanations;
    if (!items.length) {
      el.innerHTML = empty(
        "💡",
        "Nothing to explain",
        "No anomalies were reported for this dataset.",
      );
      return;
    }
    el.innerHTML = `<div class="stack"><div class="notice info">These are <b>evidence-based explanations for review</b> — a flagged record is unusual, not proven wrong. Showing the ${items.length} most important of ${r.anomalies.summary.anomaly_count}.</div>
  ${items
    .slice(0, 60)
    .map(
      (
        x,
      ) => `<div class="card expl" style="--c:${SEV[x.severity]}"><div class="row spread"><h4>${esc(x.headline)}</h4><div class="row">${pill(x.severity)}${pill(x.evidence_level)}<span class="pill">${x.support_count}/${x.available_detectors} detectors</span></div></div>
   <p>${esc(x.explanation)}</p>
   ${x.findings.map((f) => `<dl class="kv"><dt>Feature</dt><dd><b>${esc(f.feature)}</b></dd><dt>Value</dt><dd>${fmt(f.value, 4)}</dd><dt>Expected range</dt><dd>${f.expected_range.min == null && f.expected_range.max == null ? "n/a" : `${fmt(f.expected_range.min, 2)} … ${fmt(f.expected_range.max, 2)}`} <span class="muted small">(${esc(f.expected_range.source)})</span></dd><dt>Detection</dt><dd>${esc(f.detection)}</dd><dt>Severity</dt><dd>${pill(f.severity)}</dd><dt>Reason</dt><dd>${esc(f.reason)}</dd><dt>Evidence</dt><dd class="small">${f.evidence.map(esc).join(" · ")}</dd></dl>`).join("")}
   <p class="small">➡ <b>Suggested action:</b> ${esc(x.recommended_action)}</p></div>`,
    )
    .join("")}</div>`;
  };

  /* ------------------------------------------------------ recommendations */
  VIEWS.recommendations = async (el) => {
    const r = await getResult();
    if (!r) {
      el.innerHTML = needAnalysis();
      return;
    }
    el.innerHTML = `<div class="stack"><div class="row"><a class="btn small" href="/api/analysis/${r.analysis.id}/reports/recommendations">⬇ recommendations.csv</a></div>${r.recommendations
      .map(
        (
          x,
        ) => `<div class="card expl" style="--c:${SEV[x.severity]}"><div class="row spread"><h4>${pill(x.priority, x.severity)} ${esc(x.category)} · <span class="muted">${esc(x.target)}</span></h4>${x.automated_fix ? '<span class="pill OK">automated fix available</span>' : ""}</div>
   <p><b>Finding:</b> ${esc(x.finding)}</p><p>➡ ${esc(x.recommendation)}</p>${x.evidence ? `<p class="small muted">Evidence: ${esc(x.evidence)}</p>` : ""}</div>`,
      )
      .join("")}</div>`;
  };

  /* --------------------------------------------------------- remediation */
  VIEWS.remediation = async (el) => {
    const r = await getResult();
    if (!r) {
      el.innerHTML = needAnalysis();
      return;
    }
    const rem = await api(`/api/analysis/${r.analysis.id}/remediation`),
      plan = rem.plan;
    const show = (res) => `<div class="stack">
    <div class="notice ${res.dry_run ? "info" : "ok"}">${res.dry_run ? "🔍 <b>Preview only</b> — nothing was saved." : "✅ <b>Cleaned copy created.</b> Your original dataset is unchanged."} ${fmt(res.cells_changed, 0)} cells changed, ${fmt(res.rows_removed, 0)} rows removed.</div>
    ${table(
      ["Metric", "Before", "After", "Change"],
      [
        ["quality_score", "Quality score"],
        ["rows", "Rows"],
        ["missing_values", "Missing values"],
        ["duplicate_rows", "Duplicate rows"],
        ["invalid_rows", "Rows with invalid values"],
        ["inconsistent_rows", "Inconsistent rows"],
        ["statistical_anomaly_records", "Statistical anomaly records"],
      ].map(([k, l]) => {
        const b = res.before[k],
          a2 = res.after[k],
          dlt = Math.round((a2 - b) * 100) / 100;
        return `<tr><td>${l}</td><td>${fmt(b, 2)}</td><td>${fmt(a2, 2)}</td><td style="color:${dlt === 0 ? "inherit" : (k === "quality_score" ? dlt > 0 : dlt < 0) ? "#16a34a" : "#dc2626"}">${dlt > 0 ? "+" : ""}${dlt}</td></tr>`;
      }),
    )}
    <h4>What changed</h4>${
      res.changes.length
        ? table(
            ["Operation", "Column", "Changed", "Detail", "Examples"],
            res.changes.map(
              (c) =>
                `<tr><td>${esc(c.operation.replace(/_/g, " "))}</td><td>${esc(c.column || "—")}</td><td>${fmt(c.rows_removed ?? c.cells_changed, 0)}${c.rows_removed ? " rows" : ""}</td><td>${esc(c.detail)}</td><td class="small">${(c.examples || []).map((e) => `${esc(e.before)} → ${esc(e.after)}`).join("<br>")}</td></tr>`,
            ),
          )
        : '<div class="empty">No changes were necessary.</div>'
    }
    <p class="small muted">${esc(res.note)}</p>
    ${res.download_url ? `<a class="btn primary" href="${res.download_url}">⬇ Download cleaned dataset</a>` : ""}</div>`;
    el.innerHTML = `<div class="stack"><div class="card"><h3>Remediation plan</h3><p class="muted">Safe fixes are mechanical and lose no information. Opt-in fixes change real values and should be reviewed. The original file is never modified.</p>
   ${
     plan.length
       ? table(
           ["Apply", "Operation", "Affects", "Type", "Description"],
           plan.map(
             (p) =>
               `<tr><td><input type="checkbox" data-op="${p.operation}" ${p.default ? "checked" : ""}></td><td><b>${esc(p.label)}</b></td><td>${fmt(p.affected, 0)} ${esc(p.unit)}</td><td>${p.safe ? pill("SAFE", "OK") : pill("OPT-IN", "MEDIUM")}</td><td class="small">${esc(p.description)}</td></tr>`,
           ),
         )
       : '<div class="empty"><span class="big">✓</span>Nothing to fix.</div>'
   }
   <div class="row" style="margin-top:1rem"><label class="small muted">Numeric missing values<br><select id="numS"><option>median</option><option>mean</option><option>zero</option><option>drop_rows</option><option>none</option></select></label>
   <label class="small muted">Categorical missing values<br><select id="catS"><option>mode</option><option>unknown</option><option>drop_rows</option><option>none</option></select></label>
   <span style="flex:1"></span><button class="btn" id="preview">Preview Changes</button><button class="btn primary" id="apply">Apply to cleaned copy</button></div></div>
   <div id="remResult">${rem.applied ? `<div class="card"><h3>Last applied remediation <small>${esc(rem.applied.created_at)}</small></h3>${show({ ...rem.applied, dry_run: false })}</div>` : ""}</div></div>`;
    const body = () => ({
      operations: [...el.querySelectorAll("[data-op]:checked")].map(
        (c) => c.dataset.op,
      ),
      numeric_strategy: $("#numS").value,
      categorical_strategy: $("#catS").value,
    });
    const run = (dry) =>
      guard(async () => {
        const b = body();
        if (!b.operations.length) {
          toast("Select at least one operation.", "bad");
          return;
        }
        const res = await api(
          `/api/analysis/${r.analysis.id}/remediation/apply?dry_run=${dry}`,
          { method: "POST", json: b },
        );
        $("#remResult").innerHTML =
          `<div class="card"><h3>${dry ? "Preview" : "Result"}</h3>${show(res)}</div>`;
        if (!dry) toast("Cleaned copy created", "ok");
      });
    $("#preview").onclick = run(true);
    $("#apply").onclick = run(false);
  };

  /* -------------------------------------------------------------- drift */
  VIEWS.drift = async (el) => {
    const r = await getResult();
    if (!r) {
      el.innerHTML = needAnalysis();
      return;
    }
    const dr = r.drift,
      ds = (await api("/api/datasets")).datasets.filter(
        (x) => x.id !== r.dataset.id,
      );
    const picker = `<div class="card"><h3>Reference dataset</h3><p class="muted small">Drift compares this dataset (current) with a reference. Choose any earlier dataset with similar columns and re-run.</p>
    <div class="row"><select id="refPick">${ds.length ? ds.map((d) => `<option value="${d.id}">#${d.id} ${esc(d.name)} (${fmt(d.rows, 0)} rows)</option>`).join("") : '<option value="">No other datasets uploaded</option>'}</select><button class="btn primary" id="runDrift" ${ds.length ? "" : "disabled"}>Run drift analysis</button></div></div>`;
    if (!dr.available) {
      el.innerHTML = `<div class="stack"><div class="notice info">${esc(dr.message || NA)}</div>${dr.features ? "" : ""}${picker}</div>`;
      $("#runDrift").onclick = guard(() =>
        startAnalysis(r.dataset.id, $("#refPick").value),
      );
      return;
    }
    el.innerHTML = `<div class="stack"><div class="card"><div class="row spread"><h3>Overall drift: ${pill(dr.overall_status, dr.overall_risk)}</h3><span class="muted small">Reference: ${esc(dr.reference ? dr.reference.name + " (#" + dr.reference.dataset_id + ", " + dr.reference.mode.replace("_", " ") + ")" : "—")}</span></div>
   <div class="grid g4">${kpi("Drifted features", dr.drifted_features, `of ${dr.features_evaluated} assessed`, "#14b8a6")}${kpi("Significant", dr.significant_features, "", "#dc2626")}${kpi("Average PSI", dr.average_psi, "", "#4f46e5")}${kpi("Drift score", dr.drift_score, "0–100", "#f59e0b")}</div>
   <p class="small muted">Rule: a feature is drifted only when PSI ≥ ${dr.method.psi_moderate} <i>and</i> the statistical test is significant (p &lt; ${dr.method.alpha}). Features with fewer than ${dr.method.min_samples} values are not assessed.</p>
   ${dr.schema.columns_added.length || dr.schema.columns_removed.length ? `<div class="notice">Schema change — added: ${dr.schema.columns_added.map(esc).join(", ") || "none"}; removed: ${dr.schema.columns_removed.map(esc).join(", ") || "none"}</div>` : ""}</div>
   ${table(
     [
       "Feature",
       "Type",
       "Status",
       "PSI",
       "Test",
       "p-value",
       "Reference",
       "Current",
       "",
     ],
     dr.features.map(
       (f, i) =>
         `<tr><td><b>${esc(f.feature)}</b></td><td>${f.type}</td><td>${pill(f.status, f.drifted ? f.risk : f.status === "INSUFFICIENT DATA" ? "SKIPPED" : "OK")}</td><td>${fmt(f.psi, 3)}</td><td>${esc(f.test || "—")}</td><td>${f.p_value == null ? "—" : f.p_value < 0.0001 ? "<0.0001" : f.p_value}</td><td class="small">${f.type === "numeric" && f.reference_summary ? `μ ${fmt(f.reference_summary.mean, 2)}` : f.reference_summary ? `${f.reference_summary.categories} cats` : "—"}</td><td class="small">${f.type === "numeric" && f.current_summary ? `μ ${fmt(f.current_summary.mean, 2)}${f.mean_change_pct != null ? ` (${f.mean_change_pct > 0 ? "+" : ""}${f.mean_change_pct}%)` : ""}` : f.current_summary ? `${f.current_summary.categories} cats` : "—"}</td><td>${f.distribution ? `<button class="btn small" data-f="${i}">Distribution</button>` : esc(f.note || "")}</td></tr>`,
     ),
   )}
   <div class="card hidden" id="distCard"></div>${picker}</div>`;
    el.querySelectorAll("[data-f]").forEach(
      (b) =>
        (b.onclick = () => {
          const f = dr.features[b.dataset.f],
            c = $("#distCard");
          c.classList.remove("hidden");
          c.innerHTML = `<h3>${esc(f.feature)} — reference vs current distribution</h3>${distChart(f.distribution)}${f.new_categories && f.new_categories.length ? `<p class="small">New categories: ${f.new_categories.map(esc).join(", ")}</p>` : ""}${f.note ? `<p class="small muted">${esc(f.note)}</p>` : ""}`;
          c.scrollIntoView({ behavior: "smooth" });
        }),
    );
    $("#runDrift").onclick = guard(() =>
      startAnalysis(r.dataset.id, $("#refPick").value),
    );
  };

  /* ------------------------------------------------------------- alerts */
  VIEWS.alerts = async (el) => {
    if (!state.analysisId) {
      el.innerHTML = needAnalysis();
      return;
    }
    const d = await api(`/api/alerts?analysis_id=${state.analysisId}`);
    if (!d.count) {
      el.innerHTML = empty(
        "🔔",
        "No active alerts",
        "No configured threshold was exceeded for this analysis.",
      );
      return;
    }
    el.innerHTML = `<div class="stack"><div class="row">${["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((k) => `${pill(k)} <b>${d.by_severity[k] || 0}</b>`).join(" &nbsp; ")}</div>
  ${d.alerts
    .map(
      (
        a,
      ) => `<div class="card expl" style="--c:${SEV[a.severity]};${a.status === "ACKNOWLEDGED" ? "opacity:.6" : ""}"><div class="row spread"><h4>${pill(a.severity)} ${esc(a.type.replace(/_/g, " "))}</h4><span class="small muted">${esc(a.timestamp.replace("T", " ").replace("Z", ""))}</span></div>
   <p>${esc(a.message)}</p><dl class="kv"><dt>Affected</dt><dd>${esc(a.affected)}</dd><dt>Recommended</dt><dd>${esc(a.recommended_action)}</dd>${a.metric ? `<dt>Metric</dt><dd>${esc(a.metric)} = ${fmt(a.value, 2)} (threshold ${fmt(a.threshold, 2)})</dd>` : ""}</dl>
   ${a.status === "ACTIVE" ? `<button class="btn small" data-ack="${a.id}">Acknowledge</button>` : pill("ACKNOWLEDGED", "SKIPPED")}</div>`,
    )
    .join("")}</div>`;
    el.querySelectorAll("[data-ack]").forEach(
      (b) =>
        (b.onclick = guard(async () => {
          await api(`/api/alerts/${b.dataset.ack}/acknowledge`, {
            method: "PATCH",
          });
          VIEWS.alerts(el);
        })),
    );
  };

  /* ------------------------------------------------------------- trends */
  VIEWS.trends = async (el) => {
    if (!state.analysisId) {
      el.innerHTML = needAnalysis();
      return;
    }
    const r = await getResult();
    const t = await api(`/api/trends?dataset_id=${r.dataset.id}`);
    $("#pageSub").textContent = `Series: ${t.scope.name}`;
    if (!t.available) {
      el.innerHTML = `<div class="notice info">${esc(t.message)}</div><p class="muted">Currently ${t.points} analysis recorded for this dataset series. Re-upload an updated version of <b>${esc(t.scope.name)}</b> and analyze it again to build history.</p>`;
      return;
    }
    const m = t.metrics,
      row = (k, label) =>
        m[k] && m[k].trend
          ? `<tr><td><b>${label}</b></td><td>${pill(m[k].trend)}</td><td>${m[k].direction || "—"}</td><td>${fmt(m[k].previous, 2)} → ${fmt(m[k].latest, 2)}</td></tr>`
          : "";
    el.innerHTML = `<div class="stack"><div class="card"><h3>Overall: ${pill(t.overall_trend)} <small>${t.points} analyses</small></h3><p class="small muted">${esc(t.method)}</p>${table(["Indicator", "Health trend", "Raw direction", "Previous → latest"], [row("quality_score", "Quality score"), row("anomaly_count", "Anomaly count"), row("drifted_features", "Drifted features"), row("risk_score", "Risk score"), row("alert_count", "Alerts")])}</div>
   <div class="grid g2"><div class="card"><h3>Quality trend</h3>${trendChart(t.series, "quality_score", "#4f46e5", "Quality", { clamp: [0, 100], minSpan: 10 })}</div><div class="card"><h3>Anomaly trend</h3>${trendChart(t.series, "anomaly_count", "#f59e0b", "Anomalies")}</div>
   <div class="card"><h3>Drift trend</h3>${trendChart(t.series, "drifted_features", "#14b8a6", "Drifted features")}</div><div class="card"><h3>Risk trend</h3>${trendChart(t.series, "risk_score", "#dc2626", "Risk", { clamp: [0, 100], minSpan: 10 })}</div></div></div>`;
  };
  VIEWS.forecast = async (el) => {
    if (!state.analysisId) {
      el.innerHTML = needAnalysis();
      return;
    }
    const r = await getResult();
    const f = await api(`/api/forecast?dataset_id=${r.dataset.id}`);
    $("#pageSub").textContent = `Series: ${f.scope.name}`;
    if (!f.available) {
      el.innerHTML = `<div class="card empty"><span class="big">🔮</span><h3>${esc(f.message)}</h3><p>${f.history_points} of ${f.required_points} analyses recorded for this dataset series. Forecasts appear once enough history exists — we never invent predictions.</p></div>`;
      return;
    }
    const t = await api(`/api/trends?dataset_id=${r.dataset.id}`),
      k = f.horizon;
    el.innerHTML = `<div class="stack"><div class="grid g4">${kpi("Forecast quality", fmt(f.forecast.quality_score[k - 1].value, 1), `in ${k} runs`, "#4f46e5")}${kpi("Forecast risk", f.forecast.risk_score ? fmt(f.forecast.risk_score[k - 1].value, 1) : "—", f.forecast_risk_level ? pill(f.forecast_risk_level) : NA, "#dc2626")}${kpi("Forecast trend", pill(f.forecast_trend), "", "#14b8a6")}${kpi("Fit (R²)", f.r_squared ?? "—", f.reliability_note || "", "#f59e0b")}</div>
   <div class="card"><h3>Quality forecast</h3>${forecastBlock(f.forecast, t.series)}</div><p class="small muted">${esc(f.method)} Horizon is measured in future analysis runs, not calendar days.</p></div>`;
  };

  /* ------------------------------------------------------------ history */
  VIEWS.history = async (el) => {
    const [a, m] = await Promise.all([
      api("/api/analysis?limit=100"),
      api("/api/monitoring?scope=all&limit=200"),
    ]);
    if (!a.count) {
      el.innerHTML = needAnalysis();
      return;
    }
    el.innerHTML = `<div class="stack"><div class="card"><h3>Analysis history <small>${a.count}</small></h3>${table(
      [
        "#",
        "Dataset",
        "Started",
        "Status",
        "Quality",
        "Anomalies",
        "Drift",
        "Risk",
        "Decision",
        "",
      ],
      a.analyses.map(
        (x) =>
          `<tr><td>#${x.id}</td><td><b>${esc(x.dataset)}</b></td><td>${esc((x.started_at || "").replace("T", " ").replace("Z", ""))}</td><td>${pill(x.status)}</td><td>${fmt(x.quality_score, 1)}</td><td>${x.anomaly_count ?? "—"}</td><td>${x.drifted_features ?? "—"}</td><td>${x.risk_level ? pill(x.risk_level) + " " + fmt(x.risk_score, 1) : "—"}</td><td class="small">${esc(x.decision || x.error || "")}</td><td>${x.status === "COMPLETED" ? `<button class="btn small" data-open="${x.id}">Open</button> <a class="btn small" href="/api/analysis/${x.id}/reports/full_report">Report</a>` : ""}</td></tr>`,
      ),
    )}</div>
  <div class="card"><h3>Monitoring record <small>quality over time (all datasets)</small></h3>${
    m.history.length > 1
      ? lineChart({
          labels: m.history.map((p) => `#${p.analysis_id}`),
          series: [
            {
              name: "Quality",
              color: "#4f46e5",
              values: m.history.map((p) => p.quality_score),
            },
            {
              name: "Risk",
              color: "#dc2626",
              values: m.history.map((p) => p.risk_score),
            },
          ],
          clamp: [0, 100],
          minSpan: 10,
        })
      : `<div class="empty">${NA}</div>`
  }</div></div>`;
    el.querySelectorAll("[data-open]").forEach(
      (b) =>
        (b.onclick = () => {
          state.analysisId = Number(b.dataset.open);
          state.result = null;
          refreshPicker();
          location.hash = "#/dashboard";
        }),
    );
  };

  /* --------------------------------------------------------------- boot */
  async function boot() {
    buildNav();
    $("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");
    $("#analysisPicker").onchange = (e) => {
      state.analysisId = Number(e.target.value) || null;
      state.result = null;
      router();
    };
    window.addEventListener("hashchange", router);
    try {
      const h = await api("/api/health");
      $("#dbStatus").className = "dot " + (h.database.connected ? "ok" : "bad");
      $("#dbText").textContent = h.database.connected
        ? `Database ${h.database.dialect} · v${h.version}`
        : "Database unavailable";
    } catch (e) {
      $("#dbStatus").className = "dot bad";
      $("#dbText").textContent = "Server unreachable";
    }
    try {
      await refreshPicker();
    } catch (e) {
      /* shown by the view */
    }
    router();
  }
  boot();
})();
