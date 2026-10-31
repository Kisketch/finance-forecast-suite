# Version Notes

This package preserves multiple feature-stage snapshots. They are **curated snapshots**, not complete historical source trees; the authoritative current source is always `project/`.

| Version | Stage | Included in package | Notes |
|---|---|---|---|
| v0.1 | Core terminal | `versions/01_core_terminal/` | Original 8-page terminal: overview, markets, sectors, stock, forecast lab, broker views, data quality, plus the first 27-group Ridge/GBM backtests (all negative skill). |
| v0.2 | Accuracy audit | `versions/02_accuracy_audit/` | Added 1948→1949 holdout, 1950–2026 annual walk-forward, 2000–2026 modern comparison, interval calibration, coverage-targeted 98.7% interval, high-confidence slice, rare-event reweighting, regional models, open-source project review, and the audit page. |
| v0.3 | News + LLM + optimizer | `versions/03_news_llm/` | Added official-source ingestion, rule/LLM event analysis, region/sector impact, price × news fusion, constrained online optimizer, forward shadow validation, model access page, source health, market sync. |
| v0.4 | AI 增强预测 + 官方基本面源 + exe 交付 | `project/` | 新增 `models/ml_advanced.py`（ADX/KDJ/波动率 regime/季节/量价背离特征 + isotonic 概率校准集成 + 时间衰减样本权重 + 选择性输出）；2000-2026 全程方向准确率 52.3%→56.53%（追平始终看多），有信号日（51.4% 覆盖）57.14%（超始终看多）。新增 `data/sec_edgar.py`（SEC EDGAR 官方财务数据源，免费无 Key）。修复 1 高危（中文源 GBK 乱码）+ 12 中危（去重顺序/时效权重/LLM 重试/YAML 解析/路径穿越/分析互斥/零值偏倚/调度日志等）。PyInstaller onedir 打包 `dist/FIN_Terminal/FIN_Terminal.exe`。 |
| v0.5 | 新闻层算法升级 | `project/`（本次） | `news/impact.py`：同簇证据收益递减（同 event_type×region 第 n 条 ×0.5^(n-1)，抑制相关证据重复计数）；融合尺度改用 horizon 期已实现波动率 σ_h（数据驱动 link function，钳 [0.006,0.08]，常数表兜底）；波动率 regime 乘子（低波动 ×1.15 / 高波动 ×0.85，可配置）；LLM confidence 分桶在线校准（Beta(2,2) 平滑，乘子钳 [0.3,1.5]）。`news/optimizer.py`：≥30 样本改用逆 MSE 目标更新 news_weight（两分量 Granger–Ramanathan 特例，同精度→0.20、无技能→趋 0.05）；performance 新增增量技能配对 95% CI 与 combined 残差 q05/q95 轻量共形区间；修复 apply_proposal 重复定义导致的 10 分钟频控失效与 mae_price=0 边界。新增 `scripts/test_news_upgrades.py`（24 项离线回归）。旧权重文件自动合并新键，向后兼容。 |
| current | Packaged state | `project/` | v0.5 plus final checks, packaging docs, and the latest bug fixes. |

## What is preserved where

- `versions/01_core_terminal/legacy_27_backtests.json` — the original 27-group backtest output.
- `versions/01_core_terminal/screenshots/` — early overview and forecast screenshots.
- `versions/02_accuracy_audit/advanced_audit.json` — full audit results.
- `versions/02_accuracy_audit/rare_weight_experiment.json` — rare-event weighting comparison.
- `versions/02_accuracy_audit/advanced.py` — the advanced model implementation at that stage.
- `versions/03_news_llm/news/` — the complete news package.
- `versions/03_news_llm/news.db` — the news database snapshot (165 items at packaging).
- `versions/03_news_llm/news-methodology.md` — news methodology.

## Important

- Earlier versions are not guaranteed to run as-is if their source was later modified; the runnable, verified version is `project/`.
- Data files are not duplicated inside every version; the current dataset is `project/data/processed/prices_long.csv`.
- The reverse-engineering evidence is stored once in `project/reverse/tradingview/` to avoid duplicating the 419 MB analysis file.
