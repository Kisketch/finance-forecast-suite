# Innovations

1. **Official-source-only event layer with source tiers.**
   Government/central-bank/regulator/exchange sources carry weight 1.0, multilateral 0.9, company newsrooms 0.8. Social media, forums, and aggregators are excluded by design. Failed official sources are shown, never silently replaced.

2. **Conservative rule fallback that refuses to invent direction.**
   If no strong directional term is present, the rule analyzer returns direction 0 and confidence 0.15 instead of manufacturing a sentiment. English phrases use word-boundary matching to avoid false positives such as `software` → `war` and `Ray-Ban` → `ban`.

3. **LLM event analysis with a strict JSON contract and prompt-injection defense.**
   The model must return a fixed schema (`event_type`, `direction`, `magnitude`, `confidence`, `horizon_days`, `regions`, `sectors`, `entities`, `novelty`, `relevance`, `rationale`, `key_facts`). Article text is treated as untrusted data; the model has no browsing or tool access; parse failures fall back to the rule analyzer.

4. **Transparent price × news fusion.**
   `combined = (1-w) × price_logret + w × news_logret`, with `w` bounded to 0.05–0.35 and driven by source tier, recency half-life (18h), confidence, novelty, magnitude, and relevance. Every output includes price contribution, news contribution, agreement, and confidence.

5. **Constrained online optimizer, not self-modifying code.**
   Weights update only after >=20 forward samples, with hard caps (±0.05 total, ±8% region, ±5% category) and a full audit history. The LLM can propose changes, but the deterministic guardrails still apply.

6. **Honest 98.7% audit with separated concepts.**
   Directional accuracy and interval coverage are reported separately. The project proves 99.36% interval coverage is achievable while refusing to label it as directional accuracy.

7. **Rare-event reweighting with measured limits.**
   Tail events (3σ) are only 1.68% of days but have much larger errors (6.20% vs 1.37% MAE). Down-weighting improves MAE and generalization (49.1% → 51.4–51.5%), but it does not create alpha; the project reports the residual gap to always-long.

8. **Data-quality-first engineering.**
   Cross-source backfills, OHLC repair without changing close, stale-instrument exclusion from current rankings, futures roll-gap flags, and per-instrument degradation reasons.

9. **REA-based reverse engineering of a real Windows financial app.**
   TradingView Desktop 3.4.1.8194 was unpacked from MSIX and analyzed statically: 1,896 modules, 888,069 AST nodes, 6,621 findings, 48 IPC channels, with a documented Electron-shell + hosted-web-terminal architecture.

10. **Reproducible packaging.**
    Every report, raw dataset, script, and evidence file is preserved, with a file index, manifest, version snapshots, and an auditable decision log.
