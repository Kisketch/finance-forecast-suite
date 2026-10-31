"""新闻影响系数、价格先验融合、符号级综合预测。

这是一个透明的线性叠加层：
  combined_logret = (1-w) * price_logret + w * (news_score * horizon_scale)
w 默认 0.15，随官方证据强度在 0.05–0.35 间调整；新闻层没有历史新闻库，
因此只做“前向影子测试”，不宣称历史 alpha。
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .store import NewsStore

from .._paths import ROOT

WEIGHTS_PATH = Path(os.environ.get("FIN_NEWS_WEIGHTS_PATH") or (ROOT / "data" / "models" / "news_weights.json"))

DEFAULT_WEIGHTS = {
    "version": 1,
    "news_weight": 0.15,
    "half_life_hours": 18.0,
    "min_relevance": 0.45,
    "source_tier": {"official": 1.0, "multilateral": 0.9, "exchange": 1.0, "company": 0.8, "wire": 0.4},
    "category": {
        "monetary_policy": 1.1, "fiscal_policy": 1.0, "regulation": 0.9, "geopolitics": 1.1,
        "trade": 1.0, "tech": 1.0, "energy": 1.0, "real_estate": 0.9, "labor": 0.9,
        "earnings": 1.0, "other": 0.5,
    },
    "region": {"US": 1.0, "HK": 1.0, "CN": 1.0, "EU": 0.9, "UK": 0.9, "JP": 0.9, "GLOBAL": 0.8},
    "category_learned": {},
    "region_learned": {},
    # 同簇事件收益递减系数：(event_type, region) 相同的第 n 条证据权重 ×decay^(n-1)，
    # 抑制"同一事实多源报道"造成的证据总量虚增（相关性感知的证据记账）。
    "cluster_decay": 0.5,
    # 融合尺度乘子：scale = clip(σ_horizon × scale_vol_mult, 0.006, 0.08)。
    # σ_horizon 为 horizon 期已实现波动率，替代手拍常数（数据驱动的 link function）。
    "scale_vol_mult": 1.0,
    # 波动率 regime 乘子：低波动期价格信号弱、新闻相对信息价值高（>1）；
    # 高波动期新闻隐含幅度噪音大（<1）。可配置先验，不宣称最优。
    "regime_mult": {"low": 1.15, "mid": 1.0, "high": 0.85},
    # LLM confidence 在线校准表：{"mult": {桶: 乘子}, "n": {桶: 样本数}}，
    # 由 optimizer.update_weights 用前向影子命中率估计（Beta 平滑）。
    "confidence_calibration": {},
    "history": [],
    "updated_at": None,
}

REGION_BY_SYMBOL = {
    "^GSPC": "US", "^IXIC": "US", "^DJI": "US", "^RUT": "US", "^VIX": "US", "^TNX": "US",
    "^HSI": "HK", "^HSCE": "HK", "^HSTECH": "HK",
    "000001.SS": "CN", "000300.SS": "CN", "399006.SZ": "CN", "000688.SS": "CN",
    "DX-Y.NYB": "US",
}
SECTOR_BY_SYMBOL = {}
for _s in ["XLRE", "VNQ", "PLD", "SPG", "O", "DLR", "PSA", "EQIX", "AVB", "EQR",
           "0016.HK", "0823.HK", "0688.HK", "1109.HK", "000002.SZ", "600048.SS", "001979.SZ"]:
    SECTOR_BY_SYMBOL[_s] = "real_estate"
for _s in ["XLE", "XOP", "XOM", "CVX", "COP", "EOG", "SLB", "OXY", "MPC", "VLO", "KMI", "LNG",
           "0883.HK", "0386.HK", "0857.HK", "1088.HK", "1898.HK", "601857.SS", "600028.SS", "601088.SS",
           "CL=F", "BZ=F", "NG=F"]:
    SECTOR_BY_SYMBOL[_s] = "energy"
for _s in ["GC=F", "SI=F", "HG=F"]:
    SECTOR_BY_SYMBOL[_s] = "materials"
for _s in ["XLK", "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "0700.HK", "9988.HK", "3690.HK",
           "300750.SZ", "002594.SZ", "601012.SS"]:
    SECTOR_BY_SYMBOL[_s] = "tech"
for _s in ["XLF", "JPM", "GS", "MS", "BRK-B", "0388.HK", "0005.HK", "1299.HK", "2318.HK",
           "601318.SS", "600036.SS", "601398.SS", "600030.SS"]:
    SECTOR_BY_SYMBOL[_s] = "finance"
for _s in ["XLU", "600900.SS"]:
    SECTOR_BY_SYMBOL[_s] = "utilities"

HORIZON_SCALE = {1: 0.012, 5: 0.025, 20: 0.05}


def load_weights() -> dict:
    data = json.loads(json.dumps(DEFAULT_WEIGHTS))
    if WEIGHTS_PATH.exists():
        try:
            saved = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(data.get(k), dict):
                    data[k].update(v)
                else:
                    data[k] = v
        except Exception:  # noqa: BLE001
            pass
    return data


def save_weights(w: dict) -> None:
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    w["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    w["history"] = (w.get("history") or [])[-120:]
    WEIGHTS_PATH.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")


def _age_hours(published: str) -> float:
    """返回事件年龄（小时）。解析失败或明显为未来时间戳时返回 +inf，
    使时效权重趋近 0，而不是错误地获得最大时效权重。"""
    try:
        dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        if age < -24.0:  # 未来超过 1 天：源数据错误
            return float("inf")
        return max(0.0, age)
    except Exception:  # noqa: BLE001
        return float("inf")


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z\u4e00-\u9fff]{3,}", title.lower())
            if w not in {"the", "and", "for", "with", "from", "that", "this", "will", "has", "have"}}


def _dedupe_events(items: list[dict]) -> list[dict]:
    """同一事件可能被多家官方源报道；按标题相似度去重。

    先按证据权重降序排序，再顺序扫描去重——确保保留的是权重最高的一条
    （此前先去重后排序，实际保留的是列表顺序中最早出现的一条，与注释语义不符）。
    """
    ordered = sorted(items, key=lambda x: x.get("weight", 0), reverse=True)
    kept: list[dict] = []
    for item in ordered:
        ta = _tokens(item.get("title") or "")
        dup = False
        for k in kept:
            tb = _tokens(k.get("title") or "")
            if ta and tb and len(ta & tb) / max(1, len(ta | tb)) > 0.72:
                dup = True
                break
        if not dup:
            kept.append(item)
    return kept


def conf_bucket(conf: float) -> str:
    """LLM confidence 的分桶：<0.4 / <0.7 / >=0.7。"""
    if conf < 0.4:
        return "lo"
    if conf < 0.7:
        return "mid"
    return "hi"


def calibrated_confidence(raw_conf: float, weights: dict) -> float:
    """LLM confidence 的在线校准：按前向命中率对原始值打折/放大。

    校准乘子由 optimizer.update_weights 用前向影子样本估计（Beta 平滑），
    存 weights["confidence_calibration"]["mult"]；无表或对应桶缺样本时恒等返回，
    行为与未校准版本一致。乘子本身被钳制在 [0.3, 1.5]，防止校准表反向放大。"""
    try:
        conf = max(0.0, min(1.0, float(raw_conf)))
    except (TypeError, ValueError):
        return 0.0
    table = (weights.get("confidence_calibration") or {}).get("mult") or {}
    if not table:
        return conf
    try:
        mult = max(0.3, min(1.5, float(table.get(conf_bucket(conf), 1.0))))
    except (TypeError, ValueError):
        mult = 1.0
    return max(0.0, min(1.0, conf * mult))


def _cluster_decay(enriched: list[dict], decay: float) -> None:
    """同簇事件收益递减：(event_type, region) 相同的多条事件视为语义相关证据。

    文本 Jaccard 去重只消除近似重复；"同一事实被多源/多人分别报道"仍会被
    当作独立证据，虚增 Σw（coverage）→ 新闻层超配。这里把同簇第 n 条
    （按权重降序）权重乘 decay^(n-1)，等价于对相关证据做次线性累积。"""
    if not (0.0 < float(decay) < 1.0) or len(enriched) < 2:
        return
    clusters: dict[tuple[str, str], int] = {}
    for item in enriched:  # _dedupe_events 已按 weight 降序
        a = item.get("analysis") or {}
        key = (str(a.get("event_type") or "other"), str(item.get("region") or "GLOBAL"))
        n = clusters.get(key, 0) + 1
        clusters[key] = n
        if n > 1:
            f = float(decay) ** (n - 1)
            item["weight"] = round(item["weight"] * f, 5)
            item["signed"] = round(item["signed"] * f, 5)
            item["cluster_rank"] = n


def _horizon_vol_scale(data_store, symbol: str, horizon: int) -> float | None:
    """horizon 期已实现波动率：近一年日对数收益 std × √h（交易日）。

    作为融合层 link function 的数据驱动尺度——"score=1 的强新闻 ≈ 1 个
    horizon 标准差"；任何异常回退 None → 常数表（fail-open 到旧行为）。"""
    try:
        import numpy as np
        df = data_store.get(symbol)
        if df is None or len(df) < 60:
            return None
        lr = np.log(df["close"].astype(float)).diff().dropna().iloc[-250:]
        if len(lr) < 60:
            return None
        s = float(lr.std())
        if not math.isfinite(s) or s <= 0:
            return None
        return s * math.sqrt(max(1, int(horizon)))
    except Exception:  # noqa: BLE001
        return None


