let severityChart = null;
let featureChart = null;


// =====================================================
// LOAD DASHBOARD
// =====================================================

async function loadDashboard() {

    try {

        await checkHealth();

        await loadSummary();

        await loadSeverity();

        await loadFeatures();

        await loadHistory();

        await loadAnomalies();

    }

    catch (error) {

        console.error(
            "Dashboard error:",
            error
        );

    }

}


// =====================================================
// HEALTH
// =====================================================

async function checkHealth() {

    const response =
        await fetch(
            "/health"
        );

    const data =
        await response.json();

    const status =
        document.getElementById(
            "status"
        );


    if (
        data.status ===
        "healthy"
    ) {

        status.innerText =
            "● System Online";

    }

    else {

        status.innerText =
            "● Database Error";

        status.style.background =
            "#fee2e2";

        status.style.color =
            "#991b1b";
    }

}


// =====================================================
// SUMMARY
// =====================================================

async function loadSummary() {

    const response =
        await fetch(
            "/api/dashboard/summary"
        );

    const data =
        await response.json();


    document.getElementById(
        "totalAnalyses"
    ).innerText =
        data.total_analyses;


    document.getElementById(
        "totalRows"
    ).innerText =
        data.total_rows;


    document.getElementById(
        "totalAnomalies"
    ).innerText =
        data.total_anomalies;


    document.getElementById(
        "totalMissing"
    ).innerText =
        data.total_missing_values;


    document.getElementById(
        "totalDuplicates"
    ).innerText =
        data.total_duplicates;

}


// =====================================================
// SEVERITY CHART
// =====================================================

async function loadSeverity() {

    const response =
        await fetch(
            "/api/dashboard/severity"
        );

    const data =
        await response.json();


    const labels =
        data.map(
            item =>
                item.severity
        );


    const values =
        data.map(
            item =>
                item.count
        );


    const ctx =
        document.getElementById(
            "severityChart"
        );


    if (severityChart) {

        severityChart.destroy();

    }


    severityChart =
        new Chart(
            ctx,
            {

                type:
                    "doughnut",

                data: {

                    labels:
                        labels,

                    datasets: [{

                        data:
                            values

                    }]

                },

                options: {

                    responsive:
                        true

                }

            }
        );

}


// =====================================================
// FEATURE CHART
// =====================================================

async function loadFeatures() {

    const response =
        await fetch(
            "/api/dashboard/features"
        );

    const data =
        await response.json();


    const labels =
        data.map(
            item =>
                item.feature
        );


    const values =
        data.map(
            item =>
                item.count
        );


    const ctx =
        document.getElementById(
            "featureChart"
        );


    if (featureChart) {

        featureChart.destroy();

    }


    featureChart =
        new Chart(
            ctx,
            {

                type:
                    "bar",

                data: {

                    labels:
                        labels,

                    datasets: [{

                        label:
                            "Anomalies",

                        data:
                            values

                    }]

                },

                options: {

                    responsive:
                        true,

                    plugins: {

                        legend: {

                            display:
                                false

                        }

                    }

                }

            }
        );

}


// =====================================================
// HISTORY
// =====================================================

async function loadHistory() {

    const response =
        await fetch(
            "/api/dashboard/history"
        );

    const data =
        await response.json();


    const table =
        document.getElementById(
            "historyTable"
        );


    table.innerHTML = "";


    data.forEach(
        item => {

            const row =
                document.createElement(
                    "tr"
                );


            row.innerHTML = `

                <td>
                    ${item.id}
                </td>

                <td>
                    ${item.filename}
                </td>

                <td>
                    ${item.rows}
                </td>

                <td>
                    ${item.columns}
                </td>

                <td>
                    ${item.missing_values}
                </td>

                <td>
                    ${item.duplicate_rows}
                </td>

                <td>
                    ${item.anomalies_detected}
                </td>

                <td>
                    ${item.created_at}
                </td>

            `;


            table.appendChild(
                row
            );

        }
    );

}


// =====================================================
// ANOMALIES
// =====================================================

async function loadAnomalies() {

    const response =
        await fetch(
            "/api/dashboard/anomalies"
        );

    const data =
        await response.json();


    const table =
        document.getElementById(
            "anomalyTable"
        );


    table.innerHTML = "";


    data.forEach(
        item => {

            const row =
                document.createElement(
                    "tr"
                );


            row.innerHTML = `

                <td>
                    ${item.filename}
                </td>

                <td>
                    ${item.row}
                </td>

                <td>
                    ${item.feature}
                </td>

                <td>
                    ${item.value}
                </td>

                <td>
                    ${item.z_score}
                </td>

                <td>
                    ${item.severity}
                </td>

                <td>
                    ${item.recommendation}
                </td>

            `;


            table.appendChild(
                row
            );

        }
    );

}


// =====================================================
// START
// =====================================================

document.addEventListener(
    "DOMContentLoaded",
    loadDashboard
);