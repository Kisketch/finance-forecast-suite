# 方法论与可复现说明

## 1. 目标与边界

本项目的目标是构建一个**本地可复现**的金融分析/预测桌面应用，并逆向一个成熟金融终端的产品结构。边界：

- 不做交易执行、不接券商账户、不提供投资建议；
- 不声称价量模型能稳定预测价格；
- 所有结论必须能追溯到数据、代码与回测证据；
- 对不可得的数据（如付费一致预期、Level-2、逐笔）明确标注缺失。

## 2. 数据管道

### 2.1 资产宇宙

`config/universe.yaml` 定义了 97 个标的：

- 市场指数：标普500、纳斯达克、道指、罗素2000、恒生、恒生国企、恒生科技、上证、沪深300、创业板指；
- 板块 ETF：XLRE、VNQ、XLE、XOP、ICLN、TAN、XLU、XLK、XLF、XLV、XLY、XLP、XLI、XLB、XLC；
- 美股个股：REITs（PLD、SPG、O、DLR、PSA、EQIX、AVB、EQR）、能源（XOM、CVX、COP、EOG、SLB、OXY、MPC、VLO、KMI、LNG）、科技/金融（AAPL、MSFT、NVDA、GOOGL、AMZN、META、JPM、GS、MS、BRK-B）；
- 港股：腾讯、阿里、美团、中国移动、HKEX、汇丰、友邦、平安、新鸿基、领展、中国海外、华润置地、中海油、中石化、中石油、神华、中煤；
- A 股：茅台、平安、招行、工行、中信证券、万科、保利、招商蛇口、中石油、中石化、神华、长江电力、宁德时代、比亚迪、隆基、五粮液；
- 商品/美元：WTI、布伦特、天然气、黄金、白银、铜、美元指数。

### 2.2 抓取

主源：Yahoo Finance，通过 `yfinance`（自动处理 cookie/crumb），`period="max"`、`interval="1d"`、`auto_adjust=True`。

补点：

- 恒生科技（^HSTECH）、创业板指（399006.SZ）、科创50（000688.SS）、沪深300（000300.SS）：Yahoo 对部分中国指数只返回 1 行或 `period=max` 不支持，改用腾讯前复权 K 线接口（`web.ifzq.gtimg.cn` / `proxy.finance.qq.com`），最多 2000 根；
- AVB、EQR：Yahoo 只返回 1 行（2026-08 后停更），改用新浪美股日 K 接口，取全历史；
- 所有补点都记录在 `data/metadata/data_quality.json` 的 `source` / `patched` / `flags` 字段。

### 2.3 清洗

1. 统一列名：`date, open, high, low, close, volume`；
2. 去重（同日保留最后一条）、按日期排序、时区归一；
3. OHLC 关系修复：`high = max(high, open, close)`、`low = min(low, open, close)`；
   - 修复 37 个标的、1,170 行；不改收盘价；
   - 最大修复幅度：0823.HK 24.4%（2011-04-04，low > open 的复权断点）、300750.SZ 14.4%（2026-10-21，high < open 的当日字段异常）；
   - 期货（GC/SI/HG/NG/CL/BZ）的修复主要来自连续合约拼接，不能消除换月跳空。
4. 质量分级：
   - `ok`：行数 ≥250、非停更、无负价/复权疑点；
   - `degraded`：`short_history`、`stale_data`、`negative_price`、`suspect_adjustment` 之一；
   - `failed`：抓取失败（本次为 0）。

### 2.4 质量结果

- 97 个标的、685,774 行、1927-12-30 至 2026-10-21；
- 93 正常 / 4 降级 / 0 失败；
- 降级：AVB、EQR（2026-08 后停更）、600028.SS（2013-06-13 复权疑点）、CL=F（2020-04-20 负油价）；
- 标记：`extreme_move` 35、`front_month_roll` 6、`yield_level_series` 1、`ohlc_repaired` 37、`stale_data` 2、`negative_price` 1、`suspect_adjustment` 1；
- OHLC 关系违例：0；
- 跨源核对：上证指数 3713.03 vs 腾讯 3713.03（差 0.0001%）；腾讯控股 393.80 vs 393.80（0%）。

### 2.5 已知数据问题

| 问题 | 影响 | 处理 |
|---|---|---|
| AVB/EQR 2026-08 后停更 | 当前排行会误把 8 月价格当现价 | 标记 `stale_data`，从市场/板块当前排行剔除；历史回测仍可用 |
| 600028.SS 2013-06-13 单日 +26%、06-19 -24% | 长周期收益/回撤可能失真 | 标记 `suspect_adjustment`；不改原始值，报告披露 |
| 期货连续合约换月 | NG=F 2026-01-29 出现 -47% 假跳空 | 标记 `front_month_roll`；不用于默认预测/排行 |
| CL=F 2020-04-20 负油价 | 百分比收益/对数收益失效 | 标记 `negative_price`；回测跳过负价区间 |
| ^TNX 是收益率水平 | 百分比变化会放大 | 用百分点变化；标记 `yield_level_series` |
| 缺基本面估值 | 无法做 P/E、P/B、股息率横截面 | 明确列为缺失；券商观点页只引用公开目标价 |

