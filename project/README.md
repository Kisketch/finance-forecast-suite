# 金融分析预测终端（FIN Terminal）

一个面向 Windows 的本地金融分析/预测桌面应用：多市场、多板块、可复现的数据管道、诚实的滚动回测，以及一个基于 REA 的金融 App 逆向案例（TradingView Desktop）。

> 研究用途，不构成投资建议。不做交易执行。

![总览](docs/overview.png)

## 1. 功能

| 页面 | 内容 |
|---|---|
| 总览 | 10 个全球指数、板块热力图、市场宽度、跨市场相关性、技术信号 |
| 市场 | 美股 / 港股 / A 股三大市场，指数归一化、横截面表现、宽度 |
| 板块 | 房地产、能源、油气、清洁能源、科技、金融、公用事业；相对强弱与成分股 |
| 个股 | K 线、MA20/50/200、BOLL、成交量、RSI、MACD、动量/风险 |
| 预测实验室 | Ridge / GBM / RandomForest / 三模型集成，扩展窗口滚动回测，随机游走基准，90% 情景区间 |
| 新闻事件 | 官方源聚合、事件分析（规则/LLM）、区域与板块影响系数、综合预测、证据链 |
| 模型接入 | OpenAI 兼容端点、密钥本地保存、受限自主优化、前向影子验证、官方源健康 |
| 算法审查 | 1948→1949 历史留出、1950–2026 年度滚动、98.7% 目标判定、区间校准、置信度曲线、稀有事件降权、区域模型、开源项目合规 |
| 券商观点 | 高盛、大摩、JPM、UBS、中金、中信、华泰、IEA、JLL、Deloitte 等公开观点与来源 |
| 数据质量 | 97 个标的的覆盖、缺失、异常标记与降级原因 |

![预测实验室](docs/forecast.png)
![算法审查](docs/audit.png)

### 1.1 官方新闻与大模型接入（新增）

**只接官方一级源**，不接社交媒体、论坛、聚合站：

- 政府/央行/监管/交易所：Federal Reserve、ECB、Bank of England、USTR、HKSAR Government、HKMA、上海证券交易所、中国政府网（英文）；
- 多边机构：IEA；
- 公司新闻室：Apple、OpenAI、Google、Meta。

当前实现 14 个源；同步时逐源记录成功/失败与耗时。SEC、BLS、IMF、BIS、OPEC 等在当前网络下返回 403/404/超时，默认不启用，页面会保留失败原因。

**处理链**

```
官方 RSS/列表页
  → 去重、日期解析、正文摘要
  → 规则分析（无模型时）
  → LLM 结构化分析（配置模型后）
  → 区域/板块影响系数（来源层级 × 时效衰减 × 置信度 × 相关性 × 新颖度）
  → 与价格先验加权：combined = (1-w) × price + w × news
  → 前向影子验证 → 受限权重更新
```

- 新闻事件页提供“同步官方新闻 / 分析待处理 / 模型重分析 / 同步行情”。行情同步在后台执行抓取、补点、质量修复与校验，完成后自动刷新页面。行情源依赖 Yahoo；若上游限流，脚本会在前 3 个标的连续失败时快速退出并保留旧数据，不会用不完整数据覆盖。
- 新闻总权重 `w` 默认 0.15，硬边界 0.05–0.35；只有样本 ≥20 才更新，单次变化 ≤±0.05。
- 区域权重边界 0.5–1.5，单次变化 ≤±8%；领域权重边界 0.6–1.4。
- 每次变更写入 `data/models/news_weights.json` 的 `history`，可在“模型接入”页查看。
- 这不是“模型改代码”，而是受限的在线权重调整；LLM 只能提议，应用仍走边界与审计。

**接入你已有的模型**

支持任意 OpenAI-compatible 端点（Ollama / LM Studio / vLLM / DeepSeek / OpenAI）：

```powershell
# 示例：本地 Ollama
# 先在 Ollama 拉取模型，例如 qwen2.5:7b
# 然后在 App 的“模型接入”页填：
#   Base URL: http://127.0.0.1:11434/v1
#   Model:    qwen2.5:7b
#   API Key:  留空
```

也可以直接编辑 `config/llm.local.json`（不要提交到公开仓库）：

