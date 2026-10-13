// ============================================================
// PAGE LOAD
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
    loadAlerts();
    loadUploadHistory();
    loadMonitoringHistory();
    setupUpload();
});


// ============================================================
// SMALL HELPERS
// ============================================================

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value ?? "-";
    }
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);

    let data = {};
    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        throw new Error(data.detail || `Request failed (${response.status})`);
    }

    return data;
}


// ============================================================
// DASHBOARD
// ============================================================

async function loadDashboard() {
    try {
        const data = await fetchJson("/api/dashboard/summary");

        setText("qualityScore", `${data.quality_score}/100`);
        setText("anomalyCount", data.anomaly_count);
        setText("driftedFeatures", data.drifted_features);
        setText("alertCount", data.alert_count);
        setText("riskLevel", data.risk_level);
        setText("overallTrend", data.overall_trend);
    } catch (error) {
        console.error("Dashboard error:", error);
    }
}


// ============================================================
// ALERTS
// ============================================================

async function loadAlerts() {
    const container = document.getElementById("alerts");
    if (!container) return;

    try {
        const data = await fetchJson("/api/dashboard/alerts");

        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = "<p>No active alerts.</p>";
            return;
        }

        container.innerHTML = data.map(alert => `
            <div class="alert">
                <strong>${escapeHtml(alert.severity || "WARNING")}</strong>
                <span>${escapeHtml(alert.type || "")}</span>
                <p>${escapeHtml(alert.message || "")}</p>
            </div>
        `).join("");
    } catch (error) {
        console.error("Alert error:", error);
        container.innerHTML = "<p>Unable to load alerts.</p>";
    }
}


// ============================================================
// UPLOAD
// ============================================================

function setupUpload() {
    const button = document.getElementById("uploadButton");
    if (button) {
        button.addEventListener("click", uploadDataset);
    }
}

async function uploadDataset() {
    const input = document.getElementById("datasetFile");
    const status = document.getElementById("uploadStatus");

    const file = input?.files?.[0];

    if (!file) {
        status.textContent = "Please select a CSV, Excel or PDF file.";
        return;
    }

    const allowed = [".csv", ".xlsx", ".xls", ".pdf"];
    const extension = "." + file.name.split(".").pop().toLowerCase();

    if (!allowed.includes(extension)) {
        status.textContent = "Unsupported file type.";
        return;
    }

    status.textContent = "Uploading and analyzing...";

    const formData = new FormData();
    formData.append("file", file);

    try {
        const data = await fetchJson("/api/upload", {
            method: "POST",
            body: formData
        });

        status.textContent = "Dataset analyzed successfully!";
        displayUploadResult(data.analysis);

        input.value = "";
        loadUploadHistory();
    } catch (error) {
        console.error("Upload error:", error);
        status.textContent = error.message;
    }
}


// ============================================================
// DISPLAY UPLOAD RESULT
// ============================================================

function displayUploadResult(data) {
    const result = document.getElementById("uploadResult");
    if (!result) return;

    result.classList.remove("hidden");

    setText("resultQuality", `${data.quality_score}/100`);
    setText("resultAnomalies", data.anomaly_count);
    setText("resultMissing", data.missing_values);
    setText("resultDuplicates", data.duplicate_rows);
    setText("resultRisk", data.risk_level);

    const recommendationList = document.getElementById("recommendations");

    if (!recommendationList) return;

    recommendationList.innerHTML = (data.recommendations || [])
        .map(item => `<li>${escapeHtml(item)}</li>`)
        .join("");
}


// ============================================================
// UPLOAD HISTORY
// ============================================================

async function loadUploadHistory() {
    const container = document.getElementById("uploadHistory");
    if (!container) return;

    try {
        const data = await fetchJson("/api/uploads");

        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = "<p>No datasets uploaded yet.</p>";
            return;
        }

        container.innerHTML = data.map(dataset => `
            <div class="upload-item">
                <div>
                    <strong>${escapeHtml(dataset.filename)}</strong>
                    <p>
                        Type: ${escapeHtml(dataset.file_type)}
                        | Rows: ${dataset.rows}
                        | Columns: ${dataset.columns}
                        | Quality: ${dataset.quality_score}/100
                        | Risk: ${escapeHtml(dataset.risk_level)}
                    </p>
                </div>

                <button
                    class="danger-button"
                    onclick="deleteDataset(${dataset.id})"
                >
                    Delete
                </button>
            </div>
        `).join("");
    } catch (error) {
        console.error("Upload history error:", error);
        container.innerHTML = "<p>Unable to load upload history.</p>";
    }
}


// ============================================================
// DELETE UPLOADED DATASET
// ============================================================

async function deleteDataset(id) {
    if (!confirm("Delete this uploaded dataset and its stored file?")) {
        return;
    }

    try {
        await fetchJson(`/api/uploads/${id}`, {
            method: "DELETE"
        });

        await loadUploadHistory();
    } catch (error) {
        alert(error.message);
    }
}


// ============================================================
// MONITORING HISTORY
// ============================================================

async function loadMonitoringHistory() {
    const container = document.getElementById("monitoringHistory");
    if (!container) return;

    try {
        const data = await fetchJson("/api/history");

        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = "<p>No monitoring history recorded yet.</p>";
            return;
        }

        container.innerHTML = data.map(item => `
            <div class="upload-item">
                <div>
                    <strong>Run #${item.id}</strong>
                    <p>
                        Quality: ${item.quality_score}/100
                        | Anomalies: ${item.anomaly_count}
                        | Alerts: ${item.alerts}
                        | Risk: ${escapeHtml(item.risk_level)}
                        | ${escapeHtml(item.created_at || "")}
                    </p>
                </div>

                <button
                    class="danger-button"
                    onclick="deleteMonitoringHistory(${item.id})"
                >
                    Delete
                </button>
            </div>
        `).join("");
    } catch (error) {
        console.error("Monitoring history error:", error);
        container.innerHTML = "<p>Unable to load monitoring history.</p>";
    }
}


// ============================================================
// SAVE MONITORING SNAPSHOT
// ============================================================

async function saveMonitoringSnapshot() {
    try {
        await fetchJson("/api/history/record", {
            method: "POST"
        });

        await loadMonitoringHistory();
    } catch (error) {
        alert(error.message);
    }
}


// ============================================================
// DELETE ONE MONITORING RECORD
// ============================================================

async function deleteMonitoringHistory(id) {
    if (!confirm(`Delete monitoring history record #${id}?`)) {
        return;
    }

    try {
        await fetchJson(`/api/history/${id}`, {
            method: "DELETE"
        });

        await loadMonitoringHistory();
    } catch (error) {
        alert(error.message);
    }
}


// ============================================================
// DELETE ALL MONITORING HISTORY
// ============================================================

async function deleteAllMonitoringHistory() {
    if (!confirm(
        "Delete ALL monitoring history? This cannot be undone."
    )) {
        return;
    }

    try {
        const data = await fetchJson("/api/history", {
            method: "DELETE"
        });

        alert(`${data.deleted_records} monitoring records deleted.`);
        await loadMonitoringHistory();
    } catch (error) {
        alert(error.message);
    }
}


// ============================================================
// BASIC HTML ESCAPING
// ============================================================

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
