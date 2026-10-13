const fileInput =
    document.getElementById("fileInput");

const analyzeBtn =
    document.getElementById("analyzeBtn");

const status =
    document.getElementById("status");

const results =
    document.getElementById("results");

const historyBtn =
    document.getElementById("historyBtn");

const historyContainer =
    document.getElementById(
        "historyContainer"
    );


// =====================================================
// ANALYZE CSV
// =====================================================

analyzeBtn.addEventListener(
    "click",
    async () => {

        const file =
            fileInput.files[0];


        if (!file) {

            status.textContent =
                "Please select a CSV file.";

            return;
        }


        if (
            !file.name
                .toLowerCase()
                .endsWith(".csv")
        ) {

            status.textContent =
                "Please upload a CSV file.";

            return;
        }


        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );


        status.textContent =
            "Analyzing dataset...";


        analyzeBtn.disabled =
            true;


        try {

            const response =
                await fetch(
                    "/api/analyze",
                    {
                        method: "POST",
                        body: formData
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Analysis failed."
                );

            }


            displayResults(data);


            status.textContent =
                "Analysis completed successfully!";


        } catch (error) {

            status.textContent =
                "Error: " +
                error.message;

        } finally {

            analyzeBtn.disabled =
                false;

        }

    }
);


// =====================================================
// DISPLAY RESULTS
// =====================================================

function displayResults(data) {

    results.classList.remove(
        "hidden"
    );


    document.getElementById(
        "rows"
    ).textContent =
        data.rows;


    document.getElementById(
        "columns"
    ).textContent =
        data.columns;


    document.getElementById(
        "missing"
    ).textContent =
        data.quality
            ?.missing_values ?? 0;


    document.getElementById(
        "duplicates"
    ).textContent =
        data.quality
            ?.duplicate_rows ?? 0;


    document.getElementById(
        "anomaliesCount"
    ).textContent =
        data.anomalies_detected;


    displayAnomalies(
        data.anomalies
    );

}


// =====================================================
// DISPLAY ANOMALIES
// =====================================================

function displayAnomalies(
    anomalies
) {

    const container =
        document.getElementById(
            "anomalyContainer"
        );


    container.innerHTML =
        "";


    if (
        !anomalies ||
        anomalies.length === 0
    ) {

        container.innerHTML =
            "<p>No anomalies detected.</p>";

        return;
    }


    anomalies.forEach(
        anomaly => {

            const div =
                document.createElement(
                    "div"
                );


            div.className =
                "anomaly " +
                String(
                    anomaly.severity ||
                    "low"
                ).toLowerCase();


            div.innerHTML = `

                <h3>
                    ${escapeHtml(
                        anomaly.feature
                    )}
                </h3>

                <p>
                    <strong>Row:</strong>
                    ${anomaly.row}
                </p>

                <p>
                    <strong>Value:</strong>
                    ${anomaly.value}
                </p>

                <p>
                    <strong>Z-Score:</strong>
                    ${anomaly.z_score}
                </p>

                <p>
                    <strong>Severity:</strong>
                    ${escapeHtml(
                        anomaly.severity
                    )}
                </p>

                <p>
                    <strong>Recommendation:</strong>
                    ${escapeHtml(
                        anomaly.recommendation
                    )}
                </p>

            `;


            container.appendChild(
                div
            );

        }
    );

}


// =====================================================
// LOAD HISTORY
// =====================================================

historyBtn.addEventListener(
    "click",
    async () => {

        historyContainer.innerHTML =
            "<p>Loading history...</p>";


        try {

            const response =
                await fetch(
                    "/api/history"
                );


            const history =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    "Could not load history."
                );

            }


            displayHistory(
                history
            );


        } catch (error) {

            historyContainer.innerHTML =
                `<p>
                    Error:
                    ${escapeHtml(
                        error.message
                    )}
                </p>`;

        }

    }
);


// =====================================================
// DISPLAY HISTORY
// =====================================================

function displayHistory(
    history
) {

    historyContainer.innerHTML =
        "";


    if (
        !history ||
        history.length === 0
    ) {

        historyContainer.innerHTML =
            "<p>No analysis history found.</p>";

        return;
    }


    history.forEach(
        item => {

            const div =
                document.createElement(
                    "div"
                );


            div.className =
                "history-item";


            div.innerHTML = `

                <h3>
                    ${escapeHtml(
                        item.filename
                    )}
                </h3>

                <p>
                    Rows:
                    ${item.rows}
                </p>

                <p>
                    Columns:
                    ${item.columns}
                </p>

                <p>
                    Missing Values:
                    ${item.missing_values}
                </p>

                <p>
                    Duplicate Rows:
                    ${item.duplicate_rows}
                </p>

                <p>
                    Anomalies:
                    ${item.anomalies_detected}
                </p>

            `;


            historyContainer.appendChild(
                div
            );

        }
    );

}


// =====================================================
// HTML ESCAPE
// =====================================================

function escapeHtml(
    value
) {

    const div =
        document.createElement(
            "div"
        );

    div.textContent =
        value ?? "";

    return div.innerHTML;

}