## 3. 指标

### 3.1 技术指标

- MA5/10/20/50/120/200；EMA12/26；
- MACD(12,26,9)：DIF、DEA、柱；
- RSI14（Wilder 平滑）；
- BOLL(20,2)：中轨/上轨/下轨；
- ATR14（Wilder）；
- 20 日年化波动、回撤序列、夏普、索提诺。

### 3.2 绩效

- 1 周/1 月/3 月/6 月/YTD/1 年收益；
- 1 年年化波动、夏普、最大回撤；
- 站上 MA50/MA200 比例（市场宽度）；
- 相对强弱：板块 ETF / 标普500，近 63/126 日；
- 相关性：近 252 日日收益 Pearson。

## 4. 预测实验

### 4.1 特征（20 个，全部为 t 时刻已知）

- 对数收益滞后 1/2/3/5/10/21 日；
- 5/21/63 日滚动均值与波动；
- RSI14；
- MACD 柱 / 收盘价；
- 收盘价 / MA20、MA50、MA200 - 1；
- 当前回撤；
- 成交量 21 日 z-score。

### 4.2 目标

`y_t = log(close_{t+h} / close_t)`，h = 1/5/20 个交易日。

### 4.3 无未来函数设计

- 训练集只包含**目标已实现**的样本：测试点为 i 时，训练样本的最后一个目标日期 ≤ i；
- 特征只使用 `shift(+n)`、`rolling`、`ewm` 等向后看算子；
- 测试点间隔 = h，避免重叠目标造成自相关与乐观偏差；
- 训练窗口最多 2,000 个交易日（约 8 年），只保留最近 500 折（GBM 300 折），避免用 1927 年以来全部历史做数千次拟合；
- 每次拟合都重新标准化（Ridge 的 `StandardScaler` 只在训练集上 fit）。

### 4.4 模型

- 基线：随机游走（预测 0 对数收益）；
- Ridge：alpha=10，20 个特征；
- HistGradientBoosting：max_iter=200、max_depth=3、learning_rate=0.05、min_samples_leaf=30、l2=1.0。

### 4.5 指标

- MAE/RMSE（对数收益）；
- MAPE（价格）；
- 方向准确率：`sign(pred) == sign(actual)`；
- 始终看多基准：`actual > 0` 的比例；
- Skill = `1 - MAE_model / MAE_random_walk`；≤0 表示未跑赢基准；
- Diebold-Mariano：平方损失、无自协方差修正、正态近似双侧 p 值；
- 90% 区间：滚动残差的 5%/95% 分位数映射到价格。

### 4.6 结果（摘要）

27 组（8 资产 × 3 周期 Ridge + 3 资产 × 5 日 GBM）**全部 Skill < 0**：

- 最好：标普500 5 日 Ridge，Skill -1.1%，方向 52.8%，始终看多 61.0%，DM p=0.456；
- 最差：XLRE 5 日 Ridge，Skill -11.5%，方向 49.0%，始终看多 56.2%；
- 部分 DM p 值显著（标普20日 0.009、恒生20日 0.000、XLRE GBM 0.001），但方向是“显著更差”；
- 结论：价量技术模型在主要指数上不产生可用 alpha；预测页应定位为情景/风险工具。

完整结果：`analysis/forecast_results.json`。

### 4.7 高级模型与准确率审计（2026-10 增补）

在原有 20 特征 / 2 模型基础上，新增：

- 33 个特征：动量、波动、量价、Stochastic、Williams %R、CCI、OBV、跨资产上下文；
- 模型：Ridge、ElasticNet、Huber、RandomForest、HistGBM、逻辑回归、三模型集成；
- 稀有事件：`1/(1+(z-2)^2)` 降权、winsorize、Huber；
- 历史留出：1927–1948 训练，1949 预测；
- 年度滚动：1950–2026，每年只用上一年末已实现目标；
- 区间校准：名义分位 + 覆盖率定向（60% 校准 / 20% 调参 / 20% 留出）；
- 成本后策略：只多/现金、5bp 单边、换手/Sharpe/最大回撤。

核心结果：

