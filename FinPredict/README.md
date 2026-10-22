# FinPredict · 实时金融趋势预判桌面应用

**语言 / Language / Langue / Язык / Idioma**：[中文](README.md) · [English](README_EN.md) · [Français](README_FR.md) · [Русский](README_RU.md) · [Español](README_ES.md)

![FinPredict 图标](src/finpredict/web/icon.png)

一个**双击即用**的 Windows 桌面应用：实时联网获取官方市场数据，多时间维度趋势预判，历史回测检验，内置 AI 多智能体分析。无需安装 Python 或任何依赖。

![实时行情界面](docs/screenshot_quote.png)

## ⬇️ 下载（Release v1.3）

| 文件 | 大小 | 说明 |
|------|------|------|
| [FinPredict_v1.3.exe](https://github.com/Kisketch/finpredict-suite/releases/download/v1.3/FinPredict_v1.3.exe) | 30 MB | 独立版，双击即用，零环境依赖 |
| [FIN_Terminal_v0.4.exe](https://github.com/Kisketch/finpredict-suite/releases/download/v1.3/FIN_Terminal_v0.4.exe) | 29 MB | 姊妹应用 FIN_Terminal（离线多市场终端） |

> 下载后 Windows 可能提示"未知发布者"（未做代码签名），选择"更多信息 → 仍要运行"即可。

## ✨ 核心功能

| 页面 | 能力 |
|------|------|
| 📈 实时行情 | 联网拉取 K 线，支持 1 小时 / 3 小时 / 1 天 / 1 个月四周期；K 线 + MA + 布林 + RSI + MACD + 成交量 |
| 🔮 趋势预判 | 多周期方向 + 中位价 + 95% 置信区间（跨度越大区间越宽）；42 因子 + 概率校准集成 |
| 🧪 回测检验 | walk-forward 滚动验证：方向准确率 / MAE / Skill / 策略净值 vs 买入持有 |
| 🤖 AI 助手 | OpenAI 兼容接入；5 个免手写提示词模板；**多智能体委员会**（技术/基本面/风险/交易员/投资经理五角色分工+综合决策，借鉴 TradingAgents） |

## 🚀 快速开始

**方式一（推荐）**：解压后双击 `FinPredict.exe`——零环境依赖，启动即预拉数据（秒回不卡顿）。

**方式二（源码）**：
```powershell
py -m pip install -r requirements.txt
py -m finpredict.app
```

**输入标的示例**：`000001.SS`（上证）· `0700.HK`（腾讯控股）· `AAPL`（苹果）· `^GSPC`（标普500）· `CL=F`（原油）

## 📡 数据源（免费、无需 API Key）

| 市场 | 主源 | 备用 |
|------|------|------|
| A 股 (.SS/.SZ)、港股 (.HK)、恒指 | 腾讯行情 | — |
| 美股、美指数、商品、外汇 | yfinance（3 次重试） | Yahoo 限流时友好降级 |

## 🤖 AI 接入（免手写提示词）

在「AI 助手」页填写任意 OpenAI 兼容端点即可：

| 端点 | Base URL | Model |
|------|----------|-------|
| Ollama（本地） | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |

**提示词模板**（选择后自动填充当前行情/预判/回测数据）：趋势分析 · 异常解读 · 因子归因 · 操作建议 · 回测解读

**委员会模式**：一键运行 5 角色多智能体分析——技术分析师、基本面分析师、风险分析师、交易员各自独立研判，投资经理综合权衡给出最终结论（借鉴 TradingAgents / ai-hedge-fund 架构思想，独立实现）。

## 🧮 预判方法

- **特征**：42 个 Alpha158 风格因子（动量/量价/技术/regime/季节，借鉴微软 qlib）
- **模型**：Ridge + HistGradientBoosting 回归集成；方向概率经 isotonic 校准（Logit+HistGBM+ExtraTrees），时间衰减样本权重
- **验证**：扩展窗口 walk-forward，无未来函数；区间为滚动残差分位映射
- **借鉴**：qlib（因子工程）· TradingAgents（多智能体委员会）· ai-hedge-fund（多风格视角）· Lopez de Prado AFML（校准+选择性输出）——均只借鉴架构思想，未复制代码

## ⚠️ 诚实边界

方向准确率 **98.7% 在样本外不可达**（学术共识，日频方向预测上限约 54-58%）。本应用预判作情景参考，不构成买卖建议，不执行交易。

## 📦 打包

```powershell
py -m pip install pyinstaller
py -m PyInstaller finpredict.spec --noconfirm
```

## 📄 许可

研究教育用途。数据版权归原始提供方（腾讯/yfinance），请遵守其条款。

---

**相关项目**：本仓库的 `../project/` 目录包含姊妹应用 **FIN_Terminal**（离线多市场深度研究终端：97 标的、68.5 万行历史数据、SEC EDGAR 官方财务源、98.7% 准确率审计），详见根目录 [README.md](../README.md)。
