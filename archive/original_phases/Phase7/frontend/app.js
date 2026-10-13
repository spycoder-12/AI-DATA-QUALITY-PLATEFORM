const fileInput =
    document.getElementById(
        "fileInput"
    );

const analyzeButton =
    document.getElementById(
        "analyzeButton"
    );

const loading =
    document.getElementById(
        "loading"
    );

const dashboard =
    document.getElementById(
        "dashboard"
    );


analyzeButton.addEventListener(
    "click",
    async function () {

        const file =
            fileInput.files[0];

        if (!file) {

            alert(
                "Please select a CSV file."
            );

            return;
        }


        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );


        loading.classList.remove(
            "hidden"
        );

        analyzeButton.disabled =
            true;


        try {

            const response =
                await fetch(
                    "/api/analyze",
                    {
                        method:
                            "POST",

                        body:
                            formData
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


            displayDashboard(
                data
            );

        }

        catch (error) {

            alert(
                error.message
            );

        }

        finally {

            loading.classList.add(
                "hidden"
            );

            analyzeButton.disabled =
                false;
        }

    }
);


function displayDashboard(
    data
) {

    dashboard.classList.remove(
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
        "anomalies"
    ).textContent =
        data.anomalies_detected;


    document.getElementById(
        "missing"
    ).textContent =
        data.quality.missing_values;


    displaySeverity(
        data.anomalies
    );


    displayAnomalyTable(
        data.anomalies
    );


    displayRecommendations(
        data.anomalies
    );

}


function displaySeverity(
    anomalies
) {

    const container =
        document.getElementById(
            "severity"
        );


    const counts = {

        CRITICAL: 0,

        HIGH: 0,

        MEDIUM: 0,

        LOW: 0

    };


    anomalies.forEach(
        anomaly => {

            counts[
                anomaly.severity
            ]++;

        }
    );


    container.innerHTML = "";


    Object.keys(
        counts
    ).forEach(
        severity => {

            const element =
                document.createElement(
                    "div"
                );

            element.className =
                "severity";


            element.innerHTML =
                `${severity}: ${counts[severity]}`;


            container.appendChild(
                element
            );

        }
    );

}


function displayAnomalyTable(
    anomalies
) {

    const container =
        document.getElementById(
            "anomalyTable"
        );


    if (
        anomalies.length === 0
    ) {

        container.innerHTML =
            "<p>No anomalies detected 🎉</p>";

        return;
    }


    let html = `

        <table>

            <thead>

                <tr>

                    <th>Row</th>

                    <th>Feature</th>

                    <th>Value</th>

                    <th>Z-Score</th>

                    <th>Severity</th>

                </tr>

            </thead>

            <tbody>

    `;


    anomalies.forEach(
        anomaly => {

            html += `

                <tr>

                    <td>
                        ${anomaly.row}
                    </td>

                    <td>
                        ${anomaly.feature}
                    </td>

                    <td>
                        ${anomaly.value}
                    </td>

                    <td>
                        ${anomaly.z_score}
                    </td>

                    <td class="critical">
                        ${anomaly.severity}
                    </td>

                </tr>

            `;

        }
    );


    html += `

            </tbody>

        </table>

    `;


    container.innerHTML =
        html;

}


function displayRecommendations(
    anomalies
) {

    const container =
        document.getElementById(
            "recommendations"
        );


    container.innerHTML = "";


    anomalies.forEach(
        anomaly => {

            const element =
                document.createElement(
                    "div"
                );


            element.className =
                "recommendation";


            element.innerHTML = `

                <strong>
                    Row ${anomaly.row}
                    — ${anomaly.feature}
                </strong>

                <p>
                    ${anomaly.recommendation}
                </p>

            `;


            container.appendChild(
                element
            );

        }
    );

}