# Usage Guide

## 1. Requirements

- Windows 10/11 x64
- Python 3.11+ (tested on 3.14.7)
- Node.js 24 only if you want to reproduce the REA reverse-engineering step
- Edge WebView2 (bundled with Windows 10/11) for the desktop shell

## 2. Install

```powershell
cd "C:\Users\Lgnatius\Desktop\FIN_Terminal_Full_Package_2026-10-22\project"
py -m pip install -r requirements.txt
```

## 3. Run the desktop app

```powershell
.\run.ps1
```

Or run only the local API and open it in a browser:

```powershell
.\run_server.ps1
# http://127.0.0.1:8765
```

## 4. Pages

| Page | What it does |
|---|---|
| Overview | 10 global indices, sector heatmap, breadth, cross-asset correlation, technical signals |
| Markets | US / Hong Kong / China cross-sections, normalized index chart, breadth |
| Sectors | Real estate, energy, oil & gas, clean energy, tech, finance, utilities; relative strength and constituents |
| Stock | Candlestick, MA20/50/200, BOLL, volume, RSI, MACD, momentum/risk |
| Forecast Lab | Ridge / GBM / RandomForest / ensemble walk-forward backtest, random-walk baseline, 90% scenario band |
| News Events | Official-source news, event analysis, region/sector impact, combined forecast, evidence chain |
| Model Access | OpenAI-compatible endpoint, local key storage, constrained optimizer, forward validation, source health |
| Accuracy Audit | 1948→1949 holdout, 1950–2026 annual, 98.7% verdict, interval calibration, confidence curve, rare-event reweighting, regional models, open-source compliance |
| Broker Views | Public views from Goldman Sachs, Morgan Stanley, JPM, UBS, CICC, CITIC, Huatai, IEA, JLL, Deloitte |
| Data Quality | Per-instrument coverage, missing values, anomalies, degradation reasons |

## 5. Connect your own model

The app supports any OpenAI-compatible endpoint. Examples:

- Ollama: `http://127.0.0.1:11434/v1`, model `qwen2.5:7b`, key empty
- LM Studio: `http://127.0.0.1:1234/v1`
- vLLM: `http://127.0.0.1:8000/v1`
- DeepSeek/OpenAI: their official base URL and key

Steps:

1. Open **Model Access**.
2. Fill Base URL, Model, API Key.
3. Click **Save Config**, then **Test Connection**.
4. Go to **News Events** and click **Model Re-analysis** to upgrade existing rule-based analyses to LLM analyses (8 items per click).
5. Click **Generate Combined Forecast** for a selected symbol/horizon.

The key is stored only in `project/config/llm.local.json` and is never sent to the frontend.

## 6. Daily update

```powershell
cd "C:\Users\Lgnatius\Desktop\FIN_Terminal_Full_Package_2026-10-22\project"
py scripts\daily_update.py
```

This runs: market fetch -> backfills -> quality repair -> validation -> news sync -> analysis -> forward evaluation -> constrained weight update.

News-only update:

```powershell
py scripts\daily_update.py --skip-market --no-llm
```

## 7. In-app sync buttons

- **Sync Official News**: pulls the 14 official sources into SQLite and records per-source health.
- **Analyze Pending**: analyzes only new, unanalyzed items.
- **Model Re-analysis**: overwrites existing rule analyses with the configured LLM (8 items per click).
- **Sync Market**: runs market fetch, backfills, quality repair, and validation in the background; the page refreshes when done.

## 8. Troubleshooting

- **No news**: click **Sync Official News**; check **Model Access → Official Source Health** for failures.
- **Model test fails**: verify the base URL ends with `/v1`, the model name matches what the server reports, and the endpoint is reachable from this machine.
- **Market sync stops early**: upstream Yahoo may be rate-limiting. The script fast-fails on the first three consecutive symbol failures and keeps the old dataset.
- **Desktop window does not open**: run `.\run_server.ps1` and open `http://127.0.0.1:8765`; if the API works, the issue is the WebView2 runtime.
- **Port already in use**: stop the process on port 8765, or change the port in `src/finance_app/ui/app.py` / `server.py`.

## 9. Reproduction commands

```powershell
py src\finance_app\data\fetch_market.py
py scripts\patch_indices.py
py scripts\finalize_quality.py
py scripts\repair_ohlc.py
py scripts\validate_all.py
py scripts\build_analysis.py
py scripts\sync_news.py
py scripts\analyze_news.py --limit 20 --no-llm
py scripts\run_advanced_audit.py
py scripts\final_check.py
```
