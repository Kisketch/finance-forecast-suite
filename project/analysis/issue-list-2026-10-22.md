# 问题清单与改进计划（2026-10-22 审查）

- 审查范围：全部后端模块（data/analytics/models/news/ui）、前端（app.js/index.html/style.css）、依赖声明、打包交付链路
- 审查方法：代码逐文件人工审查 + 18 项 API 冒烟测试基线（全部通过）+ 既有审计报告复核
- 结论先行：工程质量中上（SQL 全参数化、LLM 输出严格裁剪、指标无未来函数），本次发现 **2 项高危、12 项中危、16 项低危**，以及 **8 项量化分析能力缺口**；全部高危与中危在本轮修复，低危择要修复。

## 一、高危（本轮必修）

| # | 位置 | 问题 | 修复方案 | 状态 |
|---|------|------|----------|------|
| H1 | news/sources.py `_parse_html`/`_article_details` | 中文官方源（上交所等）站点为 GBK/GB2312 编码，代码一律 `decode("utf-8","ignore")`，中文标题/摘要变乱码或被丢弃 | 智能编码探测：HTTP charset → HTML meta charset → utf-8 严格尝试 → gb18030 回退 | ✅ 已修复 |
| H2 | 交付链路 | 无 .exe 打包，用户须自建 Python 环境才能运行 | PyInstaller onedir 打包（含数据与资源），交付双击可运行的 FIN_Terminal.exe | ✅ 已完成 |

## 二、中危（本轮修复）

| # | 位置 | 问题 | 修复方案 | 状态 |
|---|------|------|----------|------|
| M1 | news/impact.py `_dedupe_events` | 注释称"保留证据权重最高的一条"，实际保留最新一条（排序发生在去重之后） | 先按 weight 降序排序再去重 | ✅ |
| M2 | news/impact.py `_age_hours` | 时间戳解析失败/未来时间返回 0 → recency=1.0 最大时效权重，垃圾数据反获最高权重 | 解析失败返回 +inf（时效权重≈0）；未来时间超 1 天按 +inf 处理 | ✅ |
| M3 | news/llm.py `_chat` | 重试循环形同虚设：超时/网络错误直接 break 不重试 | 对 URLError/timeout/5xx 增加一次带退避重试 | ✅ |
| M4 | ui/web/app.js | 页面渲染函数全部无 try/catch，任一 API 失败页面空白无提示；快速切换标的存在响应竞态 | switchPage 统一错误兜底 + 请求序号 token 防竞态 | ✅ |
| M5 | ui/web/app.js | 新闻标题 href 只转义引号，未校验 URL scheme，RSS 注入 `javascript:` 伪协议可执行脚本 | 渲染前校验 http/https 前缀，否则降级纯文本 | ✅ |
| M6 | data/fetch_market.py | 手写 YAML 解析器（正则）脆弱：键顺序/引号变化会静默丢标的；PyYAML 已在依赖中 | 改用 `yaml.safe_load` | ✅ |
| M7 | data/fetch_market.py | 快速失败只覆盖前 3 个标的；第 50 个标的故障时整轮拖 1 小时 | 全程序连续失败计数（≥8 连败中止） | ✅ |
| M8 | ui/server.py `_static` | 路径校验用字符串前缀比较，同级 `web-evil` 目录可绕过 | 改用 `Path.is_relative_to` | ✅ |
| M9 | news/analyzer.py | `analyze_pending` 无互斥：UI 手动分析与 15 分钟调度器可能同时处理同一批，浪费 LLM 调用 | 服务级分析锁 | ✅ |
| M10 | news/optimizer.py `_hit` | `(a>0)==(b>0)` 把 score=0 视作非正，零分样本系统性偏倚命中率 | `abs(score)<1e-9` 的样本不计入命中统计 | ✅ |
| M11 | news/service.py | 调度循环 `except: pass` 完全吞异常，后台静默失败无法诊断 | 记录到 stderr 日志 | ✅ |
| M12 | news/sources.py `_parse_rss` | 标准库 ElementTree 解析外部 XML，存在实体扩展（billion laughs）DoS 风险 | 解析前检测并剥离 `<!DOCTYPE`/`<!ENTITY` | ✅ |

