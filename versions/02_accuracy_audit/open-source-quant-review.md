# 开源量化项目审查：协议、维护状态与可借鉴点

- 审查日期：2026-10-21
- 方法：公开 GitHub 页面 / LICENSE 文件 / 检索快照交叉核对；未逐个 clone 复核
- 结论先行：**表中的“可靠性”是工程可靠性，不是预测准确率**；本报告纠正 3 处会影响商用的协议/仓库错误，并给出“采用 / 未采用”的明确边界。

## 1. 关键纠错

| # | 原表说法 | 核验结果 | 影响 |
|---|---|---|---|
| 1 | freqtrade：ISC | **GPL-3.0**（LICENSE 文件为 GNU GPL v3） | GPL 是 copyleft；闭源分发/衍生作品需合规评估，不能当作宽松协议 |
| 2 | backtrader：MIT | **GPL-3.0**（mementum/backtrader） | 同上；且主仓库自 2023-04 后无 release，属“停更” |
| 3 | dailystockanalysis（ZhuLinsen） | 实际仓库名为 **`ZhuLinsen/daily_stock_analysis`**；Star 快照约 3.2 万–6.7 万，表中 5.84 万无法复现 | 仓库名错误会导致找不到项目；Star 数只能作约数 |
| 4 | Kronos：23.3K Star | 2026-10 快照约 **3.6 万–4.1 万**；AAAI 2026 属实 | Star 数偏旧；商用许可需单独确认（repo 有 licensing inquiry） |
| 5 | vnpy：MIT | **MIT**，核验通过 | 可用于商业项目，但需保留声明 |
| 6 | FinBERT：最新 commit 数小时前 | **属实**（检索到 16 小时前提交；2026-10-12 有许可说明更新） | 维护活跃；但代码 Apache-2.0 与模型权重许可需分开看 |
| 7 | TradingAgents：112K Star | **约 111.8K**，核验通过 | 工程/社区活跃；预测准确率仍无保证 |
| 8 | OpenBB：AGPL-3.0 | **AGPL-3.0**，核验通过 | 闭源 SaaS 需商业授权；这是表中最需要重视的协议风险 |

> Star 数是动态快照，不同日期会差几千到几万；本报告不把 Star 当作质量或准确率证据。

## 2. 逐项审查

### 2.1 TradingAgents（TauricResearch）

- 类别：LLM 多智能体交易框架；Apache-2.0；约 11.18 万 Star；活跃。
- 机制：基本面/新闻/社媒/技术分析师 → 多空研究员辩论 → 交易员 → 风控。
- 可借鉴：**多角色、多视角、辩论后决策**的产品结构。
- 不直接采用：LLM 生成交易决策不可复现、成本高、易受幻觉影响；本项目不调用 LLM 做买卖判断。
- 我们的替代：**多模型委员会**（Ridge / HistGBM / RandomForest / 逻辑回归），用样本外指标而不是“辩论语气”决定权重。

### 2.2 OpenBB Platform

- 类别：终端级数据平台；AGPL-3.0；约 7.45 万 Star；活跃。
- 可借鉴：**“一次接入、多端复用”**的数据层设计。
- 我们的替代：`DataStore` 统一长表 + 本地 HTTP API；数据仍来自各自授权源，不复制 OpenBB 代码。
- 合规：AGPL 有网络服务传染性；本项目未使用其代码，因此不触发。

### 2.3 daily_stock_analysis（ZhuLinsen）

- 类别：A 股/港股/美股 LLM 日报；Star 约 3.2 万–6.7 万；活跃。
- 可借鉴：每日看板、买卖点、止损/目标价、GitHub Actions 定时推送。
- 不直接采用：依赖第三方 LLM 配额；自动推送与“投资建议”边界不清。
- 我们的替代：本地看板 + 规则信号；不做自动推送、不给买卖建议。

### 2.4 ai-hedge-fund（virattt）

- 类别：多智能体对冲基金 POC；MIT；约 5 万+ Star；README 明确“educational purposes only”。
- 可借鉴：多风格 Agent（巴菲特/芒格/格雷厄姆）→ 我们转化为**多区域/多周期专家模型**，不模拟名人。
- 不直接采用：不实盘、不下单；本项目同样不做交易执行。

### 2.5 Qlib（微软）

- 类别：AI 量化研究平台；MIT；约 3.7 万–4.9 万 Star；工业级。
- 可借鉴：**Alpha158 因子工程**、数据→因子→模型→回测的流水线。
- 我们的落地：把特征扩展到 33 个（动量/波动/量价/形态/回撤/跨资产），并保留严格的年度滚动验证。
- 未采用：Qlib 的数据接口与配置体系；我们不想引入 A 股数据生态的耦合。

### 2.6 vnpy / VeighNa

- 类别：国内量化交易框架；MIT；约 4.5 万+ Star；活跃。
- 可借鉴：多市场/多品种的分层、网关抽象。
- 不采用：实盘网关、CTP、下单；本项目明确不做交易执行。

### 2.7 freqtrade

- 类别：加密货币交易机器人；**GPL-3.0**；约 4.6 万+ Star；活跃。
- 可借鉴：回测 + 手续费/滑点 + 超参优化 + Dry-run。
- 我们的落地：在审计中加入**交易成本与换手**（见 `analysis/accuracy-audit.md` 的策略评估）。
- 合规：GPL-3.0；不复制其代码。

### 2.8 Kronos（shiyu-coder）

- 类别：K 线基础模型；AAAI 2026；Star 约 3.6 万–4.1 万；许可需单独确认。
- 可借鉴：K 线 tokenization、多尺度时序、在 45+ 交易所预训练。
- 不采用：4.1M–499.2M 参数权重需要 GPU/数据/许可；本项目不下载、不加载其模型。
- 诚实说明：论文 RankIC 提升不等于实盘收益；我们没有复现其论文指标。

