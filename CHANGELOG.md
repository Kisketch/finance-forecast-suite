# 变更日志（CHANGELOG）

本项目含两个应用：**FIN_Terminal**（离线多市场研究终端）与 **FinPredict**（实时联网预判桌面应用）。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号与 [VERSIONS.md](VERSIONS.md) 对应。

---

## [0.5] — 2026-10-31 · FIN_Terminal 新闻层算法升级

### Added
- **同簇证据收益递减**：文本 Jaccard 去重之外，(event_type, region) 相同的第 n 条证据权重 ×0.5^(n-1)——抑制"同一事实被多源/多人分别报道"造成的证据总量（coverage）虚增与新闻层超配，相关证据次线性累积（`impact._cluster_decay`）
- **数据驱动融合尺度**：scale 优先用 horizon 期已实现波动率 σ_h（"score=1 的强新闻 ≈ 1 个 horizon 标准差"），替代手拍常数表（原表本身近似 1.2%×√T 的粗版）；极端值钳制 [0.006, 0.08]，数据缺失自动回退常数表（`impact._horizon_vol_scale`）
- **波动率 regime 乘子**：20 日已实现波动率在过去一年中的分位 <25% → ×1.15（低波动期价格信号弱、新闻相对信息价值高），>75% → ×0.85（噪音大）；`regime_mult` 可配置先验（`impact._vol_regime`）
- **LLM confidence 在线校准**：原始 confidence 不再直接进权重乘法链，先按 lo/mid/hi 分桶经前向命中率校准（Beta(2,2) 先验平滑），乘子钳制 [0.3, 1.5]，无校准表时恒等回退（`impact.calibrated_confidence` + optimizer 校准表更新）
- **逆 MSE 权重更新**（Granger–Ramanathan 两分量特例）：已实现样本 ≥30 时 `w_target = 0.05 + 0.30 × mae_price/(mae_price+mae_news)`——news 与 price 同精度 → 0.20，news 完美 → 趋 0.35 上限，无技能 → 趋 0.05 下限；样本少回退原方向命中差规则，实际启用哪条规则透明记录进审计历史
- **增量技能统计**：`performance` 新增 news 相对 price 的**配对方向命中差 + 95% CI**（正态近似，n≥30 且 CI 不含 0 才标显著），以及 combined 残差 q05/q95 **轻量共形区间**（n≥20）——正面回答"新闻层是否比价格先验多知道什么"
- **回归测试** [project/scripts/test_news_upgrades.py](project/scripts/test_news_upgrades.py)：24 项断言，无网络、无真实数据依赖，可离线复跑

### Fixed
- **apply_proposal 重复定义导致频控失效**：`optimizer.py` 中该函数被定义两次，后一个（无频控）覆盖了前一个（带 10 分钟频控）——反复应用 LLM 提议可逐步把权重推至硬边界；已删除重复定义，频控恢复并有回归断言
- **逆 MSE 边界**：price 模型完美（mae_price=0）时条件写错误回退 hit-diff 规则，现正确给出 w 向 0.05 下限步进

### Compatibility
- 旧权重文件（v0.4 及以前）自动合并新键默认值（`cluster_decay` / `scale_vol_mult` / `regime_mult` / `confidence_calibration`），行为向后兼容；所有新逻辑带数据缺失回退路径，缺数据时与 v0.4 行为一致

### Verification
- `py scripts/test_news_upgrades.py`（24 项）、`test_news_pipeline.py`、`test_news_core.py` 全部通过；全仓 57 个 .py 文件编译通过
- 活服务实测：`/api/news/impact`、`/api/news/performance`、`/api/optimizer/status`、`/api/news/sources` 结构正确，四个新权重键正确暴露，服务日志无异常

---

## [1.3] — 2026-10-22 · 合并套件 / 图标 / 五语文档 / Git 研发流程

### Added
- **应用图标**：深蓝圆角 + 三根上涨 K 线 + 金色趋势箭头（PIL 绘制），多尺寸 `icon.ico` + `icon.png`，PyInstaller spec 应用后重新打包
- **五语 README**：中文主文档 + English / Français / Русский / Español，各含简介、功能表、使用说明、AI 接入表、诚实边界与图文
- **[AUDIT.md](AUDIT.md)**：准确率审计总览页（关键数字表 + 增强溯源 + **5 张真实界面截图** + 报告索引 + 复现命令 + 判读纪律）
- **[FinPredict/AUDIT.md](FinPredict/AUDIT.md)**：FinPredict 独立审计页（模型结构 / A 股实测 / 选择性输出 / 多周期区间宽度 / 已知局限）
- **[CHANGELOG.md](CHANGELOG.md)**（本文件）与 **[DEVELOPMENT.md](DEVELOPMENT.md)**（分支策略 / 提交规范 / 质量门 / 阶段时间线）
- **MIT LICENSE** + 授权范围说明表（不含第三方逆向证据与市场数据）
- **Git 研发流程**：`.gitignore` + 11 次阶段化提交（docs → terminal → audit → FinPredict → qlib → ai → i18n → releases → 下载链接 → 改名+LICENSE+AUDIT）+ `v1.3` tag
- **完整快照归档**：`snapshots/finance-forecast-suite_v1.3.zip`（源码 + 文档 + 图标 + 两个最终 exe），并作为 Release v1.3 资产发布
- **仓库 topics** 12 个（finance / quantitative-trading / stock-forecast / multi-agent / llm / pywebview …）

