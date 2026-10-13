# AI Data Quality Intelligence Platform

One application that tells you whether a dataset can be trusted. Upload a CSV, Excel or PDF-table file, click
**Analyze Dataset**, and the platform profiles it, scores its quality, finds statistical and machine-learning
anomalies, explains them in plain language, recommends fixes, builds a cleaned copy, checks for drift against a
reference dataset, tracks quality over time, raises alerts, forecasts where quality is heading and finishes with
one deterministic health decision.

```
python run.py          →  http://127.0.0.1:8000        (API docs: /api/docs)
```

## Contents
[Features](#features) · [Architecture](#architecture) · [Tech stack](#tech-stack) · [Installation](#installation) ·
[Configuration](#environment-setup) · [Database](#database-setup) · [Running](#running-the-application) ·
[Workflow](#analysis-workflow) · [Quality score](#quality-scoring) · [Anomaly detection](#anomaly-detection) ·
[ML models](#machine-learning-models) · [Severity](#severity-system) · [Explainable AI](#explainable-ai) ·
[Recommendations](#recommendations) · [Remediation](#automated-remediation) · [Drift](#drift-detection) ·
[Monitoring & alerts](#monitoring-alerts-trends-and-forecasting) · [Decision engine](#final-decision-engine) ·
[API](#api-reference) · [Reports](#reports) · [Security](#security) · [Testing](#testing) · [Structure](#project-structure)

---

## Features

| Area | What you get |
|---|---|
| **Upload** | CSV, XLSX, XLS and PDF tables. Content-signature check, size limit, sanitised filename, uuid storage, encoding + delimiter detection, empty rows/columns removed, column names normalised. The original file is never modified. |
| **Profiling** | Rows, columns, types (numeric / categorical / date / boolean), unique and missing values, duplicates, constant columns, min / max / mean / median / std / quartiles. |
| **Quality** | One canonical 0–100 score from five documented dimensions; findings with severity; per-column quality; validity rules, datatype problems, inconsistent categories, suspicious rare categories. |
| **Anomalies** | IQR and Z-score + Isolation Forest, Local Outlier Factor, One-Class SVM, combined by a consensus layer into evidence-based findings (“4 of 5 detectors support this record”). |
| **Explainable AI** | For each important anomaly: feature, value, expected range, detection methods, severity, reason, supporting evidence. |
| **Recommendations** | Generated from the problems actually found — nothing generic. |
| **Remediation** | Safe fixes + opt-in fixes, always applied to a **copy**, with change log, before/after statistics and CSV download. |
| **Drift** | Reference vs current: PSI + KS (numeric) and PSI + chi-square (categorical), schema changes, distribution charts. |
| **Monitoring** | Every analysis is a monitoring point; history, trends (improving / declining / stable), forecasts when there is enough history. |
| **Alerts** | Threshold-based, with severity, affected feature and recommended action. |
| **Decision** | Risk score, level, priority, status and recommended action — one deterministic framework. |
| **Reports** | Seven unified CSV reports and a self-contained HTML report. |
| **Honesty** | Anything that cannot be computed says *“Not available — insufficient data”*. No fabricated metrics, no fake forecasts. |

## Architecture

```
 Browser (frontend/: index.html · app.js · style.css — no external dependencies)
        │  REST + JSON
        ▼
 FastAPI  app/main.py ── app/api/{datasets, analysis, monitoring, dashboard, reports}.py
        │
        ▼
 ┌────────────────────── ONE PIPELINE  app/services/pipeline.py ──────────────────────┐
 │ load → profile → quality → statistical anomalies → ML anomalies → consensus+severity │
 │ → model comparison → explanations → remediation plan → drift → alerts → monitoring  │
 │ → trends → forecast → recommendations → final decision → save                        │
 └──────────────────────────────────────────────────────────────────────────────────────┘
        │                                                │
        ▼                                                ▼
 app/services/*  (pure, individually testable)    SQLAlchemy  app/models.py → SQLite / PostgreSQL
 app/ml/*        (sklearn wrappers)               data/uploads · data/processed · data/reports
```

Design principles: each dataset is loaded **once** (small LRU cache), features are selected **once**, the three ML
models run **once**, and every downstream service reuses those results. Optional steps are isolated — if one fails
the others still complete and the failure is reported in the result. The analysis runs in a background task and the
UI polls a progress endpoint.

## Tech stack
Python 3.10+ · FastAPI · SQLAlchemy 2 · pandas · NumPy · SciPy · scikit-learn · openpyxl / xlrd · pdfplumber ·
vanilla JS + SVG charts (no CDN, works offline) · pytest.

## Installation

```bash
git clone <your-repo-url> ai-data-quality-platform
cd ai-data-quality-platform

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Environment setup

```bash
cp .env.example .env                 # Windows: copy .env.example .env
```
Edit `.env` if you want to change anything — **every setting has a working default**, so the app runs without a
`.env` file at all.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/platform.db` | SQLAlchemy URL (SQLite or PostgreSQL) |
| `SECRET_KEY` | `change-me` | Reserved for signing/auth extensions; set a random value |
| `UPLOAD_DIR` / `PROCESSED_DIR` / `REPORT_DIR` | `data/uploads` / `data/processed` / `data/reports` | Storage folders |
| `MAX_UPLOAD_SIZE` | `50MB` | Upload limit (`50MB`, `1GB` or bytes) |
| `ALLOWED_EXTENSIONS` | `.csv,.xlsx,.xls,.pdf` | Accepted upload types |
| `CORS_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Allowed browser origins |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Server bind address |
| `LOG_LEVEL` / `DEBUG` | `INFO` / `false` | Logging; `DEBUG=true` enables auto-reload |

Invalid values stop the server at start-up with a clear message (e.g. `Configuration error: PORT must be an integer.`).
`.env` is git-ignored and is never served by the web server.

## Database setup

**SQLite (default)** – nothing to do. Tables are created automatically on first start in `data/platform.db`.

**PostgreSQL**
```bash
pip install psycopg2-binary
createdb dataquality
# .env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/dataquality
```
Special characters in the password must be URL-encoded (`@` → `%40`). Tables are created automatically.
If the database is unreachable the server still starts; `/api/health` reports `degraded` and API calls return a
friendly `503 database_unavailable` instead of a stack trace.

What is stored: dataset *metadata* (the file stays on disk), one `analysis_runs` row per analysis (scalar results +
the unified JSON result — this *is* the monitoring history), flagged anomaly records, alerts, recommendations and
remediation runs. Raw datasets are never copied into the database; raw sample values and near-unique text values
(names, e-mails, ids) are deliberately not stored.

## Running the application

```bash
python run.py                        # or:  uvicorn app.main:app --reload
```
Open <http://127.0.0.1:8000>. Interactive API documentation: <http://127.0.0.1:8000/api/docs>.

Try the bundled demo data (`python sample_data/generate_samples.py` regenerates it):

1. Upload `sample_data/customers_reference.csv` → **Analyze Dataset**.
2. Upload `sample_data/customers_current.csv`, pick the reference dataset in the drop-down → **Analyze Dataset**.
   You will see anomalies (impossible ages, extreme incomes), duplicates, inconsistent city spellings, and drift in
   `annual_income`, `city` and `age`.
3. To see trends and forecasts, upload `sample_data/series/customers_v1.csv … v6.csv` **one after another**
   (rename each to `customers.csv`, or use the API) and analyze each. Uploads that share a file name form one
   monitored series.

## Analysis workflow

1. **Upload** → validated, stored safely, preview + warnings shown.
2. **Analyze Dataset** → `POST /api/analyze/{id}` starts the pipeline in the background; the UI shows a progress bar.
3. The dashboard opens with health, KPIs, charts, insights, recommendations, remediation and report downloads.
4. Drill into *Data Quality, Anomalies, AI Explanations, Recommendations, Remediation, Drift, Alerts, Trends,
   Forecast, History*.

Pipeline: load → profile → quality → statistical anomalies → ML anomalies → consensus + severity → model comparison →
explanations → remediation plan → drift (if a reference exists) → alerts → monitoring → trends → forecast →
recommendations → final decision → save. Recommendations are generated *after* drift/trend/forecast so they can use
that evidence.

## Quality scoring

There is **one** quality score, used everywhere (dashboard, reports, monitoring, decision engine):

```
quality = 0.30·completeness + 0.20·uniqueness + 0.20·validity + 0.15·consistency + 0.15·structure

completeness = 100·(1 − missing_cells / total_cells)
uniqueness   = 100·(1 − duplicate_rows / rows)
validity     = 100·(1 − rows_with_invalid_values / rows)
consistency  = 100·(1 − rows_with_inconsistent_values / rows)
structure    = 100·(1 − constant_columns / columns)
```
Grade: ≥ 90 Excellent, ≥ 75 Good, ≥ 50 Moderate, else Poor — **capped by the weakest dimension** (a dimension
< 80 caps at Good, < 60 at Moderate) so a high average cannot hide, say, 27 % invalid rows.

*Invalid* = outside a validity range, text inside a numeric column, infinite, or outside a user-supplied approved
list. Ranges are derived from column names (`age` 0–120, `*_pct` 0–100, `score` 0–100, `anxiety_0to27` → 0–27,
non-negative measures such as `income`, `hours`, `price`) and can be overridden per analysis
(`validity_rules`, `allowed_values`). *Inconsistent* = same category spelled several ways (case/whitespace).
Rare categories are reported as *suspicious* but do not change the score. **Anomalies are intentionally not part of
the quality score** — they describe unusual, not defective, data and are weighed by the decision engine.

## Anomaly detection

**Which columns are analysed.** Numeric measurement columns only. Excluded (with the reason shown in the UI):
identifier columns, ground-truth label columns, constant and binary/flag columns, identifier-like sequences, and
small coded scales (e.g. integer 1–10 survey answers).

**Statistical detectors** (`app/services/anomaly.py`): IQR (default 1.5×) and Z-score (default |z| > 3), with
per-feature boundaries, anomaly counts, percentages and affected features. Strongly right-skewed non-negative
features (e.g. notification counts) are analysed on a log scale so a natural long tail is not mislabelled as an
error; skewness is measured on the 1 %–99 % body so a single bad value cannot flip the scale. Expected ranges are
always shown in the original units.

**Consensus** (`app/services/consensus.py`). Each of the five detectors votes. A record is *reported* when it breaks
a validity rule, or ≥ 2 detectors flag it, or one detector flags it with an extreme deviation (HIGH or above).
Single-detector, mild signals are counted as “weak signals” but not listed. Wording is evidence-based:
**STRONG** (≥ 3 detectors, or 2 + a rule breach), **MODERATE**, **WEAK** — the platform never claims a record is
definitely wrong.

**Model comparison** (`app/services/evaluation.py`) distinguishes two things:
model-generated detection (counts, timing, pairwise agreement as Jaccard overlap — always available) and
ground-truth evaluation (precision, recall, F1, accuracy, confusion matrix — **only** when the file contains a
label column such as `is_anomaly`; otherwise the UI says metrics are not available).

## Machine-learning models

| Model | File | Notes |
|---|---|---|
| Isolation Forest | `app/ml/isolation_forest.py` | 200 trees, `contamination="auto"`, fixed seed |
| Local Outlier Factor | `app/ml/local_outlier_factor.py` | `n_neighbors=20`; novelty mode when fitted on a sample |
| One-Class SVM | `app/ml/one_class_svm.py` | RBF kernel, `nu=0.05` |

Shared preprocessing (`app/services/ml_detection.py`): features > 50 % missing are dropped, remaining gaps use median
imputation, skewed features are log-transformed, `StandardScaler`, zero-variance columns removed. Categoricals are
excluded by default (optionally frequency-encoded with `ml_include_categorical`). Datasets over 10,000 rows are
fitted on a random sample and scored in full. **No crash on unsuitable data:** fewer than 20 rows, no numeric
features, or a failing model produce `SKIPPED` / `FAILED` statuses with messages; the other detectors continue.

## Severity system

One system — `LOW < MEDIUM < HIGH < CRITICAL` — implemented once in `app/services/severity.py`.

| Signal (per feature) | Level |
|---|---|
| \|z\| ≥ 5 / ≥ 4 / ≥ 3 / below | CRITICAL / HIGH / MEDIUM / LOW |
| Beyond 3×IQR outside the quartiles | HIGH (else LOW) |
| Validity-rule breach | HIGH; CRITICAL if it overshoots the range by ≥ 50 % of its width (age 185 vs 0–120) |

Record severity = highest feature severity, raised one level when ≥ 3 detectors agree — but agreement alone never
creates CRITICAL. Data-quality findings (missing / duplicates / invalid / inconsistent) use rate tables in the same
file. Alerts, recommendations and the decision engine all reuse these levels.

## Explainable AI

Example (real output from the demo data):
```
Row 190: age = 200 breaks a basic validity rule: it should be 0 to 120 (validity rule).
Flagged by 5 of 5 detectors (IQR, Z-Score, Isolation Forest, Local Outlier Factor, One-Class SVM)
plus a validity-rule breach; evidence level strong, severity CRITICAL.
```
Each explanation lists feature, value, expected range (and its source: validity rule / IQR fences / mean ± 3σ),
detection methods, severity, reason, evidence and a suggested action. Records flagged only by ML (an unusual
*combination* of normal-looking values) are explained as exactly that.

## Recommendations
`app/services/recommendation.py` turns findings into actions, each with its evidence and — where one exists — the
name of an automated fix: median/mode imputation by data type (and “drop or recollect” above 50 % missing),
remove confirmed duplicates, investigate out-of-range values and validate business rules, standardise categories
against an approved list, investigate drifted features upstream, review anomaly clusters per feature. If nothing is
wrong it says so.

## Automated remediation
Never modifies your data: it works on a copy and shows exactly what changed.

| Operation | Type | Effect |
|---|---|---|
| Standardize column names | safe | lowercase snake_case |
| Trim whitespace | safe | strip stray spaces |
| Unify category spelling/case | safe | variants → most common spelling |
| Remove exact duplicates | safe | keeps first occurrence (runs *before* imputation) |
| Fill missing values | opt-in | numeric: median / mean / zero / drop rows / none; categorical: mode / “Unknown” / drop rows / none; columns > 60 % missing skipped |
| Blank out out-of-range values | opt-in | rule violations → missing |
| Cap extreme values | opt-in | winsorize at 3×IQR |

**Preview Changes** is a true dry run. **Apply** writes `data/processed/<id>_cleaned_<time>.csv`, returns the change
log, before/after statistics (rows, missing, duplicates, invalid, inconsistent, quality score, statistical anomaly
records) and a download link.

## Drift detection
Choose a reference dataset when analyzing (or let the platform use the previous upload with the same file name).
Numeric features: PSI with bins from the reference quantiles + Kolmogorov–Smirnov test. Categorical features: PSI on
category proportions + chi-square, plus new/disappeared categories. Schema changes are listed.

A feature is **drifted only if PSI ≥ 0.10 and p < 0.05** (≥ 0.25 → significant). Requiring both prevents PSI noise
on small samples and trivial-but-“significant” p-values on huge ones. Features with fewer than 30 values on either
side are reported as *INSUFFICIENT DATA* and never counted as drifted.

## Monitoring, alerts, trends and forecasting
* **Monitoring** – each analysis stores timestamp, dataset, quality score, anomaly count, drifted features, risk level,
  alerts, decision and status. Uploads with the same file name form a monitored series.
* **Alerts** (thresholds in `AnalysisConfig`, overridable per analysis) – quality below 80 / 65 / 50, quality drop ≥ 5 / 10
  points, overall missing ≥ 5 %, any column ≥ 20 % empty, duplicates ≥ 5 %, invalid rows ≥ 1 %, critical or high
  anomalies, anomaly rate ≥ 5 % / 10 %, anomaly count up ≥ 50 % (and ≥ 5 records), each drifted feature. A single missing
  value or one duplicate row never alerts.
* **Trends** – regression slope over the last 30 analyses, with correct direction semantics: rising quality is
  *improving*, rising anomalies/risk/drift/alerts are *declining*. Weighted vote → IMPROVING / DECLINING / STABLE.
* **Forecast** – linear regression with an approximate 95 % band for the next 3 runs; requires ≥ 5 analyses. Otherwise:
  *“Insufficient historical data for reliable forecasting.”*

## Final decision engine
Deterministic additive risk score (0–100):

| Component | Max | Rule |
|---|---|---|
| Quality score | 35 | < 50: 35 · < 60: 30 · < 75: 22 · < 90: 12 · < 95: 5 |
| Data issues | 15 | missing / duplicate / invalid-row rates, 6 / 4 / 2 points per tier |
| Anomalies | 25 | max(severity points, rate points), +7 if ≥ 5 critical |
| Drift | 15 | significant 15 · moderate 8 (only with a reference) |
| Trend | 5 | declining history |
| Forecast | 5 | forecast risk ≥ 40: 5 · ≥ 20: 3 |
| Alerts | 5 | critical 5 · high 3 · medium 1 |

Risk level: ≥ 70 CRITICAL · ≥ 40 HIGH · ≥ 20 MEDIUM · else LOW. Status (HEALTHY / ATTENTION REQUIRED / AT RISK /
CRITICAL), priority (P1–P4), decision text and recommended action all derive from the level, so modules cannot
contradict each other. **Floors:** any critical anomaly ⇒ at least MEDIUM; quality < 50 or ≥ 40 % missing ⇒ at least
HIGH. Components that cannot be computed contribute 0 and are listed under `not_available`.

## API reference
Interactive docs at `/api/docs`. Errors always look like `{"error": {"code": "...", "message": "..."}}` — never a stack trace.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/datasets/upload` | Upload + validate; returns preview and warnings |
| GET | `/api/datasets` · `/api/datasets/{id}` | List / details |
| GET | `/api/datasets/{id}/preview` · `/download` | Preview rows · original file |
| DELETE | `/api/datasets/{id}` | Delete dataset, analyses and stored file |
| POST | `/api/analyze/{dataset_id}` | Start the pipeline (`?wait=true` runs synchronously and returns the result). Body (optional): `reference_dataset_id`, `auto_reference`, `thresholds`, `validity_rules`, `allowed_values` |
| GET | `/api/analysis` · `/api/analysis/{id}` · `/status` | List / unified result / progress |
| GET | `/api/analysis/{id}/profile` · `/quality` · `/anomalies` · `/explanations` · `/recommendations` · `/remediation` · `/decision` | Sections |
| POST | `/api/analysis/{id}/remediation/apply` (`?dry_run=true`) | Build cleaned copy |
| GET | `/api/analysis/{id}/remediation/download` | Cleaned CSV |
| GET | `/api/analysis/{id}/reports` · `/reports/{name}` | Report list / download |
| GET | `/api/monitoring` · `/api/trends` · `/api/forecast` | History, trends, forecast (`?dataset_id=`, `?scope=all`) |
| GET / POST | `/api/drift` · `/api/drift/compare` | Drift of an analysis · ad-hoc comparison |
| GET / PATCH | `/api/alerts` · `/api/alerts/{id}/acknowledge` | Alerts |
| GET | `/api/dashboard/summary` | Everything the dashboard shows |
| GET | `/api/health` · `/api/config` | Health + DB status · thresholds |

```bash
curl -F "file=@sample_data/customers_current.csv" http://127.0.0.1:8000/api/datasets/upload
curl -X POST "http://127.0.0.1:8000/api/analyze/1?wait=true" -H "Content-Type: application/json" \
     -d '{"validity_rules": {"annual_income": [0, 500000]}}'
```

## Reports
Per analysis, from `GET /api/analysis/{id}/reports/{name}` (also written to `data/reports/analysis_<id>/`):
`dataset_profile.csv`, `quality_report.csv`, `anomaly_report.csv`, `recommendations.csv`, `drift_report.csv`,
`monitoring_report.csv`, `final_analysis_report.csv` and `full_report.html`. They are rendered from the saved result —
downloading never re-runs the analysis.

## Security
* Extension allow-list **and** content-signature check (an `.xlsx` must really be a zip, a `.pdf` must start `%PDF`).
* Size limit enforced while streaming; partial files are removed on failure.
* Client filename is sanitised for display only; files are stored as `<uuid><ext>`; uploaded files are never executed;
  path joins are checked against the storage root; report names are whitelisted.
* No credentials in source; configuration from environment; `.env` git-ignored and not served.
* Pydantic validation on every body, strict `extra="forbid"`, unknown thresholds rejected.
* CORS limited to configured origins; every dynamic string is HTML-escaped in the UI.
* Unhandled errors return a generic message; details go to the server log only.
* **Not included:** user authentication. The platform is a single-tenant tool — put it behind a reverse proxy / VPN or
  add authentication (see `SECRET_KEY`) before exposing it publicly.

## Testing
```bash
pytest                      # 130 tests, ~25 s
pytest tests/test_api_e2e.py -k full_workflow     # the end-to-end scenario
```
Covers upload (CSV/XLSX/XLS/PDF, traversal, limits, corruption), profiling, missing/duplicate detection, quality
scoring, IQR, Z-score, each ML model, consensus, severity, explainability, recommendations, remediation, drift,
alerts, trends, forecast, decision engine, database operations and the complete
upload → analyze → persist → dashboard → reports flow.

## Project structure
```
ai-data-quality-platform/
├── run.py                      single entry point
├── requirements.txt · .env.example · .gitignore · pytest.ini
├── app/
│   ├── main.py  config.py  database.py  models.py  schemas.py
│   ├── api/        datasets · analysis · monitoring · dashboard · reports · deps
│   ├── services/   pipeline · profiler · quality · anomaly · ml_detection · consensus · severity ·
│   │               evaluation · explainability · recommendation · remediation · drift · monitoring ·
│   │               alerts · trends · forecasting · decision_engine · reports
│   ├── ml/         isolation_forest · local_outlier_factor · one_class_svm
│   └── utils/      file_handler · validators · helpers
├── frontend/       index.html · app.js · style.css
├── data/           uploads/ · processed/ · reports/      (git-ignored contents)
├── sample_data/    generate_samples.py + demo CSVs
├── tests/
└── archive/        original prototypes (reference only; not used by the app)
```

## Limitations
* Statistical/ML anomaly detection finds *unusual* values, not proven errors — hence evidence levels and review wording.
* Validity ranges are inferred from column names; provide `validity_rules` for domain-specific limits.
* Only the first sheet of an Excel workbook, and PDFs with real (not scanned) tables, are supported.
* Forecasts are simple linear extrapolations over analysis runs, not calendar time.
* No built-in authentication (see Security).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `Configuration error: …` on start | Fix the named variable in `.env` |
| `/api/health` says `degraded` | Check `DATABASE_URL` and that the DB server is running |
| Upload rejected as too large | Raise `MAX_UPLOAD_SIZE` |
| “Cannot reach the server” in the UI | Start `python run.py` and open the printed URL |
| PDF has no table | Only PDFs containing real tables can be parsed; export the table to CSV |
