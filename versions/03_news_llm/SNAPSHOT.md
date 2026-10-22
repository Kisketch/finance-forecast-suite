# Version 03 — News + LLM + Optimizer Snapshot

Stage: official-source news ingestion, rule/LLM event analysis, price × news fusion, constrained online optimizer, and model access page.

Included here:

- `news-methodology.md` — full methodology and boundaries.
- `news_sources.yaml` — the 14 official sources and tiers.
- `llm.example.json` — OpenAI-compatible model configuration template.
- `forecast.py` — price model used by the combined forecast.
- `news/` — the complete news package (sources, store, analyzer, LLM client, impact, optimizer, service).
- `news.db` — SQLite snapshot at packaging time (165 news items, 14 sources, 2 pending predictions).
- `ui_web/` — the frontend snapshot with the news and model pages.

Key design: official sources only; rule fallback refuses to invent direction; LLM must return strict JSON with prompt-injection defense; weights are bounded (0.05–0.35 total, ±8% region, ±5% category); optimizer needs ≥20 forward samples; the LLM can propose but deterministic guardrails apply.

The authoritative, runnable version is `../../project/`.
