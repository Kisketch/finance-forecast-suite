"""内置 AI 接入：OpenAI 兼容客户端 + 提示词模板库（用户无需手写提示词）。

支持任意 OpenAI 兼容端点（Ollama / LM Studio / vLLM / DeepSeek / OpenAI / 通义千问等）。
密钥只存本地 config；提示词模板覆盖趋势分析/异常解读/因子归因/操作建议/回测解读。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# frozen 模式：配置写到 exe 同目录（用户可写持久化）；开发模式：项目根
if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).resolve().parent
else:
    _BASE = Path(__file__).resolve().parents[2]
ROOT = _BASE
CONFIG_PATH = Path(os.environ.get("FINPREDICT_CONFIG") or (ROOT / "config" / "ai.json"))
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class AIConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 60
    temperature: float = 0.3
    max_tokens: int = 1200

    @property
    def configured(self) -> bool:
        return bool(self.base_url.strip() and self.model.strip())


def load_config() -> AIConfig:
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            raw = {}
    else:
        raw = {}
    cfg = AIConfig(
        base_url=str(raw.get("base_url") or "").strip().rstrip("/"),
        api_key=str(raw.get("api_key") or "").strip(),
        model=str(raw.get("model") or "").strip(),
        timeout_seconds=int(raw.get("timeout_seconds") or 60),
        temperature=float(raw.get("temperature") if raw.get("temperature") is not None else 0.3),
        max_tokens=int(raw.get("max_tokens") or 1200),
    )
    env = {"base_url": os.environ.get("FINPREDICT_BASE_URL"),
           "api_key": os.environ.get("FINPREDICT_API_KEY"),
           "model": os.environ.get("FINPREDICT_MODEL")}
    for k, v in env.items():
        if v:
            setattr(cfg, k, v.strip() if k != "base_url" else v.strip().rstrip("/"))
    return cfg


def save_config(cfg: AIConfig) -> None:
    CONFIG_PATH.write_text(json.dumps({
        "base_url": cfg.base_url, "api_key": cfg.api_key, "model": cfg.model,
        "timeout_seconds": cfg.timeout_seconds, "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        CONFIG_PATH.chmod(0o600)
    except Exception:  # noqa: BLE001
        pass


def public_status(cfg: AIConfig | None = None) -> dict:
    cfg = cfg or load_config()
    host = ""
    try:
        host = urlparse(cfg.base_url).netloc if cfg.base_url else ""
    except Exception:  # noqa: BLE001
        pass
    return {"configured": cfg.configured, "base_url": cfg.base_url, "host": host,
            "model": cfg.model, "has_key": bool(cfg.api_key), "config_path": str(CONFIG_PATH)}


# ---------- 提示词模板库 ----------
SYSTEM_BASE = ("你是一位严谨的量化金融分析师助手。基于用户提供的客观市场数据进行分析，"
               "不要编造数据；如果信息不足，明确说明。所有结论标注置信度（低/中/高）。"
               "不构成投资建议；输出用中文。")

PROMPT_TEMPLATES: dict[str, dict] = {
    "trend_analysis": {
        "name": "趋势分析",
        "desc": "解读当前价格/指标/形态，判断短期趋势方向与关键位",
        "system": SYSTEM_BASE,
        "user": """请分析 {symbol} 在 {interval} 周期下的趋势：

最新数据：
- 最新收盘：{last_close}
- MA5/MA20/MA60：{ma5} / {ma20} / {ma60}
- RSI14：{rsi14}
- MACD 柱：{macd_hist}
- 布林上下轨：{boll_up} / {boll_low}
- 近 {n} 根涨跌：{recent_pct}%

模型预判：方向={direction}，下一周期对数收益={point_logret}，95% 区间=[{q05_price}, {q95_price}]（宽度 {interval_width_pct}%）
回测：方向准确率 {dir_acc}%，MAE {mae}，Skill {skill}

请输出：1) 当前趋势判断（上涨/下跌/震荡）；2) 关键支撑/阻力位；3) 指标背离或共振信号；4) 置信度。
""",
    },
    "anomaly_explain": {
        "name": "异常解读",
        "desc": "识别近期异常波动并归因（放量/跳空/极端 RSI 等）",
        "system": SYSTEM_BASE,
        "user": """{symbol} 在 {interval} 周期下，请识别近期异常：

最近 10 根 K 线 OHLCV：
{recent_klines}

异常候选：放量(量比>2)/跳空(缺口>1%)/RSI>70 或 <30/MACD 急转/突破布林轨。

请输出：1) 列出识别到的异常；2) 每个异常的可能成因（需基于数据，不编造新闻）；3) 后续观察要点；4) 置信度。
""",
    },
    "factor_attribution": {
        "name": "因子归因",
        "desc": "把近期收益拆解到动量/波动/均值回归等因子",
        "system": SYSTEM_BASE,
        "user": """请对 {symbol} 在 {interval} 周期的近期收益做因子归因：

特征值（最近一日）：
- 5/20/60 周期均值收益：{mean_5} / {mean_20} / {mean_60}
- 5/20/60 周期波动：{vol_5} / {vol_20} / {vol_60}
- 量比 z：{vol_z}
- 回撤：{drawdown}
- ATR14：{atr14}

