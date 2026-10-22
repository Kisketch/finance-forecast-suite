# Intermediate Materials

This folder preserves the working material between the final deliverables.

## Contents

- `diagnostics_scripts/` — the exploratory scripts used to test data sources, feed discovery, anomaly inspection, OHLC repair, cross-source checks, and LLM behavior. These are kept for reproducibility, not as the main pipeline.
- `experiment_outputs/` — machine-readable outputs from the validation, market statistics, forecast, audit, rare-event, and walk-forward experiments.
- `reverse_engineering_notes/` — the REA summary and application-facts extracts for TradingView Desktop (IPC channels, paths, keywords).
- `raw_data_index.csv` — an index of the 100 raw source files under `project/data/raw/`, with relative path and size.

## Main pipeline

The authoritative pipeline scripts are in `project/scripts/`:

- `sync_news.py`, `analyze_news.py`, `daily_update.py`
- `patch_indices.py`, `finalize_quality.py`, `repair_ohlc.py`, `validate_all.py`
- `build_analysis.py`, `run_advanced_audit.py`, `rare_weight_experiment.py`
- `smoke_audit.py`, `final_check.py`

## Notes

- The large REA evidence file (`rea-analysis.json`, 419 MB) and the TradingView MSIX are stored once under `project/reverse/tradingview/`, not duplicated here.
- The raw data is stored under `project/data/raw/`; this folder only indexes it.