def _vol_regime(data_store, symbol: str) -> str:
    """当前 20 日已实现波动率在过去一年分布中的分位 → low/mid/high。

    分位 <25% 为 low（价格信号弱、新闻乘子上调）；>75% 为 high（噪音大、下调）。
    数据不足回退 "mid"，与旧版行为一致。"""
    try:
        import numpy as np
        import pandas as pd
        df = data_store.get(symbol)
        if df is None or len(df) < 120:
            return "mid"
        lr = pd.Series(np.log(df["close"].astype(float))).diff().dropna()
        v20 = lr.rolling(20).std().dropna().iloc[-250:]
        if len(v20) < 60:
            return "mid"
        q = float((v20 <= float(v20.iloc[-1])).mean())
        return "low" if q < 0.25 else ("high" if q > 0.75 else "mid")
    except Exception:  # noqa: BLE001
        return "mid"


def score_news(store: NewsStore, hours: int = 48, limit: int = 400) -> dict:
    weights = load_weights()
    items = store.list(analyzed=True, hours=hours, limit=limit)
    enriched = []
    for item in items:
        a = item.get("analysis") or {}
        if not a:
            continue
        if float(a.get("relevance", 0.0)) < float(weights.get("min_relevance", 0.45)):
            continue
        age = _age_hours(item.get("published_at"))
        recency = math.pow(0.5, age / max(1.0, float(weights.get("half_life_hours", 18)))) \
            if math.isfinite(age) else 0.0
        tier_w = (weights.get("source_tier") or {}).get(item.get("source_tier"), 0.5)
        cat_w = (weights.get("category") or {}).get(a.get("event_type"), 0.5)
        cat_l = (weights.get("category_learned") or {}).get(a.get("event_type"), 1.0)
        reg_w = (weights.get("region") or {}).get(item.get("region"), 0.8)
        reg_l = (weights.get("region_learned") or {}).get(item.get("region"), 1.0)
        w = tier_w * cat_w * cat_l * reg_w * reg_l * recency \
            * calibrated_confidence(a.get("confidence", 0), weights) \
            * float(a.get("novelty", 0.7)) * max(0.05, float(a.get("magnitude", 0))) \
            * (0.3 + 0.7 * float(a.get("relevance", 0.5)))
        if w <= 0:
            continue
        enriched.append({**item, "weight": round(w, 5),
                         "signed": round(w * float(a.get("direction", 0)), 5)})
    enriched = _dedupe_events(enriched)
    _cluster_decay(enriched, float(weights.get("cluster_decay", 0.5)))

    def bucket() -> dict:
        return {"score": 0.0, "weight": 0.0, "n": 0}

    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "lookback_hours": hours, "n": len(enriched),
           "global": bucket(), "regions": {}, "sectors": {},
           "top_events": []}
    for item in enriched:
        a = item.get("analysis") or {}
        w = item["weight"]
        signed = item["signed"]
        for r in (a.get("regions") or [item.get("region") or "GLOBAL"]):
            b = out["regions"].setdefault(str(r), bucket())
            b["score"] += signed; b["weight"] += w; b["n"] += 1
        for s in (a.get("sectors") or ["broad"]):
            b = out["sectors"].setdefault(str(s), bucket())
            b["score"] += signed; b["weight"] += w; b["n"] += 1
        g = out["global"]
        g["score"] += signed; g["weight"] += w; g["n"] += 1
    for key in ("global",):
        b = out[key]
        b["score"] = round(b["score"] / b["weight"], 4) if b["weight"] else 0.0
        b["weight"] = round(b["weight"], 4)
    for group in ("regions", "sectors"):
        for k, b in out[group].items():
            b["score"] = round(b["score"] / b["weight"], 4) if b["weight"] else 0.0
            b["weight"] = round(b["weight"], 4)
    enriched.sort(key=lambda x: x["weight"], reverse=True)
    directional = [x for x in enriched if abs(float((x.get("analysis") or {}).get("direction", 0))) >= 0.05]
    out["top_events"] = [{
        "id": x["id"], "title": x["title"], "url": x["url"], "source_name": x["source_name"],
        "source_tier": x["source_tier"], "published_at": x["published_at"],
        "direction": (x.get("analysis") or {}).get("direction"),
        "magnitude": (x.get("analysis") or {}).get("magnitude"),
        "confidence": (x.get("analysis") or {}).get("confidence"),
        "event_type": (x.get("analysis") or {}).get("event_type"),
        "sectors": (x.get("analysis") or {}).get("sectors"),
        "weight": x["weight"],
    } for x in directional[:12]]
    return out