## 三、低危（择要修复）

| # | 位置 | 问题 | 状态 |
|---|------|------|------|
| L1 | app.js `.disclaimer` 选择器命中预测页元素 | ✅ |
| L2 | app.js drawMarket N+1 请求（40 标的各发一次 /api/series） | ✅ 后端加批量端点 |
| L3 | app.js syncMarket 轮询无上限 + 成功后整页 reload | ✅ 加上限+局部刷新 |
| L4 | app.js 排序对 null 处理不一致（领跌可能是数据缺失者） | ✅ |
| L5 | app.js 字段直取无空值保护（.toFixed 抛错） | ✅ |
| L6 | app.js 新闻时间 UTC 未本地化 | ✅ |
| L7 | index.html echarts 同步加载阻塞首屏 | ✅ defer |
| L8 | impact.py min_relevance 默认 0.30 与 0.45 不一致 | ✅ 统一 0.45 |
| L9 | llm.py `_extract_json` 二次 loads 不在 try 内 | ✅ |
| L10 | llm.py 环境变量非法值崩溃 | ✅ 容错回退 |
| L11 | analyzer.py 死代码（未使用词表、relevance 覆盖） | ✅ 清理 |
| L12 | server.py 静态 text/* 无 charset 声明 | ✅ |
| L13 | indicators.py Sortino 口径非标准 | 保留（文档已注明口径） |
| L14 | optimizer.py apply_proposal 无频控 | ✅ 加 10 分钟频控 |
| L15 | store.py save_prediction 非原子 | 保留（单机并发概率低，风险可接受） |
| L16 | performance.py 相关矩阵 min_periods 未显式设置 | ✅ min_periods=60 |

## 四、量化分析能力缺口（本轮补充）

| # | 缺口 | 对照依据 | 补充方案 | 状态 |
|---|------|----------|----------|------|
| Q1 | 无基本面/财务数据源 | 《全球股市官方数据源手册》：SEC EDGAR 为唯一免费全量官方 API（10 req/s，无需 Key） | 新增 SEC EDGAR 适配器：XBRL 公司财务事实（营收/净利/EPS 等）+ 基本面面板页 | ✅ |
| Q2 | 分类概率未校准 | 学术标准做法（Platt/isotonic scaling） | 新增 CalibratedClassifierCV（isotonic）到 AI 预测模块 | ✅ |
| Q3 | 无 triple-barrier 标签 | Lopez de Prado《Advances in Financial ML》第2/3章 | 新增三重障碍标签（上/下障碍+最大持有期）作为可选目标 | ✅ |
| Q4 | 无波动率 regime 特征 | GARCH 类波动率聚集是日频收益最稳健的典型事实 | 新增波动率分位数 regime、EWMA 波动率、波动率比特征 | ✅ |
| Q5 | 缺 ADX/KDJ 等趋势强度指标 | TA-Lib/qlib 标准因子库均有 | 新增 ADX14、KDJ、EMA 距离、20日新高新低距离特征 | ✅ |
| Q6 | 训练样本等权 | regime 相关性：远期旧样本信息价值低 | 新增指数时间衰减样本权重（半衰期可选） | ✅ |
| Q7 | 未调研 2026 时序 SOTA | 时序基础模型（Chronos/TimesFM/Moirai）2024-2026 快速演进 | 完成 WebSearch 调研并写入 analysis/sota-review-2026.md | ✅ |
| Q8 | 无打包交付 | 用户要求 .exe | PyInstaller onedir + frozen 路径适配 | ✅ |

## 五、验证方式

- 每项修复后运行：`py -m compileall -q src`（语法）→ `node --check app.js`（前端）→ 18 项 API 冒烟 → 专项复测（编码/重试/竞态）
- 能力补充后：1948→1949 / 1950–2026 / 2000–2026 三组回测对照基线（58.8% / 55.15% / 52.3%）
- 打包后：干净目录启动 exe → API 18 项 → 页面截图 → 关闭无残留进程