```json
{
  "base_url": "http://127.0.0.1:11434/v1",
  "api_key": "",
  "model": "qwen2.5:7b",
  "timeout_seconds": 60,
  "temperature": 0.1,
  "max_tokens": 900
}
```

未配置模型时，新闻分析自动回退到规则评分；规则评分是**保守的**，没有明确方向词就输出中性，不会为了“看起来有观点”而编方向。

**边界（必须阅读）**

- 行情是日线：综合预测的是**下一交易日/周期**，不是盘中实时；官方新闻也有发布延迟。
- 新闻层**没有历史新闻库**，无法做真正的历史回测，只能做前向影子测试；页面会显示样本数，样本不足不会更新权重。
- 新闻分析是概率判断，不是事实；所有事件卡保留官方原文链接与来源层级，需人工复核。
- 方向准确率 98.7% 在价量+新闻的样本外**不可承诺**；98.7% 只作为“区间覆盖率”目标（已做到 99.4%，但区间很宽）。
- 新闻正文被视为不可信数据；系统提示明确禁止执行文章内指令，LLM 没有浏览/工具权限。

相关文件：`config/news_sources.yaml`、`config/llm.example.json`、`data/news/news.db`、`analysis/news-methodology.md`。

### 1.2 AI 增强预测（v0.4 新增）

在价量基础上叠加机器学习增强（`src/finance_app/models/ml_advanced.py`）：

- **增强特征**（~60 个，基线 33 个之上）：ADX/DI 趋势强度、KDJ、波动率 regime 分位、EWMA 波动率、量价背离、月份季节正余弦、EMA 距离、20 日新高新低距离；
- **isotonic 概率校准**：CalibratedClassifierCV 让 `predict_proba` 真实反映经验频率，选择性输出才有意义；
- **时间衰减样本权重**：5 年半衰期，远期样本权重低，适应 regime 漂移；
- **选择性输出**：`|p−0.5|≥0.05` 才给方向，否则"无信号"——承认"只在少数日有把握"。

**审计结果**（`analysis/enhanced-audit-2026-10-22.md`）：

| 口径 | 基线 | 增强 | 始终看多 |
|------|------|------|---------|
| 1949 留出全程 | 58.8% | 57.60% | 49.6% |
| 2000-2026 全程 | 52.3% | **56.53%** | 56.7% |
| 2000-2026 有信号(0.05) | — | **57.14%**（51.4% 覆盖） | 56.7% |

增强把基线从跑输始终看多 4.4pp，提升到追平；在 51% 覆盖的有信号日首次超过始终看多。**方向准确率 98.7% 仍不可达**（学术共识），这是诚实且实质的提升。

API：`GET /api/forecast/enhanced?symbol=^GSPC&horizon=5`、`GET /api/audit/enhanced`。

### 1.3 SEC EDGAR 官方财务数据源（v0.4 新增）

依据《全球股市官方数据源手册》，SEC EDGAR 是美国唯一全免费、无需 API Key、限速 10 req/s 的官方一级源。`src/finance_app/data/sec_edgar.py` 提供：

- ticker → CIK 映射（本地缓存 + 在线增量补充）；
- XBRL companyfacts 拉取（营收/净利/EPS/资产/负债/股本等）；
- point-in-time：保留全部重述版本，按 as_of 取当时最新；
- 派生比率（净利率/资产负债率/权益比等）。

API：`GET /api/fundamentals?symbol=AAPL`。仅覆盖美股（SEC 管辖）。

常用命令：

```powershell
py scripts\sync_news.py                 # 同步官方源
py scripts\analyze_news.py --limit 20    # 规则/LLM 分析待处理
py scripts\daily_update.py               # 行情 + 新闻 + 评估 + 权重更新（每日）
```


## 2. 数据

- 97 个标的、685,774 行日线，1927-12-30 至 2026-10-21；
- 市场：美国（S&P 500、Nasdaq、Dow、Russell 2000）、香港（HSI、HSCEI、HSTECH）、中国（上证、沪深300、创业板、科创50）；
- 板块：房地产（XLRE/VNQ 及 REITs）、能源（XLE/XOP）、清洁能源（ICLN/TAN）、科技/金融/公用事业等；
- 商品：WTI、布伦特、天然气、黄金、白银、铜；美元指数；
- 质量：93 正常 / 4 降级 / 0 失败；OHLC 违例 0；跨源核对误差 ≤0.0001%。