def symbol_context(symbol: str) -> tuple[str, str | None]:
    region = REGION_BY_SYMBOL.get(symbol, "US")
    if symbol.endswith(".HK"):
        region = "HK"
    elif symbol.endswith(".SS") or symbol.endswith(".SZ"):
        region = "CN"
    elif symbol.startswith("^"):
        region = REGION_BY_SYMBOL.get(symbol, "GLOBAL")
    elif symbol in ("CL=F", "BZ=F", "NG=F", "GC=F", "SI=F", "HG=F"):
        region = "GLOBAL"
    return region, SECTOR_BY_SYMBOL.get(symbol)


def symbol_news_score(impact: dict, symbol: str) -> dict:
    region, sector = symbol_context(symbol)
    rb = (impact.get("regions") or {}).get(region) or impact.get("global") or {}
    sb = (impact.get("sectors") or {}).get(sector) if sector else None
    rscore = float(rb.get("score", 0) or 0)
    if sb and sb.get("n"):
        score = 0.55 * rscore + 0.45 * float(sb.get("score", 0) or 0)
        n = int(rb.get("n", 0)) + int(sb.get("n", 0))
        weight = float(rb.get("weight", 0)) + float(sb.get("weight", 0))
    else:
        score = rscore
        n = int(rb.get("n", 0))
        weight = float(rb.get("weight", 0))
    return {"score": round(max(-1.0, min(1.0, score)), 4), "region": region,
            "sector": sector, "n": n, "weight": round(weight, 3)}