### Changed
- 仓库改名：`finpredict-suite` → **Kisketch/finance-forecast-suite**（涵盖双应用）；旧名 301 重定向正常，README 下载直链同步更新
- 目录合并：FinPredict 整合入主目录，消除约 1GB 重复构建产物（build_*/dist_enh/dist_fix 仅保留最终 dist_icon）
- exe 体积 28.8MB 超出 GitHub 网页上传 25MB 限制 → 改用 **Release 资产** 发布（git HTTP 推大对象两次被连接重置）

### Verification
- 两个 exe 直链实测 302→200，字节数 30,157,785 / 29,104,707 正确
- AUDIT.md 与 FinPredict/AUDIT.md 在 GitHub 正常渲染；图标正确显示

---

## [1.2] — 2026-10-22 · FinPredict 启动卡顿修复

### Fixed
- **启动白屏卡顿**（用户反馈"刚点开就卡着不动"）：根因为启动即联网拉取首次数据 5–15 秒且期间无任何反馈
  - `app.py` 增加后台预热线程，启动即预拉默认标的写入缓存 → API **0.61 秒秒回**
  - `app.js` 增加 `fetchWithTimeout`（AbortController：行情 30s / 预判 90s / 回测 240s）、全屏 loading 骨架、KPI 骨架占位、失败重试按钮、各页"计算中（约 X 秒）"提示
  - `style.css` 增加 boot-spinner / skeleton shimmer / retry-box / page-loading 样式

### Verification
- 修复版 exe 启动后 quote 0.61s 返回（641 行，最新 3663.0），进程稳定 273MB

---

## [1.1] — 2026-10-22 · 借鉴 qlib / TradingAgents / ai-hedge-fund 增强

### Added
- **42 个 Alpha158 风格因子**（借鉴微软 qlib）：动量 / 量价 / 技术（ADX+DI、KDJ）/ regime（波动率分位、EWMA 波动率）/ 季节（月份正余弦）/ 量价背离
- **isotonic 概率校准集成**（借鉴 Lopez de Prado AFML）：Logit + HistGBM + ExtraTrees + 时间衰减样本权重 + 选择性输出（|p−0.5|≥0.05）
- **多智能体委员会**（借鉴 TradingAgents / ai-hedge-fund 架构思想，独立实现）：技术分析师 / 基本面分析师 / 风险分析师 / 交易员 / 投资经理 5 角色分工 + 综合决策，端点 `/api/ai/committee`
- **[ENHANCEMENTS.md](FinPredict/ENHANCEMENTS.md)**：借鉴点 → 落地 → 验证 → 审查结论

### Verification
- 增强后 2000-2026 全程 52.3% → **56.53%**（追平"始终看多"56.7%），有信号日 **57.14%** @51.4% 覆盖（超基准）
- 委员会端点与 5 个提示词模板全部可用

---

## [1.0] — 2026-10-22 · FinPredict 首发

### Added
- **独立桌面应用**（双击 exe 即用，零环境依赖）：pywebview + 本地 HTTP API + ECharts 前端
- **多源实时数据**（免费无需 Key）：腾讯行情（A 股/港股/指数）+ yfinance（美股/商品/外汇，3 次重试）
- **多周期预判**：1 小时 / 3 小时 / 1 天 / 1 个月；walk-forward 回测 + 95% 残差分位区间（跨度越大越宽）
- **回测检验页**：方向准确率 / MAE / Skill / 策略净值 vs 买入持有 / 残差分布
- **AI 助手**：OpenAI 兼容接入 + 5 个免手写提示词模板（趋势分析 / 异常解读 / 因子归因 / 操作建议 / 回测解读）

### Verification
- A 股 000001.SS 实时 640 行日 K；回测 200 折方向准确率 54%（基准始终看多 56.5%）

---

## [0.4] — 2026-10-22 · FIN_Terminal AI 增强 + SEC EDGAR + 打包

### Added
- AI 增强预测模块 `models/ml_advanced.py`：42 因子 + 校准集成 + 选择性输出
- **SEC EDGAR 官方财务源**适配器（免费无需 Key，point-in-time 保留重述版本）
- PyInstaller onedir 打包（`FIN_Terminal.exe`）

### Fixed
- **1 项高危**：中文源 GBK 乱码 → 智能编码探测；**12 项中危**：去重顺序 / 时效权重 / LLM 重试 / YAML 解析 / 路径穿越 / 分析互斥 / 零值偏倚 / 调度日志等

### Verification
- 18/18 API 冒烟通过；增强后 52.3% → 56.53%

---

## [0.3] — 2026-10-21 · 新闻 + LLM + 优化器
官方新闻层、LLM 事件分析、区域/板块影响、价格×新闻融合、受限在线权重优化、前向影子验证、模型接入页。

## [0.2] — 2026-10-21 · 准确率审计
1949 留出 58.8%、1950–2026 年度 55.15%（vs 始终看多 56.74%）、区间校准（覆盖 99.36%）、高置信切片、稀有事件降权、开源项目评审、算法审查页。**98.7% 方向不可达判定在此确立。**

## [0.1] — 2026-10-21 · 核心终端
8 页面终端 + 27 组 Ridge/GBM 回测（全部负 skill，诚实保留）。
