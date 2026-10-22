# 2026 时序预测 SOTA 调研与本项目定位

- 调研日期：2026-10-22
- 调研目的：评估是否引入预训练时序基础模型（TSFM）提升方向预测，并定位本项目的合理边界
- 来源：arxiv 2606.27100（Noguer i Alonso & Pereira Franklin, AI Finance Institute, 2026-06）、Transformance 术语库、PickMyTrade 量化指南、蚂蚁国际 Falcon TST 报道

## 1. 2026 主流预训练时序基础模型

| 模型 | 机构 | 架构 | 参数 | 金融适用性 |
|------|------|------|------|-----------|
| Chronos / Chronos-Bolt | Amazon | T5 编解码，值 token 化 | 205M（Bolt-base） | 量化预测，单/多变量 |
| TimesFM 2.5 | Google | 解码器，patch 输入 | 200M/500M | 金融基准平均强，但部分资产被本地监督模型超过 |
| Moirai 2.0 | Salesforce | 解码器，分位数损失+多Token | 11.4M(Small) | 通用多序列，2.0 强化缺失值/鲁棒性 |
| Lag-Llama | ServiceNow+Morgan Stanley | LLaMA 风格，滞后特征 token | 2.45M | 为金融设计，32-1024 点上下文 |
| TimeGPT / TimeGPT-LH | Nixtla | 商业 API | 不公开 | 金融友好工具链 |
| Falcon TST 2.0 / Falcon-X | 蚂蚁国际 | 共享隐原型空间 | 不公开 | 外汇/资金管理多银行验证 |

## 2. 关键实证：2026-06 arxiv 论文（五美股滚动原点）

论文《Pretrained Time-Series Foundation Models for Financial Return Forecasting》在 AAPL/AMZN/GOOG/JPM/META 五只美股上，用滚动原点协议，对比预训练 TSFM（TimeGPT/TimesFM-2.5/Moirai-2.0/Chronos/Chronos-2）与从零训练神经网络（NBEATS/NHITS/PatchTST/iTransformer/KAN），基准为随机游走。

**核心结论**：
- 预训练 TSFM 在 10 个资产×任务组合中赢 8 个（排名占优）；
- 但**相对随机游走的提升"小且稀疏"**，误差改善以基点的小数计；
- Diebold-Mariano 检验：仅 **Chronos@AMZN** 和 **Moirai-2.0@GOOG** 统计显著（2/10）；
- iTransformer（本地监督）在 META 两个任务上击败所有预训练模型；
- 论文原话：TSFM 是"有用的实践先验，降低建模成本"，但**"不是统计可靠 alpha 生成的通用引擎"**。

## 3. 对本项目的含义

| 维度 | SOTA 论文结论 | 本项目对应 |
|------|--------------|-----------|
| 方向准确率天花板 | 日频方向预测，即便最强 TSFM 也只比随机游走"小且稀疏"地好 | 本项目增强模型 56.53% / 有信号日 57.14% 处于合理区间 |
| 98.7% 方向 | 学术+工业共识不可达 | 本项目诚实报告不可达，与论文一致 |
| 预训练 vs 本地监督 | 本地监督在某些资产/regime 仍能超过通用预训练 | 本项目用 sklearn 集成（本地监督）+ 校准 + 选择性，路径合理 |
| 统计显著性 | 10 组合仅 2 组显著 | 本项目不夸大单年/单标的显著结果 |

## 4. 是否引入 TSFM 的决策

**决定：本轮不引入 Chronos/TimesFM/Moirai 等预训练权重**。理由：
1. 论文已证明即便最强 TSFM，相对随机游走也只"小且稀疏"地好——不会把 57% 变成 98.7%；
2. 引入需下载 200M-500M 参数权重（Chronos-mini 也要 20M+），打包体积从 388MB 暴涨到 1GB+，且需 PyTorch 运行时（被本项目 excludes 排除）；
3. TSFM 优势在零样本多序列场景；本项目是单标的深度回测，本地监督模型（iTransformer 在 META 击败所有 TSFM 即证）路径更合适；
4. 合规：TimesFM Apache-2.0 可用，但 Chronos/Moirai 部分权重许可需逐一核实；不引入避免许可链风险。

**未来可选路径**（不在本轮）：
- 引入 Chronos-Base（mini, 20M）作为"波动率/区间预测"的辅助输入（论文显示 TSFM 对波动率更有效，对方向弱）；
- 用 TSFM 的分位数输出（P10/P50/P90）替代本项目当前的残差分位区间法，可能改善区间宽度。

## 5. 同类金融预测应用架构借鉴

基于已有 `analysis/open-source-quant-review.md`（11 项目评审）+ `reverse/tradingview/`（TradingView 逆向）+ 本次 SOTA 调研：

| 借鉴点 | 来源 | 本项目落地 |
|--------|------|-----------|
| Alpha158 因子工程 | Qlib（微软） | 特征扩到 ~60 个（动量/波动/形态/regime/季节/跨资产） |
| 回测+成本+换手 | freqtrade | 成本后策略评估（5bp 单边、年换手、Sharpe、最大回撤） |
| 多智能体辩论 | TradingAgents | 多模型委员会（Ridge/GBM/RF/Logit/ExtraTrees），用样本外指标而非"语气"定权重 |
| 多市场数据层 | OpenBB | DataStore 统一长表 + 本地 HTTP API |
| 托管 Web 终端 | TradingView 逆向 | pywebview + ECharts 本地窗口（采纳布局/主题持久化，不采纳 remote 桥） |
| 概率校准+选择性 | Lopez de Prado AFML | isotonic 校准 + |p-0.5|≥0.05 选择性输出 |
| 官方一级源 | 《数据源手册》 | SEC EDGAR 适配器（免费无 Key） |

## 6. 一句话总结

2026 SOTA 证明：即便最强预训练时序模型，在日频方向预测上也只比随机游走"小且稀疏"地好（10 组合仅 2 组统计显著）。本项目的 57% 方向准确率（有信号日）处于学术界合理区间；**诚实的 57% 与 SOTA 论文结论一致，比虚构的 98.7% 更可信**。
