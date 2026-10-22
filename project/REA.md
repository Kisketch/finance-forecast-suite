# REA 配置状态与使用说明

日期：2026-10-21

## 1. 当前状态

| 项目 | 状态 | 证据 |
|---|---|---|
| REA CLI | 已安装，`rea 6.7.0` | `npm install -g rea-agents`，`rea --version` |
| REA MCP（OpenCode） | **已注册** | `C:\Users\Lgnatius\.config\opencode\opencode.jsonc` 第 29–35 行：本地 `rea.mjs mcp` |
| 本会话可用 rea 工具 | 207 个 | OpenCode MCP 工具目录 |
| Node.js | 24.19.0 | `rea doctor` |
| 宿主 | win32 x64 | `rea doctor` |
| Ghidra | **未安装** | `GHIDRA_INSTALL_DIR` 未设置 |
| Hopper | 未安装 | `HOPPER_LAUNCHER_PATH` 未设置 |
| IDA | 未配置 | `REA_IDA_MCP_CONFIG` 未设置 |
| JADX（Android） | 未配置 | `REA_JADX_MCP_JAR` 未设置 |
| Agent skill | 需更新（`config_drift`） | `rea doctor` |

结论：**rea 已经配置可用**，但只具备“无需原生引擎”的能力（JavaScript/Electron、.NET 静态、桌面安装盘点、SQLite、Go/Rust 元数据等）。要做原生二进制反编译，需要额外安装 Ghidra 12.1.x + JDK 21+，或配置 IDA。

## 2. 本次实际使用

```powershell
# 获取 Electron 目标（winget 处理 CDN 鉴权）
winget download --id TradingView.TradingViewDesktop --download-directory .\reverse\tradingview

# 解包 MSIX（本质 ZIP）
Copy-Item .\reverse\tradingview\*.msix .\reverse\tradingview\tv.zip
Expand-Archive .\reverse\tradingview\tv.zip .\reverse\tradingview\extracted

# 静态分析 app.asar
rea analyze-javascript-application .\reverse\tradingview\extracted\resources\app.asar `
  --format json --max-heap-mb 2048 --analysis-timeout-ms 600000 > .\reverse\tradingview\rea-analysis.json
```

产物：

- `reverse/tradingview/rea-analysis.json`（419.1 MB）
- `reverse/tradingview/summary.json`
- `reverse/tradingview/app_facts.json`
- `analysis/reverse/tradingview-reverse-report.md`

## 3. 如需原生二进制分析

推荐 Ghidra（免费）：

1. 安装 JDK 21+（64 位）；
2. 下载 Ghidra 12.1.x 并解压；
3. 设置环境变量：

```powershell
[Environment]::SetEnvironmentVariable("GHIDRA_INSTALL_DIR", "C:\Tools\ghidra_12.1.4_PUBLIC", "User")
```

4. 验证：

```powershell
rea doctor
rea capabilities
```

5. 用法：

```powershell
rea inspect .\target.exe --provider ghidra --json
rea search .\target.exe entry --kind procedures --provider ghidra --json
rea function .\target.exe <procedure> --provider ghidra --json
```

Windows 支持边界：Ghidra 在 Windows 上仍是实验性支持（P0，只读），支持 x86/x64 PE；大型二进制可提高 `REA_GHIDRA_STARTUP_TIMEOUT_MS`。

## 4. 更新 Agent skill

`rea doctor` 显示 skill 身份过期。可执行：

```powershell
rea setup --yes --client opencode
```

该命令会备份并更新 `~/.config/opencode/opencode.jsonc` 中的 REA MCP 注册与 skill。若当前会话已能调用 rea 工具，可不执行；执行后建议重启 OpenCode。

## 5. 备注

- `morlu/rea` 是笔误，正确仓库是 `morluto/rea`；`git clone` 因仓库较大曾超时，CLI 通过 npm 安装即可，不需要本地克隆。
- `rea` 的 JS 分析是**静态**的：不会执行目标代码；结论需标注“静态证据/未运行时验证”。
