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

11. **Sublinear accumulation of correlated evidence.** *(v0.5)*
    Title-level Jaccard dedup only removes near-duplicates; distinct texts reporting the same fact (e.g., three officials commenting on one rate decision) still inflate Σw and over-trust the news layer. Events sharing (event_type, region) get weight ×0.5^(n-1) by descending rank — correlated evidence accrues sublinearly instead of being double-counted.

12. **Data-driven link function for the fusion scale.** *(v0.5)*
    The news-score→log-return scale is no longer a hand-picked constant table: it uses the realized volatility of the forecast horizon (scale ≈ σ_h, i.e. "a score-1 event ≈ one horizon standard deviation"), clamped to [0.006, 0.08], with the constant table (≈1.2%×√T) kept only as a fallback.

13. **Volatility-regime conditioning.** *(v0.5)*
    The 20-day realized-vol percentile over the past year conditions a news multiplier (low-vol ×1.15, high-vol ×0.85, configurable): news carries relatively more information when the price signal is quiet, and is discounted when noise dominates.

14. **Online calibration of LLM confidence.** *(v0.5)*
    Raw LLM confidence enters the multiplicative evidence weight only after bucket-wise calibration (lo/mid/hi) against forward hit rates with a Beta(2,2) prior; multipliers are clamped to [0.3, 1.5] and fall back to identity when unestimated — the least reliable number in the chain no longer sits unchecked at its core.

15. **Inverse-MSE weight updates with an abstention floor.** *(v0.5)*
    Once ≥30 realized shadow predictions exist, news_weight targets 0.05 + 0.30 × mae_price/(mae_price+mae_news) — a two-component Granger–Ramanathan special case: equally accurate → 0.20, perfect news → the 0.35 cap, no skill → the 0.05 floor. Below 30 samples the original directional-hit rule applies; the active rule is recorded in the audit history.

16. **Incremental-skill reporting instead of marginal hit rates.** *(v0.5)*
    performance() reports the paired per-row directional hit difference (news vs price) with a 95% CI, flagging significance only at n≥30 with the interval excluding zero, plus a q05/q95 empirical (split-conformal style) residual interval for combined predictions at n≥20 — directly answering "does the news layer know more than the price prior?" rather than implying it from two marginal rates.
