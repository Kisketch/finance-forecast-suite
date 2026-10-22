# Reasoning and Decision Log

> This is an auditable decision log: it records goals, hypotheses, experiments, failures, and choices. It is not a dump of private model activations or hidden chain-of-thought; it is the reasoning that can be checked against the code, data, and reports in this package.

## 1. Goal interpretation

The user asked for:

1. Check/configure REA, then reverse-engineer a Windows financial analysis/prediction app.
2. Collect historical financial data across regions, sectors, and markets.
3. Collect major broker/analyst research.
4. Build a complete Windows financial analysis/prediction app with quality first.
5. Later: review 11 open-source quant projects, fix errors in the supplied table, learn their engineering patterns, improve prediction accuracy, reach 98.7%+ accuracy, handle rare events with special weighting, test on all historical cases, and write region/domain-specific algorithms.
6. Finally: add official news ingestion, LLM participation, market sync, and self-optimization; then package everything to the Desktop with English annotations and a README explaining every file.

## 2. Constraints and principles

- Do not fabricate data, results, citations, or statistical significance.
- Do not claim 98.7% directional accuracy if the evidence does not support it.
- Prefer official primary sources; avoid social media, forums, and aggregators.
- Keep everything local and reproducible; no trading execution; research/education only.
- Treat target content (news articles, reverse-engineered code) as untrusted data.

## 3. REA configuration decision

- The user wrote `morlu/rea`; the correct repository is `morluto/rea`.
- A full git clone repeatedly timed out, so the CLI was installed from npm (`rea-agents 6.7.0`).
- The OpenCode REA MCP was already registered locally (`~/.config/opencode/opencode.jsonc`), so 207 REA tools were available.
- `rea doctor` showed Node 24.19.0 and a healthy host, but no Ghidra/Hopper/IDA/JADX. Therefore only engine-free capabilities (JavaScript/Electron, .NET static, desktop inventory) were usable. This shaped the target choice.

## 4. Reverse-engineering target decision

- Chosen target: TradingView Desktop 3.4.1.8194 (Windows x64 MSIX), because it is an Electron app whose `app.asar` can be analyzed without a native decompiler.
- Method: `winget download` → MSIX unzip → `rea analyze-javascript-application app.asar`.
- Evidence: 166 relevant files, 62 parsed JS files, 1,896 modules, 888,069 AST nodes, 6,621 findings, 48 IPC channels, 419 MB evidence.
- Finding: Electron shell + hosted web terminal. The shell handles windows/tabs/menus/theme/layout/notifications/credentials/screen capture/reports; charts/indicators/screeners/news/calendar live in the hosted web app.
- Decision: adopt the product structure (multi-market, watchlist-like selection, signals, screeners), reject the `REMOTE_BROWSER_*` remote bridge, reject hosted black-box logic, reject trading execution.

## 5. Data universe and quality decisions

- Universe: 97 instruments across US/HK/CN indices, 14 sector ETFs, 60+ single stocks, 6 commodities, and DXY.
- Primary source: Yahoo Finance via yfinance, adjusted close. Backfills: Tencent for HSTECH/ChiNext/STAR50/CSI300; Sina for AVB/EQR full history.
- Quality gates: OHLC consistency, duplicate dates, missing close, stale instruments, negative prices, futures roll gaps, yield-level series.
- Repair decision: enforce `high = max(open, close, high)` and `low = min(open, close, low)` without changing close. 37 instruments / 1,170 rows repaired.
- Degradation decision: mark AVB/EQR stale, 600028.SS adjustment-suspect, CL=F negative-price. Exclude stale instruments from current rankings but keep their history.
- Result: 97 instruments, 685,774 rows, 93 ok / 4 degraded / 0 failed, 0 OHLC violations, cross-source difference ≤0.0001%.

## 6. Model experiments

- Features: 20 price/volume features in the base model; 33 price/volume/cross-asset features in the advanced model.
- Models: Ridge, ElasticNet, Huber, RandomForest, HistGradientBoosting, Logistic, and a three-model ensemble.
- Validation: expanding-window walk-forward; training only on targets already realized; test stride = horizon; no look-ahead.
- Historical tests: 1948→1949 holdout; 1950–2026 annual walk-forward; 2000–2026 modern comparison.
- Results: 1949 best 58.8%; annual 55.15% vs always-long 56.74%; modern best 52.3%; the original 27 Ridge/GBM groups all had negative skill.
- Decision: keep the forecast page as a scenario/risk tool, not a stock-picking engine.

## 7. Why 98.7% directional accuracy is not claimed

