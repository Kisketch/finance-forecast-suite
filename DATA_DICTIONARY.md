# Data Dictionary

## 1. `project/data/processed/prices_long.csv`

Long-format daily price table.

| Column | Meaning |
|---|---|
| date | Trading date (YYYY-MM-DD) |
| open / high / low / close | Adjusted OHLC (Yahoo auto-adjusted where applicable) |
| volume | Reported volume (may be 0 for some indices) |
| symbol | Instrument code (e.g., `^GSPC`, `0700.HK`, `600519.SS`, `CL=F`) |
| name_cn | Chinese display name |
| name_en | English display name |
| market | `US`, `HK`, `CN`, or `GLOBAL` |
| group | Source grouping from `config/universe.yaml` |

## 2. `project/data/metadata/data_quality.json`

Per-instrument quality report.

| Field | Meaning |
|---|---|
| status | `ok`, `degraded`, or `failed` |
| rows | Number of daily rows |
| start / end | First and last date |
| last_close | Last close |
| null_close | Missing close count |
| zero_volume_pct | Share of zero-volume days |
| max_abs_daily_return | Largest absolute daily return |
| extreme_days | Days with |return| > 25% |
| flags | `short_history`, `stale_data`, `extreme_move`, `front_month_roll`, `negative_price`, `yield_level_series`, `ohlc_repaired`, `suspect_adjustment`, `missing_close`, `zero_volume` |

## 3. `project/data/news/news.db` (SQLite)

### `news`

| Column | Meaning |
|---|---|
| id | SHA1-derived item ID |
| source_id / source_name / source_tier | Official source identity and tier |
| region / category / language | Source metadata |
| title / summary / url | Item content and link |
| published_at / fetched_at | UTC timestamps |
| date_estimated | 1 if the date was inferred from the URL or fetch time |
| meta_json | Extra metadata |
| analysis_json / analysis_model / analyzed_at | Event analysis and method |

Analysis JSON fields: `event_type`, `direction`, `magnitude`, `confidence`, `horizon_days`, `regions`, `sectors`, `entities`, `novelty`, `relevance`, `rationale`, `key_facts`, `method`, `credibility`.

### `source_health`

| Column | Meaning |
|---|---|
| source_id / name | Official source |
| checked_at | Last sync time |
| ok | 1 success / 0 failure |
| fetched / kept | Items fetched / items kept after filtering |
| elapsed_ms | Fetch duration |
| error | Error text if failed |

### `predictions`

| Column | Meaning |
|---|---|
| created_at | Prediction time |
| symbol / region / horizon / model | Forecast identity |
| last_date / last_close | Price anchor |
| price_logret | Price-model expected log return |
| news_score | News impact score in -1..1 |
| combined_logret | Weighted combined expected log return |
| weights_json | Weights used |
| news_ids_json | Evidence item IDs |
| actual_logret / evaluated_at | Realized outcome after maturity |

## 4. `project/config/news_sources.yaml`

Official source registry. Each source has `id`, `name`, `type` (`rss` or `html`), `url`, `tier`, `region`, `category`, `language`, optional `link_regex`, optional `article_fetch`, and `max_items`.

## 5. `project/data/research/open_source_projects.json`

Normalized review of the 11 open-source quant projects: project, category, stars snapshot, license, maintenance, reliability, adoption decision, and risk.

## 6. API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/meta` | GET | Dataset metadata |
| `/api/overview` | GET | Indices, sectors, breadth, correlation, signals |
| `/api/universe` | GET | Instrument list with staleness and flags |
| `/api/series` | GET | OHLCV plus indicators for one symbol |
| `/api/sector` | GET | Sector ETF, relative strength, constituents |
| `/api/forecast` | GET | Walk-forward forecast for symbol/horizon/model |
| `/api/analysts` | GET | Broker/analyst views |
| `/api/quality` | GET | Data-quality report |
| `/api/audit` | GET | Accuracy audit results |
| `/api/projects` | GET | Open-source review |
| `/api/news` | GET | News list with filters |
| `/api/news/stats` | GET | News counts by source/region |
| `/api/news/impact` | GET | Region/sector impact scores |
| `/api/news/sources` | GET | Source health |
| `/api/news/performance` | GET | Forward shadow validation |
| `/api/llm/status` | GET | LLM configuration status (no key) |
| `/api/optimizer/status` | GET | Weights, performance, history |
| `/api/market/sync/status` | GET | Market refresh status |
| `/api/news/sync` | POST | Sync official news |
| `/api/news/analyze` | POST | Analyze new or existing items (rule/LLM) |
| `/api/news/predict` | POST | Generate combined price × news forecast |
| `/api/news/evaluate` | POST | Evaluate matured predictions |
| `/api/optimizer/update` | POST | Constrained weight update |
| `/api/optimizer/propose` | POST | Ask LLM for a bounded proposal |
| `/api/optimizer/apply` | POST | Apply a bounded proposal |
| `/api/llm/test` | POST | Test the configured endpoint |
| `/api/llm/config` | POST | Save endpoint/model/key locally |
| `/api/market/sync` | POST | Start a background market refresh |