数据源：Yahoo Finance（yfinance，前复权）为主；腾讯行情补恒生科技/创业板/科创50/沪深300；新浪财经补 AVB/EQR 全历史。详见 `analysis/methodology.md`。

## 3. 分析结论（2026-10-21）

- **美国韧性**：标普 500 7,712.57，YTD +12.45%，近 1 年 +15.73%；
- **中国/香港承压**：恒生 23,651.87（YTD -10.20%）、恒生科技 3,994.77（YTD -30.36%）、沪深300 4,111.93（YTD -12.84%）、创业板 2,694.71（1 月 -17.98%）；
- **能源独强**：XLE 近 1 年 +62.61%，XOP +65.19%；WTI 100.01、布伦特 110.97；IEA 却预计 2026 年需求 -2.6 mb/d——价格由供给/地缘溢价主导；
- **房地产分化修复**：XLRE 近 1 年 +4.37%，但万科A -49.19%、保利 -29.14%；华润置地 +6.62%、中国海外 -6.73%；
- **相关性**：标普-恒生 0.06、标普-上证 0.12、恒生-上证 0.51、原油-标普 -0.39、黄金-美元 -0.39；
- **预测要诚实**：旧版 27 组 Ridge/GBM 滚动回测全部未跑赢随机游走（Skill -0.4% 到 -11.5%）；新版年度集成审计的 MAE Skill +1.17%，但方向准确率 55.15% 仍低于“始终看多”56.74%。

### 98.7% 准确率审计

- **方向准确率 98.7% 在真实样本外数据上不可达**：1949 留出最好 58.8%，1950–2026 年度 55.15%，2000–2026 现代 52.3%；“始终看多”基准在长样本上是 56.74%。
- **98.7% 区间覆盖率可达**：覆盖率定向校准在留出段达到 99.36%，但区间宽度约 15.6% 对数收益；覆盖率不等于方向准确率。
- **稀有事件降权有效但有限**：2000–2026 Ridge 的方向准确率从 49.1%（不降权）提升到 51.4%–51.5%，Skill 从 -2.77% 改善到 -0.38%–-0.63%，但仍低于“始终看多”。
- **成本后策略跑输买入持有**：5bp 单边、5 日周期，年化 7.47% vs 买入持有 8.52%，最大回撤 -58.75%。
- 完整证据：`analysis/accuracy-audit.md`、`analysis/advanced_audit.json`。

完整报告：

- `analysis/market/2026-market-outlook.md`
- `analysis/methodology.md`
- `analysis/news-methodology.md`
- `analysis/accuracy-audit.md`
- `analysis/open-source-quant-review.md`
- `analysis/analysts/broker-profiles.md`
- `analysis/reverse/tradingview-reverse-report.md`

## 4. 逆向案例：TradingView Desktop

- 目标：TradingView Desktop `3.4.1.8194`（Windows x64 MSIX）
- 工具：REA `rea-agents 6.7.0`，静态分析 `app.asar`（不执行）
- 规模：166 个相关文件、62 个已解析 JS、1,896 个模块、888,069 个 AST 节点、6,621 条发现
- 结论：Electron 外壳 + 托管 Web 终端的混合架构；外壳提供 48 个 IPC 通道（`tvd:get-watchlist`、`tvd:get-theme`、`tvd:layout-change`、`tvd:get-credentials`、`tvd:screen-capture` 等），并保留 `REMOTE_BROWSER_*` remote 桥
- 我们采纳：自选/布局/主题持久化、信号/筛选/多市场结构；不采纳：remote 桥、托管黑盒、交易执行
- 证据：`reverse/tradingview/`（419 MB 证据包 + 摘要 + 应用事实）

## 5. 快速开始

环境：Windows 10/11 x64、Python 3.11+（本机 3.14.7）。

### 方式一：直接运行打包好的 exe（推荐）

解压 `dist/FIN_Terminal/` 后双击 `FIN_Terminal.exe` 即可，无需安装 Python。

### 方式二：从源码运行