- 1949 留出最好 58.8%（HistGBM 分类），“始终看多”49.6%；
- 1950–2026 年度 55.15%，但“始终看多”56.74%——长样本上模型跑输多头偏置；
- 2000–2026 现代最好 52.3%（集成），全部 Skill < 0；
- 稀有事件降权把 2000–2026 Ridge 的方向从 49.1% 提升到 51.4%–51.5%，Skill 从 -2.77% 改善到 -0.38%–-0.63%，但仍低于“始终看多”；
- 98.7% 方向准确率不可达；98.7% 区间覆盖率可通过定向校准达到（99.36%，宽度 15.6% 对数收益）；
- 成本后策略年化 7.47%，低于买入持有 8.52%，最大回撤 -58.75%。

详见 `analysis/accuracy-audit.md` 与 `analysis/advanced_audit.json`。

## 5. 应用架构

```
src/finance_app/
├── data/
│   ├── fetch_market.py   # Yahoo 抓取
│   └── store.py          # 长表加载、总览、板块、序列、预测缓存
├── analytics/
│   ├── indicators.py     # 技术/风险指标
│   └── performance.py    # 横截面绩效、相关性、宽度
├── models/
│   ├── forecast.py       # 特征、滚动回测、DM、情景区间
│   └── advanced.py       # 多模型、年度滚动、稀有事件、区间校准、成本策略
└── ui/
    ├── server.py         # 标准库 HTTP API + 静态资源
    ├── app.py            # pywebview / WebView2 桌面窗口
    └── web/              # HTML/CSS/JS + ECharts
```

- 后端无 FastAPI/Flask 依赖，使用 `http.server.ThreadingHTTPServer`，降低安装成本；
- 前端 ECharts 本地化（`web/echarts.min.js`），离线可用；
- 桌面窗口用 pywebview + Edge WebView2（Windows 10/11 自带）；
- API：`/api/overview`、`/api/series`、`/api/sector`、`/api/forecast`、`/api/analysts`、`/api/quality`、`/api/universe`、`/api/audit`、`/api/projects`。

## 6. 复现

环境：Windows 10/11 x64、Python 3.14.7、Node.js 24（仅 REA CLI 需要）。

```powershell
# 安装依赖
py -m pip install -r requirements.txt

# 1) 抓取（约 4 分钟，97 标的）
py src\finance_app\data\fetch_market.py

# 2) 补点（腾讯/新浪）
py scripts\patch_indices.py
py scripts\finalize_quality.py

# 3) OHLC 修复与校验
py scripts\repair_ohlc.py
py scripts\validate_all.py

# 4) 回测（约 3 分钟）
py scripts\build_analysis.py

# 5) 启动桌面应用
py -m finance_app.ui.app
```

## 7. 质量门禁自检

| 项目 | 结果 |
|---|---|
| 数据来源可追溯 | 通过（Yahoo/腾讯/新浪，逐标的记录） |
| 时间戳与复权口径 | 通过（前复权，报告披露） |
| OHLC 一致性 | 通过（0 违例） |
| 跨源抽查 | 通过（0.0001% / 0%） |
| 未来函数 | 通过（训练目标已实现、测试间隔 h） |
| 基准对比 | 通过（随机游走 + 始终看多） |
| 统计显著性与方向 | 通过（DM p 与 Skill 同时报告） |
| 失败/降级披露 | 通过（4 个降级标的与原因） |
| 可复现命令 | 通过（见上） |
| 投资建议边界 | 通过（明确研究用途，不做交易执行） |

## 8. 局限

1. 只有价量数据，没有盈利、估值、一致预期、资金流、持仓、期权隐含波动率；
2. 没有做 FX 调整，跨市场收益不可直接比较；
3. 期货是连续合约，换月跳空未做 back-adjustment；
4. 停更标的（AVB/EQR）只能用于历史，不应用于当前；
5. 回测是单资产、单模型，没有做组合权重、交易成本、滑点、容量分析；
6. 预测区间来自残差分位数，假设残差分布近似稳定；极端 regime 下会失效；
7. 券商观点来自公开报道，目标价会修订，不能当作实时一致预期；
8. 逆向分析是静态的，未执行 TradingView Desktop，也未抓取其托管网页端。

## 9. 新闻层方法

官方新闻的抓取、来源分层、规则/LLM 分析、区域/板块加权、与价格先验融合、前向影子验证与受限权重更新，见 `analysis/news-methodology.md`。

关键边界：

- 只用官方一级源；不使用社交媒体/论坛/聚合站。
- 新闻层没有历史新闻库，不能做真正的历史回测；只做前向影子测试。
- 方向准确率 98.7% 在价量+新闻的样本外不可承诺；98.7% 只作为区间覆盖率目标。
- LLM 必须返回严格 JSON；解析失败回退规则；新闻正文被视为不可信数据。
