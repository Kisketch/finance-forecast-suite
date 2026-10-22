# 金融分析预测应用合集

本文件夹包含**两个独立但互补**的金融分析预测桌面应用，均为研究教育用途，不构成投资建议。

## ⬇️ 下载（Release v1.3）

| 应用 | 文件 | 大小 | 说明 |
|------|------|------|------|
| **FinPredict** | [FinPredict_v1.3.exe](https://github.com/Kisketch/finpredict-suite/releases/download/v1.3/FinPredict_v1.3.exe) | 30 MB | 实时联网预判，双击即用，零环境依赖 |
| **FIN_Terminal** | [FIN_Terminal_v0.4.exe](https://github.com/Kisketch/finpredict-suite/releases/download/v1.3/FIN_Terminal_v0.4.exe) | 29 MB | 离线多市场研究终端 |

> Windows 可能提示"未知发布者"（未代码签名），选择"更多信息 → 仍要运行"即可。

## 目录结构

```
FIN_Terminal_Full_Package_2026-10-22/
├── README.md                  ← 本文件（总入口）
├── project/                   ← 应用一：FIN_Terminal 离线多市场终端（源码+数据）
├── versions/                  ← FIN_Terminal 功能阶段快照
├── intermediate_materials/    ← FIN_Terminal 中间实验产物
├── FinPredict/                ← 应用二：FinPredict 实时联网预判应用
│   ├── dist_fix/FinPredict/FinPredict.exe   ← 双击即用的独立 exe
│   ├── src/finpredict/        ← 源码（data/model/ai/server/app + web 前端）
│   ├── finpredict.spec        ← PyInstaller 打包配置
│   ├── ENHANCEMENTS.md        ← 借鉴 qlib/TradingAgents/ai-hedge-fund 的增强说明
│   └── README.md              ← FinPredict 详细说明
├── PACKAGE_README.md          ← FIN_Terminal 包说明
├── USAGE.md                   ← FIN_Terminal 使用指南
├── VERSION_NOTES.md           ← 版本演进
└── ...                        ← 其他审计/决策/数据字典文档
```

## 应用一：FIN_Terminal（离线多市场终端）

**定位**：本地多市场深度研究终端，含 97 标的、685,774 行历史数据（1927-2026）、官方新闻层、AI 增强预测、TradingView 逆向证据。

**特点**：
- 离线数据（90MB prices_long.csv 打包在内），无需联网即可回测
- 多市场（美股/港股/A 股/商品/房地产/能源）+ 10 个分析页面
- AI 增强模型（42 特征 + isotonic 校准集成 + 选择性输出，56.53% 方向准确率追平始终看多）
- SEC EDGAR 官方财务数据源 + 14 官方新闻源 + LLM 事件分析
- 诚实的 98.7% 审计（方向不可达，区间覆盖 99.36% 可达）

**运行**：
```powershell
cd project
py -m pip install -r requirements.txt
.\run.ps1                    # 启动桌面窗口
```
或运行打包好的 `project/dist/FIN_Terminal/FIN_Terminal.exe`

**入口文档**：`project/README.md`、`PACKAGE_README.md`、`USAGE.md`、`project/analysis/accuracy-audit.md`

## 应用二：FinPredict（实时联网独立预判）

**定位**：双击即用、无需配置任何环境的实时联网趋势预判应用。

**特点**：
- **真正独立**：双击 exe 即用，无需安装 Python 或任何依赖
- **实时联网**：腾讯行情（A 股/港股/指数，免费无 Key）+ yfinance（美股，带重试）
- **多周期预判**：1 小时 / 3 小时 / 1 天 / 1 个月，跨度越大区间越宽
- **历史回测**：walk-forward 滚动验证，方向准确率/MAE/Skill/策略净值
- **内置 AI**：OpenAI 兼容接入 + 5 个免手写提示词模板 + 多智能体委员会（借鉴 TradingAgents/ai-hedge-fund）
- **启动不卡**：后台预热缓存（秒回）+ 全屏 loading 骨架 + fetch 超时 + 失败重试

**运行**：双击 `FinPredict/dist_fix/FinPredict/FinPredict.exe`

**入口文档**：`FinPredict/README.md`、`FinPredict/ENHANCEMENTS.md`

## 两个应用的区别

| 维度 | FIN_Terminal | FinPredict |
|------|--------------|------------|
| 数据 | 离线 90MB 历史数据（打包内） | 实时联网（腾讯+yfinance） |
| 标的 | 97 个固定标的 | 任意输入（A 股/港股/美股/指数/商品） |
| 周期 | 日线（1/5/20 日） | 1h/3h/1d/1月 |
| 启动 | 需 Python 环境 或 用 exe | 双击 exe 即用，无环境依赖 |
| AI | LLM 事件分析 + 权重优化 | 5 模板 + 多智能体委员会 |
| 适合 | 深度研究/多市场对比/回测审计 | 实时看盘/快速预判/移动场景 |

## 诚实边界（两应用共同）

- **方向准确率 98.7% 不可达**（学术共识，日频方向预测上限约 54-58%）
- FIN_Terminal 增强模型：56.53% 全程（追平始终看多），有信号日 57.14%（超基准）
- FinPredict：54% 方向准确率（A 股日频），选择性输出在无把握时不下注
- 所有预判作情景参考，**不构成买卖建议，不执行交易**

## 快速开始

**想实时看盘/快速预判** → 双击 `FinPredict/dist_fix/FinPredict/FinPredict.exe`

**想深度研究/多市场回测** → `cd project; py -m pip install -r requirements.txt; .\run.ps1`

详见各应用子目录的 README。
