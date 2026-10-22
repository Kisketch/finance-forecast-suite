# Licenses and Sources

## 1. Market data sources

- Yahoo Finance via `yfinance` — primary daily OHLCV source; users must comply with Yahoo’s terms.
- Tencent quote API — backfill for Hang Seng TECH, ChiNext, STAR 50, CSI 300.
- Sina Finance — backfill for AVB and EQR full history.
- Official news RSS/HTML sources: Federal Reserve, ECB, Bank of England, USTR, HKSAR Government, HKMA, Shanghai Stock Exchange, China Government (English), IEA, Apple, OpenAI, Google, Meta.

The data is stored locally for research and education. Redistribution may be restricted by the original providers.

## 2. Reviewed open-source projects and licenses

| Project | License (verified) | Use in this package |
|---|---|---|
| TradingAgents | Apache-2.0 | Reviewed only; multi-agent LLM trading not integrated |
| OpenBB Platform | AGPL-3.0 | Engineering pattern only; no code copied |
| daily_stock_analysis | Repository license | Reviewed only; not integrated |
| ai-hedge-fund | MIT | Reviewed only; not integrated |
| qlib | MIT | Engineering pattern only; no code copied |
| vnpy / VeighNa | MIT | Reviewed only; trading gateway not integrated |
| freqtrade | GPL-3.0 (corrected from ISC) | Engineering pattern only; no code copied |
| Kronos | Open source / AAAI 2026 | Reviewed only; not integrated |
| backtrader | GPL-3.0 (corrected from MIT) | Engineering pattern only; no code copied |
| FinBERT | Apache-2.0 (training code); weights need separate check | Reviewed only; not integrated |
| AKShare | MIT | Engineering pattern only; no code copied |
| TA-Lib | BSD | Indicators independently reimplemented |

## 3. Compliance statement

- No GPL or AGPL source code was copied into this project.
- Only publicly documented engineering ideas were used, and the implementations here are independent.
- TradingView is a trademark of its owner. The reverse-engineering work is for interoperability/learning; no TradingView code or assets are redistributed beyond the locally downloaded package needed for analysis.

## 4. Research disclaimer

This project is for research and education. It does not execute trades, does not provide investment advice, and does not guarantee prediction accuracy. All forward-looking outputs are scenarios, not promises.