请输出：1) 主导因子判断（动量/均值回归/波动率扩张/量价确认）；2) 各因子方向贡献（正/负/中性）；3) 因子共振或冲突；4) 置信度。
""",
    },
    "action_advice": {
        "name": "操作建议",
        "desc": "基于预判+回测给出情景化的仓位/止损建议（非买卖指令）",
        "system": SYSTEM_BASE + " 你只给情景化建议，不给具体买卖指令，不承诺收益。",
        "user": """基于以下信息给 {symbol} 的情景化建议（{interval} 周期）：

预判：方向={direction}，置信区间宽度 {interval_width_pct}%
回测：方向准确率 {dir_acc}%，策略年化 {strategy_ann}，最大回撤 {max_dd}
基准：始终看多准确率 {baseline_dir}%

请输出：1) 情景判断（是否有信号）；2) 若有信号，建议的仓位倾向（轻/中/重/空）与逻辑；3) 止损/止盈参考位（基于区间）；4) 不建议入场的条件；5) 置信度与免责声明。
""",
    },
    "backtest_review": {
        "name": "回测解读",
        "desc": "解读回测结果，指出模型是否可靠与改进方向",
        "system": SYSTEM_BASE,
        "user": """请解读以下回测结果（{symbol}，{interval}，horizon={horizon}）：

样本数：{n_folds}
方向准确率：{dir_acc}（基准始终看多 {baseline_dir}）
MAE：{mae}（随机游走 {baseline_mae}），Skill：{skill}
RMSE：{rmse}
策略年化：{strategy_ann}（买入持有 {buy_hold_ann}），最大回撤：{max_dd}

请输出：1) 模型是否跑赢基准（方向/MAE/收益三维度）；2) 是否存在过拟合迹象；3) 该周期下模型的可靠性评级；4) 改进建议（更多数据/换模型/调参）；5) 置信度。
""",
    },
}


def render_prompt(template_id: str, context: dict) -> tuple[str, str] | None:
    """渲染提示词模板，返回 (system, user)。"""
    tpl = PROMPT_TEMPLATES.get(template_id)
    if not tpl:
        return None
    try:
        user = tpl["user"].format(**context)
    except KeyError as exc:
        return None, f"模板变量缺失: {exc}"
    return tpl["system"], user


# ---------- 多智能体委员会（借鉴 TradingAgents 多角色 + ai-hedge-fund 多风格）----------
# 不复制任何项目代码，只借鉴"多视角分工 + 综合决策"的架构思想。
COMMITTEE_ROLES = [
    {
        "id": "technical", "name": "技术分析师",
        "system": SYSTEM_BASE + " 你专注技术面：K线形态、均线、动量、超买超卖、趋势强度。",
        "user": """作为技术分析师，评估 {symbol}（{interval} 周期）：

最新数据：收盘 {last_close}，MA5/20/60={ma5}/{ma20}/{ma60}，RSI14={rsi14}，MACD柱={macd_hist}，ADX={adx14}，KDJ-J={kdj_j}
布林轨：{boll_up}/{boll_low}；ATR14={atr14}；20日波动率分位={vol_regime_q}

模型预判：方向={direction}，p_up={p_up}，95%区间宽度={interval_width_pct}%
回测：方向准确率 {dir_acc}，有信号日准确率 {signal_acc}（覆盖 {signal_cov}）

请输出：1) 趋势状态（多头/空头/震荡/转折）；2) 关键技术位（支撑/阻力）；3) 指标共振或背离；4) 技术面结论（看涨/看跌/中性，置信度）。""",
    },
    {
        "id": "fundamental", "name": "基本面分析师",
        "system": SYSTEM_BASE + " 你从基本面/动量/规模视角分析（无财报时用动量与趋势代理）。",
        "user": """作为基本面分析师，评估 {symbol}（{interval}）：

动量代理：5/10/20/60 周期均值收益={mean_5}/{mean_10}/{mean_20}/{mean_60}
规模/位置：MA5距离={px_ma5}，MA20距离={px_ma20}，EMA20距离={px_ema20}
20日新高距离={dist_high20}，新低距离={dist_low20}；回撤={drawdown}

请输出：1) 趋势持续性判断（动量是否衰减）；2) 估值代理（相对均线高估/低估）；3) 基本面结论（看涨/看跌/中性，置信度）。""",
    },
    {
        "id": "risk", "name": "风险分析师",
        "system": SYSTEM_BASE + " 你专注风险：波动率、回撤、置信区间、尾部风险。",
        "user": """作为风险分析师，评估 {symbol}（{interval}）的风险：

波动率：20日={vol_20}，60日={vol_60}，波动率分位={vol_regime_q}，EWMA波动率={ewma_vol20}
ATR14={atr14}；当前回撤={drawdown}；最大回撤（回测）={max_dd}
95%区间宽度={interval_width_pct}%；预判方向置信={p_up}