```powershell
cd "C:\Users\Lgnatius\Desktop\FIN_Terminal_Full_Package_2026-10-22\project"
py -m pip install -r requirements.txt

# 已有数据，直接启动桌面窗口
.\run.ps1
```

### 打包 exe

```powershell
py -m pip install pyinstaller
py -m PyInstaller fin_terminal.spec --noconfirm
# 产物：dist\FIN_Terminal\FIN_Terminal.exe
```

首次/重新抓取数据（约 4 分钟）：

```powershell
py src\finance_app\data\fetch_market.py
py scripts\patch_indices.py
py scripts\finalize_quality.py
py scripts\repair_ohlc.py
py scripts\validate_all.py
# 可选：重新生成算法审计（约 10 分钟）
py scripts\rare_weight_experiment.py
py scripts\run_advanced_audit.py
```

只启动本地 API（浏览器访问 http://127.0.0.1:8765）：

```powershell
.\run_server.ps1
```

## 6. 项目结构

```
金融分析预测/
├── config/
│   ├── universe.yaml              # 97 个标的
│   ├── news_sources.yaml          # 14 个官方新闻源
│   └── llm.example.json           # 模型接入模板
├── data/
│   ├── raw/                       # 原始 CSV（Yahoo/腾讯/新浪）
│   ├── processed/prices_long.csv  # 685,774 行长表
│   ├── metadata/data_quality.json
│   ├── analysts/analyst_views.json
│   ├── news/news.db               # 新闻、分析、预测、源健康
│   └── models/news_weights.json   # 受限权重与审计历史（首次更新后生成）
├── src/finance_app/
│   ├── data/                      # 抓取、仓库
│   ├── analytics/                 # 指标、绩效、相关性
│   ├── models/forecast.py         # 简单回测、DM、情景区间
│   ├── models/advanced.py         # 多模型、年度滚动、稀有事件、区间校准
│   ├── news/                      # 官方源、分析、LLM、加权、优化
│   └── ui/                        # HTTP API、pywebview、Web UI
├── scripts/                       # 补点、校验、新闻、报告表
├── analysis/                      # 市场/方法/新闻/券商/逆向报告
├── reverse/tradingview/           # 逆向证据
├── docs/                          # 截图
├── requirements.txt
├── run.ps1 / run_server.ps1
├── run_daily.ps1                  # 行情+新闻+评估+权重
└── REA.md                         # REA 配置状态
```

## 7. 依赖

`requirements.txt`：

```
pandas>=3.0
numpy>=2.5
yfinance>=1.7
scikit-learn>=1.9
PyYAML>=6.0
pywebview>=6.2
```

- 图表：ECharts 5.5（本地 `src/finance_app/ui/web/echarts.min.js`，离线可用）
- 桌面壳：pywebview 6.2 + Edge WebView2（Windows 10/11 自带）
- 后端：Python 标准库 `http.server`，无 Flask/FastAPI 依赖
- 逆向：Node.js 24 + `rea-agents` 6.7.0（可选，仅用于复现逆向）

## 8. 已知限制

- 仅价量数据，无盈利/估值/一致预期/资金流/期权隐含波动率；
- 未做 FX 调整，跨市场收益不可直接比较；
- 期货连续合约存在换月跳空（NG=F 2026-01-29 是典型例子）；
- AVB/EQR 2026-08 后停更，已从当前排行剔除；
- 600028.SS 2013 年存在复权疑点，已标记；
- 预测区间来自残差分位数，极端 regime 下会失效；
- 逆向分析是静态的，未执行 TradingView Desktop，也未分析其托管网页端。

## 9. 产物路径

- 应用根目录：`C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测`
- 数据长表：`data\processed\prices_long.csv`
- 质量报告：`data\metadata\data_quality.json`
- 校验报告：`analysis\validation_report.json`
- 回测结果：`analysis\forecast_results.json`
- 算法审计：`analysis\advanced_audit.json`
- 逆向证据：`reverse\tradingview\rea-analysis.json`

## 10. 许可与合规

- 本项目代码用于研究与教育；
- 数据版权归原始提供方（Yahoo/腾讯/新浪等），请遵守其条款；
- 券商观点仅做公开信息摘要，不复制全文、不构成投资建议；
- TradingView 是其权利人的商标；逆向分析仅用于学习产品结构，不重新分发其代码或资源。