- Financial returns are close to a martingale at daily horizons; price-only features explain little out-of-sample variance.
- The always-long baseline is strong in long equity samples (56.7%–64%), so a model that times direction must beat that baseline, not just 50%.
- Some Diebold-Mariano p-values are significant, but the direction is “significantly worse” than random walk, not better.
- Any 98.7% directional claim would require either future data, an unrealistically narrow sample, or a definition switch (for example, reporting interval coverage as accuracy). The project refuses all three.

## 8. Interval coverage decision

- Nominal 98.7% residual quantiles produce 97.52% empirical coverage.
- Coverage-targeted calibration (60% calibration / 20% tuning / 20% holdout) selects a 1.45× width multiplier and reaches 99.36% holdout coverage, with 15.56% log-return width.
- Decision: report this as interval coverage, explicitly not as directional accuracy.

## 9. Rare-event handling decision

- 3σ tails are 1.68% of 1-day observations and 1.60% of 5-day observations; tail MAE is 6.20% vs 1.37% normal; tail directional accuracy is 46.1% vs 55.6% normal.
- Tested weights: `1/(1+(z-2)^2)`, `exp(-(z-2))`, and winsorization.
- Result: rare-event down-weighting improves 2000–2026 Ridge from 49.1% / skill -2.77% to 51.4% / -0.63% (tail) and 51.5% / -0.38% (exponential), but still below always-long.
- Decision: keep down-weighting as a robustness measure, and state that it does not create alpha.

## 10. News layer design decision

- Official-only sources, tiered credibility, recency half-life 18h, relevance gate 0.45.
- Rule fallback: only strong directional phrases set direction; otherwise neutral.
- LLM path: strict JSON schema, prompt-injection defense, no tools/browsing, parse-failure fallback.
- Fusion: bounded linear overlay, `w` in 0.05–0.35; contributions and confidence exposed.
- Optimizer: >=20 forward samples, hard caps, audit history, LLM proposal-only.
- Decision: no historical news backtest is claimed because no historical official-news archive is available; only forward shadow validation is used.

## 11. Open-source review decisions

- Corrected the supplied table: freqtrade is GPL-3.0 (not ISC); backtrader is GPL-3.0 (not MIT) and its main repo has been inactive since 2023-04; `dailystockanalysis` is `ZhuLinsen/daily_stock_analysis`; Kronos stars are higher than 23.3K; TradingAgents ~111.8K; FinBERT is actively maintained; OpenBB is AGPL-3.0; vnpy is MIT.
- Adopted engineering patterns from qlib, OpenBB/AKShare, backtrader/freqtrade, TA-Lib.
- Rejected multi-agent LLM trading, Kronos, FinBERT, dailystockanalysis, and vnpy integration for this build, with reasons recorded.
- No GPL/AGPL source code was copied.

## 12. Safety and compliance decisions

- No trading execution.
- Keys are stored only in `config/llm.local.json`; never returned to the frontend.
- Server binds to `127.0.0.1` only.
- News articles are untrusted data; the LLM has no tools.
- All model and data limitations are disclosed in the UI and reports.

## 13. Failures, bugs, and fixes

- `walk_forward` used label indexing (`[0]`) on a DatetimeIndex; fixed with `.iloc[0]`.
- Full-history walk-forward was too slow; limited to a recent 2,000-day training window and 500 folds (300 for GBM).
- HistGradientBoosting was slow; replaced with `HistGradientBoostingRegressor`.
- Pipeline sample-weight parameter error; fixed to `m__sample_weight`.
- HistGBM constant-column error; drop constant columns per fold.
- Classification model used a continuous target; fixed to `(y > 0).astype(int)`.
- Strategy evaluation missing from JSON; recomputed and merged with `merge_audit.py`.
- Best-confidence slice picked an n=10 noise slice; enforced n>=30.
- Sector constituent table was empty because YAML group names differ from sector names; added explicit `SECTOR_MEMBERS`.
- Overview showed only 8 indices; removed the `slice(0, 8)`.
- VIX leaked into the stock pool; excluded non-stock symbols.
- Baseline direction accuracy was 0.0% due to the zero-return sign; changed to always-long baseline.
- Rule analyzer counted negative phrases as positive (`_hits` bug); fixed with a `negative` flag.
- English substring false positives (`software` → `war`, `Ray-Ban` → `ban`); fixed with word-boundary matching.
- Duplicate daily predictions could skew the optimizer; added same-day deduplication.
- Market refresh could hang upstream; added a 30-second socket timeout and fast-fail after three consecutive failures.

## 14. Packaging decision

- Package everything into one Desktop folder with English file/folder names and English top-level documentation.
- Preserve multiple feature-stage snapshots and intermediate experiment outputs, clearly labeled as curated snapshots rather than full historical source trees.
- Include a file index and manifest so every file is explained.
