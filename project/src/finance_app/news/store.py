"""官方新闻与预测记录的本地 SQLite 存储。"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .sources import NewsItem, SourceResult

from .._paths import ROOT

DEFAULT_DB = ROOT / "data" / "news" / "news.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  source_name TEXT,
  source_tier TEXT,
  region TEXT,
  category TEXT,
  language TEXT,
  title TEXT NOT NULL,
  summary TEXT,
  url TEXT,
  published_at TEXT,
  fetched_at TEXT,
  date_estimated INTEGER DEFAULT 0,
  meta_json TEXT DEFAULT '{}',
  analysis_json TEXT,
  analysis_model TEXT,
  analyzed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_source ON news(source_id);
CREATE INDEX IF NOT EXISTS idx_news_analyzed ON news(analyzed_at);
CREATE TABLE IF NOT EXISTS source_health (
  source_id TEXT PRIMARY KEY,
  name TEXT,
  checked_at TEXT,
  ok INTEGER,
  fetched INTEGER,
  kept INTEGER,
  elapsed_ms INTEGER,
  error TEXT
);
CREATE TABLE IF NOT EXISTS predictions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT,
  symbol TEXT,
  region TEXT,
  horizon INTEGER,
  model TEXT,
  last_date TEXT,
  last_close REAL,
  price_logret REAL,
  news_score REAL,
  combined_logret REAL,
  weights_json TEXT,
  news_ids_json TEXT,
  actual_logret REAL,
  evaluated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pred_symbol ON predictions(symbol, created_at DESC);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class NewsStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or DEFAULT_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(SCHEMA)
            con.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def upsert(self, items: Iterable[NewsItem]) -> dict:
        new = dup = 0
        now = _utc_now()
        with self._conn() as con:
            for item in items:
                try:
                    con.execute(
                        """INSERT INTO news(id, source_id, source_name, source_tier, region, category,
                           language, title, summary, url, published_at, fetched_at, date_estimated, meta_json)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (item.id, item.source_id, item.source_name, item.source_tier, item.region,
                         item.category, item.language, item.title, item.summary, item.url,
                         item.published_at, item.fetched_at, int(item.date_estimated),
                         json.dumps(item.meta or {}, ensure_ascii=False)),
                    )
                    new += 1
                except sqlite3.IntegrityError:
                    dup += 1
        return {"new": new, "duplicates": dup, "checked_at": now}

    def _row(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["analysis"] = json.loads(d.pop("analysis_json") or "null")
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
        d["date_estimated"] = bool(d.get("date_estimated"))
        return d

    def list(self, limit: int = 80, region: str | None = None, category: str | None = None,
             tier: str | None = None, analyzed: bool | None = None, hours: int | None = None,
             q: str | None = None) -> list[dict]:
        where, args = [], []
        if region and region != "ALL":
            where.append("region = ?"); args.append(region)
        if category and category != "ALL":
            where.append("category = ?"); args.append(category)
        if tier and tier != "ALL":
            where.append("source_tier = ?"); args.append(tier)
        if analyzed is True:
            where.append("analysis_json IS NOT NULL")
        elif analyzed is False:
            where.append("analysis_json IS NULL")
        if hours:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
            where.append("published_at >= ?"); args.append(cutoff)
        if q:
            where.append("(title LIKE ? OR summary LIKE ?)"); args += [f"%{q}%", f"%{q}%"]
        sql = "SELECT * FROM news"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY published_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 500)))
        with self._conn() as con:
            return [self._row(r) for r in con.execute(sql, args).fetchall()]

    def get(self, news_id: str) -> dict | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
            return self._row(row) if row else None

    def unanalyzed(self, limit: int = 20) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM news WHERE analysis_json IS NULL ORDER BY published_at DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
            return [self._row(r) for r in rows]

    def reset_analysis(self) -> int:
        with self._conn() as con:
            cur = con.execute("UPDATE news SET analysis_json=NULL, analysis_model=NULL, analyzed_at=NULL")
            return int(cur.rowcount)

    def save_analysis(self, news_id: str, analysis: dict, model: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE news SET analysis_json = ?, analysis_model = ?, analyzed_at = ? WHERE id = ?",
                (json.dumps(analysis, ensure_ascii=False), model, _utc_now(), news_id),
            )

    def delete_source(self, source_id: str) -> int:
        with self._conn() as con:
            cur = con.execute("DELETE FROM news WHERE source_id = ?", (source_id,))
            return int(cur.rowcount)

    def stats(self) -> dict:
        with self._conn() as con:
            total = con.execute("SELECT COUNT(*) FROM news").fetchone()[0]
            analyzed = con.execute("SELECT COUNT(*) FROM news WHERE analysis_json IS NOT NULL").fetchone()[0]
            official = con.execute("SELECT COUNT(*) FROM news WHERE source_tier IN ('official','multilateral','exchange')").fetchone()[0]
            today = datetime.now(timezone.utc).date().isoformat()
            today_n = con.execute("SELECT COUNT(*) FROM news WHERE substr(published_at,1,10) = ?", (today,)).fetchone()[0]
            latest = con.execute("SELECT MAX(published_at) FROM news").fetchone()[0]
            by_source = [dict(r) for r in con.execute(
                "SELECT source_id, source_name, COUNT(*) n, MAX(published_at) latest FROM news GROUP BY source_id ORDER BY n DESC"
            ).fetchall()]
            by_region = [dict(r) for r in con.execute(
                "SELECT region, COUNT(*) n FROM news GROUP BY region ORDER BY n DESC"
            ).fetchall()]
        return {"total": total, "analyzed": analyzed, "unanalyzed": total - analyzed,
                "official": official, "today": today_n, "latest": latest,
                "by_source": by_source, "by_region": by_region}

    def record_health(self, result: SourceResult, kept: int) -> None:
        with self._conn() as con:
            con.execute(
                """INSERT INTO source_health(source_id,name,checked_at,ok,fetched,kept,elapsed_ms,error)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_id) DO UPDATE SET name=excluded.name, checked_at=excluded.checked_at,
                   ok=excluded.ok, fetched=excluded.fetched, kept=excluded.kept,
                   elapsed_ms=excluded.elapsed_ms, error=excluded.error""",
                (result.source.id, result.source.name, _utc_now(), int(result.error is None),
                 result.fetched, kept, result.elapsed_ms, result.error),
            )

    def source_health(self) -> list[dict]:
        with self._conn() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM source_health ORDER BY ok DESC, source_id"
            ).fetchall()]

    def save_prediction(self, row: dict) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
        with self._conn() as con:
            existing = con.execute(
                """SELECT id FROM predictions WHERE symbol=? AND horizon=? AND model=? AND last_date=?
                   AND created_at >= ? ORDER BY id DESC LIMIT 1""",
                (row["symbol"], int(row["horizon"]), row.get("model"), row.get("last_date"), cutoff),
            ).fetchone()
            if existing:
                con.execute(
                    """UPDATE predictions SET price_logret=?, news_score=?, combined_logret=?,
                       weights_json=?, news_ids_json=?, created_at=? WHERE id=?""",
                    (row.get("price_logret"), row.get("news_score"), row.get("combined_logret"),
                     json.dumps(row.get("weights") or {}, ensure_ascii=False),
                     json.dumps(row.get("news_ids") or [], ensure_ascii=False),
                     _utc_now(), int(existing["id"])),
                )
                return int(existing["id"])
            cur = con.execute(
                """INSERT INTO predictions(created_at,symbol,region,horizon,model,last_date,last_close,
                   price_logret,news_score,combined_logret,weights_json,news_ids_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (_utc_now(), row["symbol"], row.get("region"), int(row["horizon"]), row.get("model"),
                 row.get("last_date"), row.get("last_close"), row.get("price_logret"),
                 row.get("news_score"), row.get("combined_logret"),
                 json.dumps(row.get("weights") or {}, ensure_ascii=False),
                 json.dumps(row.get("news_ids") or [], ensure_ascii=False)),
            )
            return int(cur.lastrowid)

    def pending_predictions(self, limit: int = 200) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM predictions WHERE actual_logret IS NULL ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def evaluated_predictions(self, limit: int = 500) -> list[dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM predictions WHERE actual_logret IS NOT NULL ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["weights"] = json.loads(d.pop("weights_json") or "{}")
                d["news_ids"] = json.loads(d.pop("news_ids_json") or "[]")
                out.append(d)
            return out

    def all_predictions(self, limit: int = 100) -> list[dict]:
        with self._conn() as con:
            rows = con.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["weights"] = json.loads(d.pop("weights_json") or "{}")
                d["news_ids"] = json.loads(d.pop("news_ids_json") or "[]")
                out.append(d)
            return out

    def set_actual(self, pred_id: int, actual: float) -> None:
        with self._conn() as con:
            con.execute("UPDATE predictions SET actual_logret = ?, evaluated_at = ? WHERE id = ?",
                        (float(actual), _utc_now(), int(pred_id)))
