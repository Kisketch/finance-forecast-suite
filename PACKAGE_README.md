# FIN Terminal — Full Package

Package date: 2026-10-22
Package folder: `C:\Users\Lgnatius\Desktop\FIN_Terminal_Full_Package_2026-10-22`

## What this package contains

1. `project/` — the complete, runnable project (source, data, reports, reverse-engineering evidence, screenshots).
2. `versions/` — curated feature-stage snapshots with English annotations.
3. `intermediate_materials/` — raw-data index, diagnostics scripts, experiment outputs, reverse-engineering notes.
4. Top-level English documents — usage, checks, reasoning/decision log, innovations, data dictionary, licenses, user requests, chat log, file index, manifest.

## Quick start

```powershell
cd "C:\Users\Lgnatius\Desktop\FIN_Terminal_Full_Package_2026-10-22\project"
py -m pip install -r requirements.txt
.\run.ps1
```

Then open the **Model Access** page to connect your own OpenAI-compatible model (Ollama / LM Studio / vLLM / DeepSeek / OpenAI), and use **News Events** to sync official sources and generate a combined forecast.

## One-paragraph result summary

The project builds a local multi-market terminal for US, Hong Kong, and China equities, real estate, oil/energy, commodities, and cross-asset analysis. It contains 97 instruments and 685,774 daily rows (1927-12-30 to 2026-10-21), with 93 normal / 4 degraded / 0 failed instruments, zero OHLC violations, and cross-source close checks within 0.0001%. It also adds an official-source news layer (14 configured official sources, 11 healthy at the latest sync), a rule/LLM event analyzer, a transparent news-weight overlay, and a constrained online weight optimizer. The accuracy audit shows that 98.7% directional accuracy is not reachable out of sample (best 1949 holdout 58.8%; 1950–2026 annual 55.15% vs 56.74% always-long; 2000–2026 modern 52.3%), while 98.7% interval coverage is reachable (targeted calibration: 99.36% coverage with 15.56% log-return width). The project never fabricates the 98.7% directional claim.

## Key numbers

| Item | Result |
|---|---:|
| Instruments / rows | 97 / 685,774 |
| Date range | 1927-12-30 to 2026-10-21 |
| Data quality | 93 ok / 4 degraded / 0 failed |
| OHLC violations | 0 |
| Cross-source close difference | <= 0.0001% |
| 1948→1949 directional holdout | 58.8% best |
| 1950–2026 annual directional | 55.15% vs 56.74% always-long |
| 2000–2026 modern directional | 52.3% best |
| 98.7% interval coverage (targeted) | 99.36% |
| High-confidence slice | 61.3% accuracy at 1.6% coverage |
| Rare-event reweighting (2000–2026) | 49.1% -> 51.4% / 51.5% |
| Cost-aware strategy | 7.47% annual vs 8.52% buy-and-hold |
| Leakage checks | 6/6 passed |
| Official news items | 165 (109 official/multilateral, 66%) |
| News sources | 14 configured / 11 healthy |
| API smoke | 18/18 passed |
| Text mojibake scan | 0 |

## Important boundaries

- 98.7% directional accuracy is not claimed. Only interval coverage reaches 98.7%+.
- The news layer has no historical news archive, so it is evaluated only as a forward shadow test. It does not claim historical alpha.
- The app does not execute trades and is for research/education only.
- The market-data refresh depends on Yahoo Finance. During packaging, the upstream returned empty responses; the refresh fast-fails and preserves the existing complete dataset instead of overwriting it with partial data.

## Conversation record

- `USER_REQUESTS.md` — verbatim key requirements from the user.
- `CHAT_LOG.md` — chronological actions and results across all phases.
- `REASONING_AND_DECISIONS.md` — the full auditable reasoning/decision chain.
- Raw token-level transcripts and hidden model activations are not included; all produced artifacts, experiment outputs, and evidence files are preserved in `project/`, `versions/`, and `intermediate_materials/`.

## Where to look first

- `project/README.md` — the project’s own Chinese README.
- `USAGE.md` — step-by-step usage.
- `CHECK_REPORT.md` — verification results and known issues.
- `REASONING_AND_DECISIONS.md` — the full auditable reasoning/decision chain.
- `INNOVATIONS.md` — what is novel in this build.
- `project/analysis/accuracy-audit.md` — the 98.7% audit.
- `project/analysis/news-methodology.md` — official news + LLM + weighting methodology.
- `project/analysis/reverse/tradingview-reverse-report.md` — REA reverse-engineering report.
