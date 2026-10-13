# Archive — original prototype phases (reference only)

These are the original incremental prototypes the platform was built from. **Nothing in the application
depends on this folder** — you can delete it. It is kept so the origin of each capability is traceable.

`.env` files and `__pycache__` were removed from this copy, and one hard-coded database password found in
`phase11/main.py` was redacted. **If that password was ever real, rotate it.**

## Where each prototype's logic went

| Prototype folder | What it contained | Now lives in |
|---|---|---|
| Phase1 | CSV loading, basic profiling | `app/utils/file_handler.py`, `app/services/profiler.py` |
| Phase2 | Missing / duplicate / constant / validity checks, a quality score | `app/services/quality.py` (generalised: rules are derived from column names instead of hard-coding `age`, `city`, `gender`) |
| Phase3 | IQR + Z-score detectors, feature selector | `app/services/anomaly.py` |
| Phase4 | Isolation Forest, LOF, One-Class SVM, preprocessing | `app/ml/*.py`, `app/services/ml_detection.py` |
| Phase5, phase9, phase10 | Model comparison, agreement, precision/recall/F1, confusion matrices | `app/services/evaluation.py` |
| Phase6 | Explanations, severity ladder, recommendations | `app/services/explainability.py`, `severity.py`, `recommendation.py` |
| Phase7, phase8, phase11 | FastAPI + database + frontend generations | `app/main.py`, `app/api/*`, `app/database.py`, `app/models.py`, `frontend/` |
| phase12 | Feature-level "risk predictor" | rule kept as a deterministic check; the RandomForest was **not** ported (see below) |
| phase13 | XAI report | `app/services/explainability.py` |
| phase14 | Quality scorer + decision engine | `quality.py` (one score) and `decision_engine.py` |
| phase15 | Remediation | `app/services/remediation.py` |
| phase16 | PSI + KS drift | `app/services/drift.py` (added categorical drift, sample-size guard) |
| phase17 | Monitor + alert engine | `monitoring.py`, `alerts.py` |
| phase18 | Trend + forecast | `trends.py`, `forecasting.py` |
| phase19 | Final decision engine | `decision_engine.py` |
| phase20 | Upload service (CSV/Excel/PDF), dashboard | `file_handler.py`, `api/dashboard.py` |

## Defects found in the prototypes (and fixed rather than ported)

1. **Five different quality-score formulas** (phases 2, 14, 15, 17, 20). Now exactly one, documented in `quality.py`.
2. **Trend direction inverted** (phase 18): a falling anomaly count was labelled `DECLINING` and the overall
   verdict treated *rising* anomalies as improving. Fixed with explicit "higher is better" semantics.
3. **Phase 18 forecast** worked from as few as 2 points. Now requires 5 or says
   *"Insufficient historical data for reliable forecasting."*
4. **Phase 19 decision engine read other phases' CSV reports** using column names that do not exist
   (`final_quality_score`, `forecast_quality`) and matched columns by substring, so `quality_slope`
   overwrote `quality_trend`. It also tested for `INCREASING`/`RISING` labels no module ever produced.
5. **Phase 12 "prediction" model** trained a RandomForest to reproduce the rule that generated its own labels
   (missing > 20 % or constant → "risky"), so its accuracy meant nothing.
6. **Phase 17 alerts** fired on a single missing value or duplicate row.
7. **Phase 7/8 uploads** stored files under the client-supplied filename (path traversal / overwrite) and
   returned exception text in HTTP 500 responses.
8. **Phase 11** hard-coded database credentials in source and ignored `.env`.
9. **Phase 6 explanations** chose rows to explain from the ground-truth `is_anomaly` column, which real
   datasets do not have.
10. **Phase 15** imputed missing values *before* removing duplicates, which can create false duplicates.