### 2.9 backtrader

- 类别：事件驱动回测；**GPL-3.0**；约 1.6 万+ Star；**2023-04 后停更**。
- 可借鉴：事件驱动、broker/commission 抽象。
- 我们的落地：向量化回测 + 成本模型；不复制代码。
- 建议：若需事件驱动，优先考虑活跃 fork / vectorbt / NautilusTrader。

### 2.10 FinBERT（ProsusAI）

- 类别：金融情绪；代码 Apache-2.0；维护活跃（2026-10 仍有提交）。
- 可借鉴：新闻/研报情绪因子。
- 不采用：缺少授权新闻源与中文金融语料；三分类粒度粗。
- 预留：`context` 特征接口可接情绪分数，但本期不伪造数据。

### 2.11 AKShare

- 类别：国内数据源；MIT；约 2.28 万 Star；活跃。
- 可借鉴：免费接口覆盖广。
- 我们的选择：主源 Yahoo + 腾讯/新浪补点；AKShare 作为备选，未作为唯一源。
- 风险：爬虫依赖上游结构；关键数据需交叉验证。

### 2.12 TA-Lib

- 类别：技术指标；BSD；业界标准。
- 可借鉴：指标定义与参数。
- 我们的落地：pandas 原生实现 RSI/MACD/BOLL/ATR/Stochastic/Williams %R/CCI/OBV，避免 Windows C 依赖。

## 3. 采用矩阵

| 项目 | 采用方式 | 是否复制代码 | 许可风险 |
|---|---|---|---|
| TradingAgents | 多模型委员会（非 LLM） | 否 | 低 |
| OpenBB | DataStore/API 分层 | 否 | 低（未用 AGPL 代码） |
| daily_stock_analysis | 看板/信号结构 | 否 | 低 |
| ai-hedge-fund | 多专家模型 | 否 | 低 |
| Qlib | 因子工程思想 | 否 | 低 |
| vnpy | 多市场分层 | 否 | 低 |
| freqtrade | 成本/换手评估 | 否 | 低（未用 GPL 代码） |
| Kronos | 仅思想，不加载权重 | 否 | 需确认模型许可 |
| backtrader | 回测思想 | 否 | 低（未用 GPL 代码） |
| FinBERT | 预留接口，不接入 | 否 | 低 |
| AKShare | 备选数据源 | 否 | 低 |
| TA-Lib | 指标定义，pandas 重写 | 否 | 低 |

## 4. 合规结论

1. **GPL-3.0（freqtrade、backtrader）与 AGPL-3.0（OpenBB）是 copyleft**；如果修改后对外分发，或把 AGPL 代码作为网络服务提供，通常需要开源或商业授权。
2. MIT/Apache-2.0/BSD 是宽松协议，但仍需保留版权与许可声明。
3. **模型权重许可可能不同于代码许可**（Kronos、FinBERT）；商用前必须单独核对。
4. 本项目没有复制上述项目的源代码；所有指标、回测、集成均为 pandas/scikit-learn 独立实现。因此当前代码不因这些项目而变成 GPL/AGPL。
5. “Star 多”不等于“预测准”；本项目的回测结果（见 `analysis/accuracy-audit.md`）说明，工程可靠性与市场可预测性是两件事。

## 5. 来源

- freqtrade LICENSE: https://github.com/freqtrade/freqtrade/blob/develop/LICENSE
- backtrader: https://github.com/mementum/backtrader
- daily_stock_analysis: https://github.com/ZhuLinsen/daily_stock_analysis
- Kronos: https://github.com/shiyu-coder/Kronos
- vnpy: https://github.com/vnpy/vnpy
- FinBERT: https://github.com/ProsusAI/finBERT
- TradingAgents: https://github.com/TauricResearch/TradingAgents
- OpenBB: https://github.com/OpenBB-finance/OpenBB
- Qlib: https://github.com/microsoft/qlib
- AKShare: https://github.com/akfamily/akshare
- TA-Lib: https://github.com/ta-lib/ta-lib-python

## 本轮新增的工程借鉴（2026-10-22）

- **qlib**：因子→训练→滚动回测→组合的流水线，启发了 `models/advanced.py` 的年度扩展窗口与逐日预测；未复制源码。
- **OpenBB / AKShare**：多源数据层与官方源优先级，启发了 `news/sources.py` 的分层抓取、源健康与失败保留；未使用 AGPL 代码。
- **backtrader / freqtrade**：事件回测、成本、换手与 dry-run 思路，启发了 `strategy_eval` 的 5bp 单边、只多/现金、成本拖累与换手统计。
- **TA-Lib**：指标口径（MA/BOLL/RSI/MACD/ATR）已在 `analytics/indicators.py` 独立实现。
- **TradingAgents / ai-hedge-fund**：多智能体辩论**未接入**；原因是 LLM 幻觉、API 成本、缺少可复现的样本外 alpha 证据。我们只采用“LLM 做事件结构化分析 + 确定性加权”的轻量方案。
- **Kronos**：K 线 Foundation Model **未接入**；权重、商用许可、算力与可解释性都需要单独评估。
- **FinBERT / dailystockanalysis**：新闻情绪/日报**未接入**；本项目只做官方源事件分析，不生成无来源的买卖建议。
- **vnpy**：实盘网关**不接入**；本项目不做交易执行。

合规：本轮新增代码全部为独立实现；未复制任何 GPL/AGPL 源码。官方新闻只存标题、摘要、链接与元数据，供本地研究与人工复核。
