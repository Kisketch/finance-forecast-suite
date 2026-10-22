"""受限在线优化：用已实现的前向预测更新新闻权重。

不是“让模型改代码”，而是：
- 只在样本数 >= min_samples 时更新；
- 单次新闻总权重变化 <= ±0.05，区域权重变化 <= ±8%；
- 所有权重有硬边界，全部变更写入 history；
- LLM 只能“提议”，应用前仍走同样的边界与审计。
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

from .impact import DEFAULT_WEIGHTS, load_weights, save_weights
from .llm import LLMClient
from .store import NewsStore


def evaluate_predictions(store: NewsStore, data_store, max_eval: int = 300) -> dict:
    pending = store.pending_predictions(limit=max_eval)
    evaluated = 0
    errors = []
    for p in pending:
        try:
            df = data_store.get(p["symbol"])
            if df is None or df.empty or not p.get("last_date"):
                continue
            last = pd.Timestamp(p["last_date"])
            if last not in df.index:
                pos = int(df.index.searchsorted(last))
                if pos >= len(df.index):
                    continue
                last = df.index[pos]
            i = int(df.index.get_loc(last))
            j = i + int(p["horizon"])
            if j >= len(df):
                continue
            c0, c1 = float(df["close"].iloc[i]), float(df["close"].iloc[j])
            if c0 <= 0 or c1 <= 0:
                continue
            store.set_actual(int(p["id"]), math.log(c1 / c0))
            evaluated += 1
        except Exception as exc:  # noqa: BLE001
            errors.append({"id": p.get("id"), "error": f"{type(exc).__name__}: {exc}"})
    return {"evaluated": evaluated, "pending": len(pending) - evaluated, "errors": errors[-10:]}


def _hit(a: float, b: float) -> bool:
    """方向命中判定。零分预测(|score|<1e-9)不计入命中——避免"零分==非正"
    的系统性偏倚（此前 score=0 在 actual<0 时被计为命中、actual>0 时计为 miss）。"""
    try:
        a = float(a); b = float(b)
    except (TypeError, ValueError):
        return False
    if abs(a) < 1e-9 or abs(b) < 1e-9:
        return False
    return (a > 0) == (b > 0)


def _hit_valid(a: float, b: float) -> bool:
    """是否应计入命中率分母（非零预测）。"""
    try:
        return abs(float(a)) >= 1e-9
    except (TypeError, ValueError):
        return False


def performance(store: NewsStore) -> dict:
    rows = store.evaluated_predictions(limit=1000)
    if not rows:
        return {"n": 0, "note": "还没有已实现的前向预测。先做综合预测，等目标周期结束后再评估。"}
    # 只对非零预测计命中率分母，避免零值偏倚
    c_rows = [r for r in rows if _hit_valid(r.get("combined_logret"), r.get("actual_logret"))]
    p_rows = [r for r in rows if _hit_valid(r.get("price_logret"), r.get("actual_logret"))]
    n_rows = [r for r in rows if _hit_valid(r.get("news_score"), r.get("actual_logret"))]
    hit_c = sum(_hit(r["combined_logret"], r["actual_logret"]) for r in c_rows) / len(c_rows) if c_rows else 0.0
    hit_p = sum(_hit(r["price_logret"], r["actual_logret"]) for r in p_rows) / len(p_rows) if p_rows else 0.0
    hit_n = sum(_hit(r["news_score"], r["actual_logret"]) for r in n_rows) / len(n_rows) if n_rows else 0.0
    mae_c = sum(abs(r["combined_logret"] - r["actual_logret"]) for r in rows) / len(rows)
    mae_p = sum(abs(r["price_logret"] - r["actual_logret"]) for r in rows) / len(rows)
    brier_n = sum(((r["news_score"] + 1) / 2 - (1 if r["actual_logret"] > 0 else 0)) ** 2 for r in rows) / len(rows)
    by_region: dict[str, dict] = {}
    for r in rows:
        reg = r.get("region") or "GLOBAL"
        b = by_region.setdefault(reg, {"n": 0, "hit_combined": 0, "hit_price": 0, "hit_news": 0, "n_c": 0, "n_p": 0, "n_n": 0})
        b["n"] += 1
        if _hit_valid(r.get("combined_logret"), r.get("actual_logret")):
            b["n_c"] += 1
            b["hit_combined"] += int(_hit(r["combined_logret"], r["actual_logret"]))
        if _hit_valid(r.get("price_logret"), r.get("actual_logret")):
            b["n_p"] += 1
            b["hit_price"] += int(_hit(r["price_logret"], r["actual_logret"]))
        if _hit_valid(r.get("news_score"), r.get("actual_logret")):
            b["n_n"] += 1
            b["hit_news"] += int(_hit(r["news_score"], r["actual_logret"]))
    for b in by_region.values():
        b["hit_combined"] = round(b["hit_combined"] / b["n_c"], 4) if b["n_c"] else 0.0
        b["hit_price"] = round(b["hit_price"] / b["n_p"], 4) if b["n_p"] else 0.0
        b["hit_news"] = round(b["hit_news"] / b["n_n"], 4) if b["n_n"] else 0.0
    return {
        "n": len(rows), "hit_combined": round(hit_c, 4), "hit_price": round(hit_p, 4),
        "hit_news": round(hit_n, 4), "mae_combined": round(mae_c, 5),
        "mae_price": round(mae_p, 5), "brier_news": round(brier_n, 4),
        "by_region": by_region, "last": rows[0].get("evaluated_at"),
        "recent": [{
            "id": r.get("id"), "symbol": r.get("symbol"), "region": r.get("region"),
            "horizon": r.get("horizon"), "created_at": r.get("created_at"),
            "price_logret": r.get("price_logret"), "news_score": r.get("news_score"),
            "combined_logret": r.get("combined_logret"), "actual_logret": r.get("actual_logret"),
        } for r in rows[:30]],
        "note": "前向影子测试；样本少时不要据此判断稳定性。",
    }


def _clip(v, lo: float, hi: float) -> float:
    try:
        return max(float(lo), min(float(hi), float(v)))
    except (TypeError, ValueError):
        return float(lo)


_APPLY_TS = {"last": 0.0}


def update_weights(store: NewsStore, data_store, min_samples: int = 20) -> dict:
    ev = evaluate_predictions(store, data_store)
    perf = performance(store)
    if perf.get("n", 0) < min_samples:
        return {"updated": False, "reason": f"样本不足：{perf.get('n', 0)} < {min_samples}",
                "evaluation": ev, "performance": perf}
    weights = load_weights()
    before = {"news_weight": weights.get("news_weight"), "region_learned": dict(weights.get("region_learned") or {})}
    changes = []
    overall_news = float(perf["hit_news"])
    overall_price = float(perf["hit_price"])
    delta = _clip((overall_news - overall_price) * 0.5, -0.05, 0.05)
    old_w = float(weights.get("news_weight", 0.15))
    new_w = _clip(old_w + delta, 0.05, 0.35)
    if abs(new_w - old_w) > 1e-6:
        weights["news_weight"] = round(new_w, 4)
        changes.append({"target": "news_weight", "before": round(old_w, 4), "after": round(new_w, 4),
                        "reason": f"news_hit={overall_news:.3f}, price_hit={overall_price:.3f}"})
    for region, b in (perf.get("by_region") or {}).items():
        if b["n"] < max(8, min_samples // 3):
            continue
        d = _clip((b["hit_news"] - 0.5) * 0.16, -0.08, 0.08)
        reg = dict(weights.get("region_learned") or {})
        old = float(reg.get(region, 1.0))
        new = _clip(old * (1 + d), 0.5, 1.5)
        if abs(new - old) > 1e-6:
            reg[region] = round(new, 4)
            weights["region_learned"] = reg
            changes.append({"target": f"region:{region}", "before": round(old, 4), "after": round(new, 4),
                            "reason": f"n={b['n']}, news_hit={b['hit_news']:.3f}"})

    # 领域/事件类型权重：只统计预测时引用过的事件类别，样本 >=8 才更新。
    cat_stats: dict[str, dict] = {}
    for r in store.evaluated_predictions(limit=1000):
        cats = set()
        for nid in r.get("news_ids") or []:
            item = store.get(nid)
            a = (item or {}).get("analysis") or {}
            if a.get("event_type"):
                cats.add(a["event_type"])
        for cat in cats:
            b = cat_stats.setdefault(cat, {"n": 0, "hit": 0})
            b["n"] += 1
            b["hit"] += int((r.get("news_score", 0) > 0) == (r.get("actual_logret", 0) > 0))
    for cat, b in cat_stats.items():
        if b["n"] < 8:
            continue
        hit = b["hit"] / b["n"]
        d = _clip((hit - 0.5) * 0.12, -0.05, 0.05)
        learned = dict(weights.get("category_learned") or {})
        old = float(learned.get(cat, 1.0))
        new = _clip(old * (1 + d), 0.6, 1.4)
        if abs(new - old) > 1e-6:
            learned[cat] = round(new, 4)
            weights["category_learned"] = learned
            changes.append({"target": f"category:{cat}", "before": round(old, 4), "after": round(new, 4),
                            "reason": f"n={b['n']}, news_hit={hit:.3f}"})
    if changes:
        weights.setdefault("history", []).append({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "type": "online_update", "n": perf["n"],
            "hit_news": overall_news, "hit_price": overall_price,
            "changes": changes,
        })
        save_weights(weights)
    return {"updated": bool(changes), "reason": "已更新" if changes else "无有效变更",
            "evaluation": ev, "performance": perf, "before": before,
            "after": {"news_weight": weights.get("news_weight"),
                      "region_learned": weights.get("region_learned")}, "changes": changes}


def apply_proposal(store: NewsStore, proposal: dict) -> dict:
    import time
    now = time.time()
    # 频控：10 分钟内只能应用一次 LLM 提议，避免反复点击把权重逐步推到硬边界
    if now - _APPLY_TS["last"] < 600:
        return {"applied": False, "reason": "提议应用过于频繁，请等待 10 分钟后再试",
                "retry_after_seconds": int(600 - (now - _APPLY_TS["last"]))}
    _APPLY_TS["last"] = now
    weights = load_weights()
    before = {"news_weight": weights.get("news_weight"),
              "region_learned": dict(weights.get("region_learned") or {})}
    old_w = float(weights.get("news_weight", 0.15))
    new_w = _clip(proposal.get("news_weight", old_w), max(0.05, old_w - 0.05), min(0.35, old_w + 0.05))
    weights["news_weight"] = round(new_w, 4)
    reg = dict(weights.get("region_learned") or {})
    for r, v in (proposal.get("region_learned") or {}).items():
        old = float(reg.get(r, 1.0))
        reg[r] = round(_clip(v, max(0.5, old * 0.92), min(1.5, old * 1.08)), 4)
    weights["region_learned"] = reg
    cat = dict(weights.get("category_learned") or {})
    for c, v in (proposal.get("category_learned") or {}).items():
        old = float(cat.get(c, 1.0))
        cat[c] = round(_clip(v, max(0.6, old * 0.92), min(1.4, old * 1.08)), 4)
    weights["category_learned"] = cat
    weights.setdefault("history", []).append({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": "llm_proposal_applied", "proposal": proposal,
        "before": before, "after": {"news_weight": weights["news_weight"], "region_learned": reg,
                                     "category_learned": cat},
    })
    save_weights(weights)
    return {"applied": True, "before": before,
            "after": {"news_weight": weights["news_weight"], "region_learned": reg,
                      "category_learned": cat}}


def llm_proposal(client: LLMClient, store: NewsStore) -> dict:
    perf = performance(store)
    weights = load_weights()
    prompt = (
        "You are optimizing a *bounded* news-weight overlay for a research terminal. "
        "You may only propose small changes; the code will clamp them. "
        "Return JSON: {\"news_weight\": 0.05..0.35, \"region_learned\": {\"US\":0.5..1.5,...}, "
        "\"category_learned\": {\"tech\":0.6..1.4,...}, \"rationale\": \"<=300 chars\"}. "
        "Do not propose code changes or trading actions.\n\n"
        f"Current news_weight={weights.get('news_weight')} region_learned={weights.get('region_learned')} "
        f"category_learned={weights.get('category_learned')}\n"
        f"Forward performance={perf}\n"
    )
    raw = client.chat_json("Return only a bounded JSON proposal.", prompt)
    proposal = {"news_weight": _clip(raw.get("news_weight", weights.get("news_weight", 0.15)), 0.05, 0.35),
                "region_learned": {}, "category_learned": {}, "rationale": str(raw.get("rationale") or "")[:300]}
    for r, v in (raw.get("region_learned") or {}).items():
        if r in ("US", "HK", "CN", "EU", "UK", "JP", "GLOBAL"):
            proposal["region_learned"][r] = _clip(v, 0.5, 1.5)
    for c, v in (raw.get("category_learned") or {}).items():
        if c in ("monetary_policy", "fiscal_policy", "regulation", "geopolitics", "trade", "tech",
                 "energy", "real_estate", "labor", "earnings", "other"):
            proposal["category_learned"][c] = _clip(v, 0.6, 1.4)
    return proposal


def apply_proposal(store: NewsStore, proposal: dict) -> dict:
    weights = load_weights()
    before = {"news_weight": weights.get("news_weight"),
              "region_learned": dict(weights.get("region_learned") or {})}
    old_w = float(weights.get("news_weight", 0.15))
    new_w = _clip(proposal.get("news_weight", old_w), max(0.05, old_w - 0.05), min(0.35, old_w + 0.05))
    weights["news_weight"] = round(new_w, 4)
    reg = dict(weights.get("region_learned") or {})
    for r, v in (proposal.get("region_learned") or {}).items():
        old = float(reg.get(r, 1.0))
        reg[r] = round(_clip(v, max(0.5, old * 0.92), min(1.5, old * 1.08)), 4)
    weights["region_learned"] = reg
    cat = dict(weights.get("category_learned") or {})
    for c, v in (proposal.get("category_learned") or {}).items():
        old = float(cat.get(c, 1.0))
        cat[c] = round(_clip(v, max(0.6, old * 0.92), min(1.4, old * 1.08)), 4)
    weights["category_learned"] = cat
    weights.setdefault("history", []).append({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": "llm_proposal_applied", "proposal": proposal,
        "before": before, "after": {"news_weight": weights["news_weight"], "region_learned": reg,
                                     "category_learned": cat},
    })
    save_weights(weights)
    return {"applied": True, "before": before,
            "after": {"news_weight": weights["news_weight"], "region_learned": reg,
                      "category_learned": cat}}
