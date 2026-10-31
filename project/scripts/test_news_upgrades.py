# -*- coding: utf-8 -*-
"""新闻层 v0.5 算法升级回归测试（无网络、无真实数据依赖）。

覆盖：同簇事件收益递减、LLM confidence 在线校准、已实现波动率尺度、
波动率 regime 乘子、逆 MSE 权重更新、增量技能配对 CI、共形区间、
apply_proposal 频控、旧版权重文件兼容、score_news 端到端（去重+衰减+过滤）。

用法：py scripts/test_news_upgrades.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
_TMP = tempfile.mkdtemp(prefix="fin_news_upgrades_")
os.environ["FIN_NEWS_WEIGHTS_PATH"] = str(Path(_TMP) / "weights.json")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from finance_app.news import impact, optimizer

fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not cond:
        fails.append(name)


class FakeStore:
    def __init__(self, rows=None, list_items=None, items=None):
        self._rows = rows or []
        self._list_items = list_items or []
        self._items = items or {}
    def list(self, **kw):
        return self._list_items
    def get(self, nid):
        return self._items.get(nid)
    def pending_predictions(self, limit=200):
        return []
    def evaluated_predictions(self, limit=500):
        return self._rows
    def set_actual(self, pid, actual):
        pass
    def save_prediction(self, row):
        return 1


class FakeDS:
    def __init__(self, df):
        self.df = df
    def get(self, symbol):
        return self.df


rng = np.random.default_rng(7)
px = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, 400)))
df = pd.DataFrame({"close": px}, index=pd.bdate_range("2024-01-01", periods=400))

# ---------- 1. confidence 校准 ----------
w = {"confidence_calibration": {"mult": {"lo": 0.5, "mid": 1.0, "hi": 1.2}}}
check("conf 校准 lo 打折 / hi 放大 / 无表恒等",
      abs(impact.calibrated_confidence(0.2, w) - 0.10) < 1e-9
      and abs(impact.calibrated_confidence(0.8, w) - 0.96) < 1e-9
      and impact.calibrated_confidence(0.5, {}) == 0.5)
check("conf 非法输入回退 0", impact.calibrated_confidence(None, w) == 0.0)

# ---------- 2. 簇收益递减 ----------
items = [
    {"weight": 1.0, "signed": 0.5, "region": "US", "analysis": {"event_type": "monetary_policy"}},
    {"weight": 0.8, "signed": 0.4, "region": "US", "analysis": {"event_type": "monetary_policy"}},
    {"weight": 0.6, "signed": 0.3, "region": "US", "analysis": {"event_type": "monetary_policy"}},
    {"weight": 0.9, "signed": -0.3, "region": "CN", "analysis": {"event_type": "monetary_policy"}},
]
impact._cluster_decay(items, 0.5)
check("簇内 1/0.5/0.25 递减，跨簇不衰减",
      [i["weight"] for i in items] == [1.0, 0.4, 0.15, 0.9])
impact._cluster_decay(items, 0.0)
check("decay=0 / 非法值关闭衰减", items[1]["weight"] == 0.4)
impact._cluster_decay(items, 1.0)
check("decay=1（非法区间）关闭衰减", items[1]["weight"] == 0.4)

# ---------- 3. combine：波动率尺度 + regime ----------
imp_full = {"global": {"weight": 3.0, "n": 5}, "n": 5}
imp_half = {"global": {"weight": 1.5, "n": 5}, "n": 5}
c = impact.combine(0.01, 5, 0.5, imp_full, None, vol_scale=0.02, regime="low")
check("scale 用已实现波动率 + regime 乘子",
      c["scale_source"] == "realized_vol" and abs(c["horizon_scale"] - 0.02) < 1e-6 and c["regime_mult"] == 1.15)
c2 = impact.combine(0.01, 5, 0.5, imp_full, None)
check("无数据回退常数表 + mid", c2["scale_source"] == "table" and c2["horizon_scale"] == 0.025)
check("极端 σ 被钳到 0.08", impact.combine(0.01, 5, 0.5, imp_full, None, vol_scale=0.5)["horizon_scale"] == 0.08)
check("w 仍受 [0.05, 0.35] 硬边界", impact.combine(0.0, 5, 1.0, imp_full, None)["news_weight"] <= 0.35)
check("coverage=0.5 → w=base（原行为）", impact.combine(0.01, 5, 0.5, imp_half, {"news_weight": 0.25})["news_weight"] == 0.25)

# ---------- 4. 已实现波动率 / regime 判定 ----------
vs = impact._horizon_vol_scale(FakeDS(df), "AAPL", 5)
check("σ_h ≈ σ_1d×√5", vs is not None and 0.01 < vs < 0.10)
check("regime 判定合法 + 数据不足回退 mid",
      impact._vol_regime(FakeDS(df), "AAPL") in ("low", "mid", "high")
      and impact._vol_regime(FakeDS(df.iloc[:50]), "AAPL") == "mid")
check("空数据 σ 回退 None", impact._horizon_vol_scale(FakeDS(None), "AAPL", 5) is None)

# ---------- 5. performance：增量技能 + 共形区间 ----------
rows = []
for i in range(40):
    actual = 0.01 if i % 2 else -0.01
    news = 0.5 if i % 2 else -0.5
    price = 0.01
    rows.append({"id": i, "symbol": "X", "region": "US", "horizon": 5,
                 "price_logret": price, "news_score": news,
                 "combined_logret": 0.85 * price + 0.15 * (news * 0.025), "actual_logret": actual})
perf = optimizer.performance(FakeStore(rows))
check("增量技能：news 全对 vs price 半对 → 显著为正",
      perf["incremental_skill"]["n"] == 40 and perf["incremental_skill"]["mean_diff"] == 0.5
      and perf["incremental_skill"]["significant"] is True)
check("共形区间存在；样本<20 输出 None",
      bool(perf["residual_interval"]) and "q05" in perf["residual_interval"]
      and optimizer.performance(FakeStore(rows[:10]))["residual_interval"] is None)

# ---------- 6. update_weights 全流程 ----------
items6 = {}
for i, r in enumerate(rows):
    nid = f"n{i}"
    r["news_ids"] = [nid]
    items6[nid] = {"id": nid, "analysis": {"event_type": "tech", "confidence": 0.8}}
res = optimizer.update_weights(FakeStore(rows, items=items6), FakeDS(df), min_samples=20)
check("news 更新走逆 MSE 规则",
      any("inverse_mse" in str(c.get("reason")) for c in res["changes"]))
check("news 更准 → w 0.15→0.20",
      any(c["target"] == "news_weight" and c["after"] == 0.2 for c in res["changes"]))
saved = impact.load_weights()
check("confidence 校准表持久化 + category/region 上调",
      "hi" in (saved.get("confidence_calibration") or {}).get("mult", {})
      and saved.get("category_learned", {}).get("tech", 1.0) > 1.0
      and saved.get("region_learned", {}).get("US", 1.0) > 1.0)

# ---------- 7. price 完美（mae_price=0）→ w 向 0.05 下限步进 ----------
# （换全新权重文件隔离：第 6 步已把 news_weight 持久化为 0.20）
impact.WEIGHTS_PATH = Path(_TMP) / "fresh7.json"
perfect = [{"id": 100 + i, "symbol": "X", "region": "US", "horizon": 5,
            "price_logret": (a := (0.01 if i % 2 else -0.01)), "news_score": 0.5 if i % 3 else -0.5,
            "combined_logret": a, "actual_logret": a} for i in range(30)]
res_p = optimizer.update_weights(FakeStore(perfect), FakeDS(df), min_samples=20)
check("mae_price=0 仍走逆 MSE，w 0.15→0.10",
      any("inverse_mse" in str(c.get("reason")) and c["target"] == "news_weight" and c["after"] == 0.10
          for c in res_p["changes"]))

# ---------- 8. 频控（重复定义 bug 回归） ----------
r1 = optimizer.apply_proposal(None, {"news_weight": 0.2})
r2 = optimizer.apply_proposal(None, {"news_weight": 0.2})
check("apply_proposal 10 分钟频控生效",
      r1.get("applied") is True and r2.get("applied") is False and "retry_after_seconds" in r2)

# ---------- 9. score_news 端到端：过滤 + 去重 + 簇衰减 ----------
now_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")


def ev(i, title, conf=0.9, etype="monetary_policy", rel=0.9):
    return {"id": i, "title": title, "url": "u", "source_name": "Fed", "source_tier": "official",
            "published_at": now_iso, "region": "US",
            "analysis": {"event_type": etype, "direction": 1, "magnitude": 0.8, "confidence": conf,
                         "novelty": 0.9, "relevance": rel, "regions": ["US"], "sectors": ["broad"]}}

out = impact.score_news(FakeStore(list_items=[
    ev("a", "Fed raises rates by fifty basis points"),
    ev("b", "Fed raises rates by fifty basis points"),
    ev("c", "Fed signals further policy tightening ahead"),
    ev("d", "Agency opens temporary heat shelters", rel=0.2),
]), hours=48)
w_a, w_c = out["top_events"][0]["weight"], out["top_events"][1]["weight"]
# 权重保留 5 位小数，w_c = w_a×0.5 的绝对舍入误差上限 5e-6，容差取 1e-5
check("端到端：去重+过滤后 n=2，同簇第二条权重减半，全局分值为正",
      out["n"] == 2 and out["regions"]["US"]["n"] == 2 and abs(w_c - w_a * 0.5) < 1e-5
      and out["global"]["score"] > 0)

# ---------- 10. 旧版权重文件兼容 ----------
_old_wp = impact.WEIGHTS_PATH
old_path = Path(_TMP) / "old_weights.json"
old_path.write_text('{"news_weight": 0.25, "history": []}', encoding="utf-8")
impact.WEIGHTS_PATH = old_path
w_old = impact.load_weights()
check("旧权重文件合并出新键默认值",
      w_old.get("cluster_decay") == 0.5 and w_old.get("news_weight") == 0.25
      and w_old.get("confidence_calibration") == {}
      and impact.calibrated_confidence(0.8, w_old) == 0.8)
impact.WEIGHTS_PATH = _old_wp

print()
if fails:
    print(f"FAILED: {len(fails)} -> {fails}")
    sys.exit(1)
print("UPGRADE TESTS ALL PASSED")
