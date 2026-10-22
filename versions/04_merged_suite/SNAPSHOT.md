# SNAPSHOT 04 — 合并套件 / 图标 / 五语 / Git 流程（v1.3）

- 快照日期：2026-10-22
- 对应版本：FIN_Terminal v0.4 + FinPredict v1.3
- 性质：**策展式快照**（curated snapshot），非完整源码树；权威可运行版本始终是仓库根的 `project/` 与 `FinPredict/`

## 本阶段新增

| 类别 | 内容 |
|------|------|
| 新应用 | **FinPredict** 完整源码（实时联网预判，双击 exe 即用）：`src/finpredict/`（data/model/ai/server/app + web 前端） |
| 借鉴增强 | 42 个 Alpha158 风格因子（qlib）+ isotonic 校准集成与选择性输出（AFML）+ 5 角色多智能体委员会（TradingAgents / ai-hedge-fund 架构思想） |
| 应用图标 | `icon.ico`（256→16 多尺寸）+ `icon.png`（深蓝圆角 + 上涨 K 线 + 金色趋势箭头），已应用到 exe |
| 五语文档 | `README.md`（中）+ `README_EN.md` / `README_FR.md` / `README_RU.md` / `README_ES.md` |
| 审计文档 | `AUDIT.md`（总览页，含 5 张真实界面截图）+ `FinPredict/AUDIT.md`（独立审计页） |
| Git 流程 | `.gitignore` + `DEVELOPMENT.md`（分支策略/提交规范/质量门）+ `CHANGELOG.md` + `VERSIONS.md` + 11 次阶段化提交 + `v1.3` tag |
| 许可 | MIT `LICENSE` + 授权范围表（不含第三方逆向证据与市场数据） |
| 发布物 | `FinPredict_v1.3.exe`（30 MB，带图标）、`FIN_Terminal_v0.4.exe`（29 MB）、`finance-forecast-suite_v1.3.zip`（完整快照包） |
| 目录合并 | FinPredict 整合入主目录；清理约 1GB 重复构建产物，仅保留最终 `dist_icon` |

## 关键验证结果

| 项目 | 结果 |
|------|------|
| 增强模型方向准确率（2000-2026） | 52.3% → **56.53%**（追平始终看多 56.7%） |
| 有信号日准确率 | **57.14%** @ 51.4% 覆盖（超基准） |
| FinPredict 启动体验 | 首次数据 5–15s 卡顿 → 预热缓存后 **0.61s 秒回** |
| A 股实时数据 | 640 行日 K（腾讯行情），最新 3663.0 |
| exe 下载链路 | 302→200，字节数 30,157,785 / 29,104,707 正确 |
| 98.7% 方向准确率 | **不可达**（判定维持，见 `AUDIT.md`） |

## 本快照内文件

```
04_merged_suite/
├── SNAPSHOT.md
├── CHANGELOG.md              # 完整变更日志 v0.1 → v1.3
├── AUDIT.md                  # 准确率审计总览（含界面截图）
├── LICENSE                   # MIT + 授权范围
├── DEVELOPMENT.md            # 研发流程与 Git 规范
├── VERSIONS.md               # 版本记录
├── finpredict/               # FinPredict 源码快照
│   ├── src/finpredict/       # data / model / ai / server / app + web
│   ├── README*.md            # 五语 README
│   ├── AUDIT.md              # FinPredict 独立审计页
│   ├── ENHANCEMENTS.md       # 借鉴与增强说明
│   ├── finpredict.spec
│   ├── requirements.txt
│   └── icon.ico / icon.png
└── icons/                    # 图标副本
```

完整内容（含 90MB 行情数据与 419MB 逆向证据）见仓库根 `project/` 与 `FinPredict/`；归档包见 GitHub Release v1.3。