请输出：1) 当前波动率状态（高/中/低，相对历史）；2) 下行风险与尾部敞口；3) 仓位建议（轻/中/重/空）；4) 风险结论（可介入/观望/规避，置信度）。""",
    },
    {
        "id": "trader", "name": "交易员",
        "system": SYSTEM_BASE + " 你专注择时与执行：信号、入场、止损、止盈。",
        "user": """作为交易员，为 {symbol}（{interval}）设计交易计划：

预判：方向={direction}，p_up={p_up}，增强信号={enhanced_signal}（1涨/0跌/-1无信号）
中位价={q50_price}，95%区间=[{q05_price},{q95_price}]（宽度{interval_width_pct}%）
回测：方向准确率{dir_acc}，策略年化{strategy_ann}，最大回撤{max_dd}

请输出：1) 是否有清晰入场信号；2) 入场参考区间；3) 止损参考位（基于下轨）；4) 止盈参考位（基于上轨）；5) 交易员结论（执行/等待/放弃，置信度）。""",
    },
    {
        "id": "manager", "name": "投资经理",
        "system": SYSTEM_BASE + " 你是投资经理，综合团队各方观点做最终决策。不盲从任何一方，权衡分歧。",
        "user": """作为投资经理，综合团队对 {symbol}（{interval}）的分析：

技术分析师观点：{technical_view}
基本面分析师观点：{fundamental_view}
风险分析师观点：{risk_view}
交易员观点：{trader_view}

预判与回测摘要：方向={direction}，p_up={p_up}，方向准确率{dir_acc}，有信号日准确率{signal_acc}，区间宽度{interval_width_pct}%

请输出：1) 团队观点分歧与共识总结；2) 权衡后的最终结论（看涨/看跌/中性/观望）；3) 建议仓位倾向（轻/中/重/空）；4) 关键前提条件（什么情况下改变判断）；5) 免责声明。""",
    },
]


def run_committee(client: "AIClient", context: dict) -> dict:
    """运行多智能体委员会：4 角色各自分析，投资经理综合。

    串行调用（4+1 次 LLM 调用，约 30-60 秒）。任一角色失败不影响其他。
    """
    views = {}
    for role in COMMITTEE_ROLES[:-1]:  # 前 4 个独立角色
        rid = role["id"]
        try:
            r = client.chat(role["system"], role["user"].format(**context))
            views[rid] = r.get("content") or r.get("error", "(空)")
        except Exception as exc:  # noqa: BLE001
            views[rid] = f"(分析失败: {exc})"
    # 投资经理综合
    mgr = COMMITTEE_ROLES[-1]
    mgr_ctx = {**context, "technical_view": views.get("technical", "—"),
               "fundamental_view": views.get("fundamental", "—"),
               "risk_view": views.get("risk", "—"), "trader_view": views.get("trader", "—")}
    try:
        r = client.chat(mgr["system"], mgr["user"].format(**mgr_ctx))
        final = r.get("content") or r.get("error", "(空)")
    except Exception as exc:  # noqa: BLE001
        final = f"(综合失败: {exc})"
    return {
        "roles": [{"id": r["id"], "name": r["name"], "view": views.get(r["id"], "—")}
                  for r in COMMITTEE_ROLES[:-1]],
        "manager": final,
        "n_roles": len(COMMITTEE_ROLES),
    }


class AIClient:
    def __init__(self, cfg: AIConfig | None = None):
        self.cfg = cfg or load_config()

    def _endpoint(self) -> str:
        base = self.cfg.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def chat(self, system: str, user: str) -> dict:
        if not self.cfg.configured:
            return {"error": "未配置 AI：请在「AI 助手」页填写 base_url 与 model"}
        try:
            urlparse(self.cfg.base_url)
        except Exception:  # noqa: BLE001
            return {"error": "base_url 格式无效"}
        body = {
            "model": self.cfg.model,
            "messages": [{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            "temperature": self.cfg.temperature, "max_tokens": self.cfg.max_tokens,
            "stream": False,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(self._endpoint(), data=json.dumps(body).encode("utf-8"),
                                             headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds) as resp:
                    data = json.loads(resp.read(4_000_000))
                choices = data.get("choices") or []
                if not choices:
                    return {"error": f"响应缺少 choices: {str(data)[:300]}"}
                msg = choices[0].get("message") or {}
                content = msg.get("content") or ""
                if isinstance(content, list):
                    content = "".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in content)
                return {"content": content, "model": self.cfg.model,
                        "latency_ms": 0}
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:400]
                last = {"error": f"HTTP {exc.code}: {detail}"}
                if exc.code >= 500 and attempt == 0:
                    time.sleep(1.5)
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                last = {"error": f"{type(exc).__name__}: {exc}"}
                if attempt == 0:
                    time.sleep(1.5)
                    continue
                break
        return last or {"error": "调用失败"}

    def test(self) -> dict:
        started = time.time()
        if not self.cfg.configured:
            return {"ok": False, "error": "未配置 base_url/model"}
        r = self.chat("You are a health check.", 'Return {"ok":true}')
        r["latency_ms"] = int((time.time() - started) * 1000)
        r["ok"] = "error" not in r
        return r
