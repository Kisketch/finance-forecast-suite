# Check Report

Date: 2026-10-22
Package: `C:\Users\Lgnatius\Desktop\FIN_Terminal_Full_Package_2026-10-22`

## 1. Automated checks (all passed)

| Check | Command | Result |
|---|---|---|
| Python syntax | `py -m compileall -q project\src` | exit 0 |
| Frontend syntax | `node --check project\src\finance_app\ui\web\app.js` | exit 0 |
| API smoke | `py project\scripts\smoke_audit.py` | 18/18 passed |
| News pipeline test | `py project\scripts\test_news_pipeline.py` | passed |
| LLM mock test | `py project\scripts\test_llm_mock.py` | passed |
| LLM API config test | `py project\scripts\test_llm_api.py` | passed |
| Desktop shell | `py -m finance_app.ui.app` | process alive after 9s, no stderr |
| Browser console | news/model/audit pages | 0 errors |
| SQLite integrity | `PRAGMA integrity_check` on `data/news/news.db` | ok |
| JSON validation | 7 key JSON files | all parse |
| Mojibake scan | 103 text files | 0 replacement/mojibake sequences |
| Required files | 21 key paths | all present |

## 2. Data checks

- 97 instruments, 685,774 rows, 1927-12-30 to 2026-10-21.
- 93 normal / 4 degraded / 0 failed.
- OHLC violations: 0 after repair (37 instruments, 1,170 rows repaired without changing close).
- Cross-source close check: SSE 3713.03 vs Tencent 3713.03 (0.0001%); Tencent Holdings 393.80 vs 393.80 (0%).
- Degraded: AVB, EQR (stale after 2026-08), 600028.SS (2013 adjustment suspect), CL=F (negative price).
- Flags: extreme_move 35, front_month_roll 6, yield_level_series 1, ohlc_repaired 37, stale_data 2, negative_price 1, suspect_adjustment 1.

## 3. Accuracy checks

- Directional 98.7%: not reached and not claimed.
  - 1948→1949 best: 58.8% (HistGBM classifier; always-long 49.6%; AUC 0.586; MCC 0.177).
  - 1950–2026 annual: 55.15% vs always-long 56.74%.
  - 2000–2026 modern: 52.3% (ensemble) vs always-long 56.7%; all skill scores negative.
- Interval 98.7%: reached by coverage-targeted calibration: 99.36% coverage, width 15.56% log return.
- High-confidence slice: 61.3% accuracy at 1.6% coverage (n=62).
- Rare-event reweighting (2000–2026 Ridge): 49.1% -> 51.4% (tail) / 51.5% (exponential), but still below always-long.
- Cost-aware strategy: 7.47% annual vs 8.52% buy-and-hold; max drawdown -58.75%.
- Leakage checks: 6/6 passed.

## 4. News checks

- 165 news items; 109 official/multilateral (66%).
- 14 configured official sources; 11 healthy at the latest sync.
- 165 items analyzed in rule mode; 18 items above the relevance threshold contribute to impact.
- Global rule-based news score +0.26 on a -1..1 scale, explicitly labeled low-confidence rule mode.
- Forward predictions: 2 pending; 0 matured; therefore no optimizer weight update yet.
- No LLM configured by default; the app uses the conservative rule fallback.
- LLM path verified with a local mock OpenAI server (config save, connection test, JSON analysis, fallback).

## 5. Known issues

1. **Market refresh upstream**: during packaging, Yahoo Finance returned empty responses/hung. The script now sets a 30-second socket timeout and fast-fails if the first three symbols fail, preserving the complete existing dataset. Re-run later from the **News Events → Sync Market** button.
2. **News layer has no historical archive**: only forward shadow validation is possible; no historical news backtest is claimed.
3. **LLM output can be wrong**: JSON structure is validated, but facts are not guaranteed; every event card keeps the official source link.
4. **Directional 98.7% is not achievable with the current data**: adding news and LLM does not change this into a promise.
5. **Futures roll gaps and stale instruments** are flagged, not silently removed.

## 6. No-bug statement

No blocking bug was found in the tested paths. “Zero bug” cannot be mathematically proven; the statement above is the scope of what was tested.