def combine(price_logret: float, horizon: int, news_score: float, impact: dict,
            weights: dict | None = None, vol_scale: float | None = None,
            regime: str | None = None) -> dict:
    """价格先验 × 新闻分融合（线性意见池）。

    尺度（link function）优先用 horizon 期已实现波动率 σ_h（由 predict_combined
    传入），等价于"score=1 的强新闻 ≈ 1 个 horizon 标准差"；缺失时回退常数表
    HORIZON_SCALE（本身近似 1.2%×√T 的粗版）。regime 乘子作用于新闻幅度：
    低波动期价格信号弱、新闻相对信息价值高（>1）；高波动期新闻隐含幅度噪音
    大（<1）。两个先验均可经 weights 覆盖（scale_vol_mult / regime_mult）。"""
    weights = weights or load_weights()
    coverage = min(1.0, float((impact.get("global") or {}).get("weight", 0)) / 3.0)
    base = float(weights.get("news_weight", 0.15))
    w = 0.0 if not impact.get("n") else max(0.05, min(0.35, base * (0.6 + 0.8 * coverage)))
    try:
        vs = float(vol_scale) if vol_scale else None
    except (TypeError, ValueError):
        vs = None
    try:
        k_mult = max(0.5, min(1.5, float(weights.get("scale_vol_mult", 1.0) or 1.0)))
    except (TypeError, ValueError):
        k_mult = 1.0
    if vs and vs > 0 and math.isfinite(vs):
        scale = max(0.006, min(0.08, vs * k_mult))
        scale_source = "realized_vol"
    else:
        scale = HORIZON_SCALE.get(int(horizon), 0.025)
        scale_source = "table"
    reg_mult = 1.0
    if regime:
        try:
            reg_mult = max(0.5, min(1.5, float((weights.get("regime_mult") or {}).get(str(regime), 1.0))))
        except (TypeError, ValueError):
            reg_mult = 1.0
    news_logret = float(news_score) * scale * (0.6 + 0.4 * coverage) * reg_mult
    combined = (1.0 - w) * float(price_logret) + w * news_logret
    agreement = 0
    if abs(price_logret) > 1e-9 and abs(news_score) > 1e-9:
        agreement = 1 if (price_logret > 0) == (news_score > 0) else -1
    confidence = min(0.9, 0.30 + 0.30 * coverage + 0.15 * max(0, agreement) + 0.10 * min(1.0, impact.get("n", 0) / 10))
    return {
        "combined_logret": round(combined, 6),
        "price_contribution": round((1.0 - w) * float(price_logret), 6),
        "news_contribution": round(w * news_logret, 6),
        "news_weight": round(w, 4),
        "price_weight": round(1.0 - w, 4),
        "news_logret": round(news_logret, 6),
        "agreement": agreement,
        "confidence": round(confidence, 3),
        "horizon_scale": round(scale, 6),
        "scale_source": scale_source,
        "regime": str(regime or "mid"),
        "regime_mult": round(reg_mult, 3),
        "coverage": round(coverage, 3),
    }


