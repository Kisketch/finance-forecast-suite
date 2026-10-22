# Version 02 — Accuracy Audit Snapshot

Stage: 1948→1949 holdout, annual walk-forward, interval calibration, rare-event reweighting, and open-source review.

Included here:

- `accuracy-audit.md` — the full audit report.
- `advanced_audit.json` — raw audit results (historical holdout, annual regression/classification, interval calibration, coverage-targeted calibration, confidence curve, rare events, strategy evaluation, rare-weight experiment, modern model comparison, regional models, leakage checks).
- `rare_weight_experiment.json` — rare-event down-weighting comparison.
- `open-source-quant-review.md` — review and corrections for the 11 supplied open-source projects.
- `advanced.py` — the advanced model implementation at this stage.
- `audit.png` — audit page screenshot.

Key results: 1949 best 58.8%; 1950–2026 annual 55.15% vs always-long 56.74%; 2000–2026 modern 52.3%; interval 98.7% target reached at 99.36% coverage; high-confidence slice 61.3% at 1.6% coverage; rare-event reweighting 49.1% → 51.4–51.5%; cost-aware strategy 7.47% vs 8.52% buy-and-hold; leakage 6/6.

The authoritative, runnable version is `../../project/`.
