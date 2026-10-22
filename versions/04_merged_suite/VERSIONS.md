# 版本记录（VERSIONS）

## FIN_Terminal（离线多市场终端）

| 版本 | 日期 | 内容 |
|------|------|------|
| v0.1 | 2026-10-21 | 核心终端：8 页面 + 27 组 Ridge/GBM 回测（全部负 skill，诚实保留） |
| v0.2 | 2026-10-21 | 准确率审计：1949 留出 58.8%、98.7% 方向不可达判定、区间覆盖 99.36% 可达、稀有事件降权 |
| v0.3 | 2026-10-21 | 官方新闻层 + LLM 事件分析 + 受限在线权重优化 + 前向影子验证 |
| v0.4 | 2026-10-22 | AI 增强预测（42 因子+校准集成，52.3%→56.53%）+ SEC EDGAR 源 + 修复 1 高危 12 中危 + PyInstaller 打包 |

## FinPredict（实时联网预判）

| 版本 | 日期 | 内容 |
|------|------|------|
| v1.0 | 2026-10-22 | 首发独立 exe：多周期预判（1h/3h/1d/1月）+ walk-forward 回测 + AI 接入 + 5 提示词模板；多源数据（腾讯+yfinance） |
| v1.1 | 2026-10-22 | 借鉴增强：42 Alpha158 因子（qlib）+ isotonic 校准集成 + 选择性输出（AFML）+ 多智能体委员会（TradingAgents/ai-hedge-fund） |
| v1.2 | 2026-10-22 | 体验修复：启动预热缓存（15s→0.6s 秒回）+ 全屏骨架屏 + fetch 超时 + 失败重试 |
| v1.3 | 2026-10-22 | 应用图标（K线+趋势箭头）+ 五语 README（中/英/法/俄/西）+ Git 研发流程 |

## 发布物

| 文件 | 说明 |
|------|------|
| `FinPredict/dist_icon/FinPredict/FinPredict.exe` | FinPredict 最终版（v1.3，带图标） |
| `project/dist/FIN_Terminal/FIN_Terminal.exe` | FIN_Terminal 最终版（v0.4） |