def predict_combined(store: NewsStore, data_store, symbol: str, horizon: int = 5,
                     model: str = "ensemble", log: bool = True) -> dict:
    price = data_store.forecast(symbol, horizon, model)
    if not price or price.get("error"):
        return {"error": (price or {}).get("error", "price forecast failed")}
    impact = score_news(store, hours=48)
    ns = symbol_news_score(impact, symbol)
    weights = load_weights()
    vol_scale = _horizon_vol_scale(data_store, symbol, horizon)
    regime = _vol_regime(data_store, symbol)
    comb = combine(float(price.get("point_logret", 0)), horizon, ns["score"], impact, weights,
                   vol_scale=vol_scale, regime=regime)
    notes = [
        "价格先验来自价量滚动回测；新闻层只使用官方一级源，权重被限制在 5%–35%。",
        "新闻层没有历史新闻库，无法做真正的历史回测；这里只做前向影子测试。",
        "融合尺度优先用已实现波动率 σ_h 校准（强新闻≈1 个 horizon 标准差），常数表仅兜底。",
        "波动率 regime 乘子：低波动期新闻乘子上调、高波动期下调——可配置先验，非最优估计。",
        "方向准确率 98.7% 在价量+新闻的样本外不可承诺；请把结果当情景，不是买卖信号。",
        "LLM 分析可能出错；所有事件卡都保留原文链接与来源层级，需人工复核。",
    ]
    row = {
        "symbol": symbol, "region": ns["region"], "horizon": horizon, "model": model,
        "last_date": price.get("last_date"), "last_close": price.get("last_close"),
        "price_logret": price.get("point_logret"), "news_score": ns["score"],
        "combined_logret": comb["combined_logret"],
        "weights": {"news_weight": comb["news_weight"], "source_tier": weights.get("source_tier"),
                    "category_learned": weights.get("category_learned"),
                    "region_learned": weights.get("region_learned")},
        "news_ids": [e["id"] for e in impact.get("top_events", [])[:10]],
    }
    pred_id = store.save_prediction(row) if log else None
    return {
        "symbol": symbol, "horizon": horizon, "model": model,
        "price": {"last_date": price.get("last_date"), "last_close": price.get("last_close"),
                  "point_price": price.get("point_price"), "point_logret": price.get("point_logret"),
                  "q05": price.get("q05_price"), "q50": price.get("q50_price"), "q95": price.get("q95_price"),
                  "skill": price.get("skill_score"), "dir_acc": price.get("dir_acc"),
                  "baseline_dir": price.get("baseline_dir_acc"), "folds": price.get("n_folds")},
        "news": {"score": ns["score"], "region": ns["region"], "sector": ns["sector"],
                 "n": ns["n"], "weight": ns["weight"], "impact": impact},
        "combined": comb, "prediction_id": pred_id, "notes": notes,
    }
