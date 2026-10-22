# 研发流程与 Git 规范（DEVELOPMENT）

本项目（FIN_Terminal + FinPredict 双应用合集）的完整研发流程、分支策略与提交规范。

## 1. 仓库结构

```
（仓库根）
├── FinPredict/        # 应用二：实时联网预判（独立 exe，双击即用）
├── project/           # 应用一：FIN_Terminal 离线多市场终端（源码）
├── versions/          # FIN_Terminal 功能阶段快照
└── *.md               # 顶层文档（审计/决策/数据字典）
```

## 2. 分支策略

| 分支 | 用途 | 生命周期 |
|------|------|----------|
| `main` | 稳定发布分支，exe 从此打出 | 永久 |
| `feature/*` | 新功能开发（如 feature/ai-committee） | 合并后删除 |
| `fix/*` | 缺陷修复（如 fix/startup-freeze） | 合并后删除 |
| `docs/*` | 文档/翻译 | 合并后删除 |

单人开发采用 trunk-based：日常直接提交 `main`，较大改动开 feature 分支，合并前自测（compileall + node check + API 冒烟）。

## 3. 提交规范（Conventional Commits）

```
<type>(<scope>): <subject>

type:   feat | fix | docs | chore | refactor | test
scope:  ui | ai | model | data | server | docs
示例：
  feat(ai): multi-agent committee (5 roles + manager synthesis)
  fix(ui): startup freeze - prefetch cache + skeleton + timeouts
  docs: five-language README (zh/en/fr/ru/es)
```

## 4. 研发阶段时间线（与提交历史对应）

| 阶段 | 内容 | 关键提交 |
|------|------|----------|
| S1 | FIN_Terminal 离线终端：数据管道 + 10 页面 + 回测 | `feat: FIN_Terminal offline terminal core` |
| S2 | 准确率审计：98.7% 判定 + 区间校准 + 高置信切片 | `docs: accuracy audit (98.7% verdict)` |
| S3 | 新闻层 + LLM + 受限权重优化器 | `feat: news + llm + optimizer` |
| S4 | FinPredict 实时预判应用：多周期 + 回测 + AI 模板 | `feat: FinPredict real-time app` |
| S5 | 借鉴 qlib/TradingAgents/ai-hedge-fund 增强：42 因子 + 校准集成 + 委员会 | `feat(qlib)/feat(ai)` |
| S6 | 启动卡顿修复：预热缓存 + 骨架屏 + 超时重试 | `fix(ui): startup freeze` |
| S7 | 图标 + 五语 README + Git 研发流程 | `chore(ui): icon` / `docs: i18n` |

## 5. 质量门（每次合并前）

```powershell
py -m compileall -q FinPredict/src        # Python 语法
node --check FinPredict/src/finpredict/web/app.js   # 前端语法
py scripts/smoke_api.py                   # API 冒烟（如适用）
```

## 6. 版本发布

- 版本号：`v<主>.<次>.<补丁>`（见 VERSIONS.md）
- 发布物：dist_icon/FinPredict/FinPredict.exe（带图标最终版）
- 打包命令：`py -m PyInstaller finpredict.spec --noconfirm`
- 打包后在干净环境验证：启动 → API 秒回 → 四页面可用 → 无残留进程
