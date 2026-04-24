# Codesk (Codex 轻量手机控制台)

本项目的核心目标始终是作为 Codex 的单个轻量手机控制台。
除了支持在本地局域网（Windows端与手机端）进行直连互控，项目现已将中继控制面部署到了云端公网，形成了更广域的协同操作架构。

### 🌐 云端中继节点
部署信息已从 GitHub 上传包中移除，请在私有环境中自行配置。

## 架构拓扑

目前 Codesk 包含以下几个互为支点的核心模块：

### 1. 代理底层与互联支撑 (Core & Bridge)
- `bridge/` (涵盖核心 Codesk Agent)
  本地系统代理内核。原先仅用作 HTTP/WS 代理桥接，随着业务拓展，已成为真正的智能终端代理层。内建 `desktop_automation.py` 进行桌面自反馈流支持、`cloud_identity.py` 提供设备端向云端的鉴权等，以及核心适配器 `adapter.py` 对接桌面程序后端。
- `scripts/`
  工具带脚本层，用来进行项目构建包装与依赖分发。如包含了 Windows 安装包发行版和应用进程托盘等环境初始化命令组(`build_windows_installer.ps1` 和 `setup_codex_cli.ps1`)。

### 2. 终端侧矩阵 (End-User Clients)
- `clients/windows/`
  提供用于 Windows 常驻任务栏环境的原生客户端 (`codesk_tray.py`)。它采用 PySide6 构建原生容器视图，负责拉起/监控 Codex 核心进程并以二维码的形式向云端或本机局域网下发生效权限绑定。 
- `android_app/`
  独立开发发布的 Android Native + Web 适配端，承接了授权和远程控制逻辑，并且可以直接扫码加入桌面接管链路。

### 3. 公共网关中继 (Cloud / Gateway)
- `mcp_relay/`
  负责通过 WebSocket 收发处理局域网内或者是授权通过后的“轻指令分发通道”。以极低的数据驻留特征维持设备和指令面板心跳链接。
- `cloud_gateway/`
  为远距离和跨网络拓扑使用环境提供中心化 Cloud Gateway 处理，聚合设备流与多协议端信令转发。

---

## 初始依赖安装

对项目进行二次开发或本地启动前，你需激活 Python 环境：
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
# 安装底层依赖 (注意，某些客户端组件如 PySide6 可能需要通过系统级的 pip 覆盖或是通过脚本独立拉取)
python -m pip install -r requirements.txt
```

## 按端独立启动

代码库采用多进程/微服务架构独立设计，各端请根据使用需求单独进行拉起：

**A. 启动跨网（Relay）中继**
默认采用 8891 端口（支持设置 `CODEX_MCP_RELAY_PUBLIC_URL`以转发至公网）：
```powershell
python -m mcp_relay.main
```

**B. 启动本地守护代理 (Bridge)**
连接并适配 Codex 桌面的后端链路（注意：为了防止 WindowsApp 权限报错受限，可通过 `scripts\setup_codex_cli.ps1` 完成隔离后使用）。代理服务包含基于托盘及基础通道的入口：
```powershell
python -m bridge.main
# 当需要运行带有完整功能注册验证机制的 Agent 时:
# python -m bridge.agent_main
```

**C. 构建及运行 Codesk 原生客户端环境**
若需分发针对终端用户的应用程序或测试 Windows 环境，可利用构建脚本进行自动化打包 (使用 PyInstaller 编译)。
```powershell
.\scripts\build_windows_installer.ps1 -OutputDir "./release_output"
```
你将获取开箱即跑的 `Codesk-Setup.exe`，免安装繁琐依赖。

---

## 工程化优化展望

本项目目前在快速迭代与多维延伸期间，为防止长期的破窗效应并兼顾“简洁至上、可维护性”等第一性原理（KISS），我们提出以下推荐重构理念，以便于长期维护以及减少团队沟通屏障：

> **1. 现代化与原子级的依赖管理锁定**
> 目前依赖仅仅由分散的 `requirements.txt` 或构建脚本包揽管理，未生成锁存表 (`Lockfile`)。未来建议引入诸如 `uv` 或者 `Poetry` 构建 `pyproject.toml` 标准环境空间，这能实现各模块（前端 Web 代码生成/Python API及安装包拆分等）更严谨的库版本保护机制，一键还原开发图谱并加速 CI 时间。

> **2. 补齐静态分析及代码规则防线**
> Python 语言天生具有脆弱的弱运行时报错率。建议引入基于 Rust 的极速静态分析器 **Ruff**（统一承担 Black, isort, Flake8 职能）以及基于严格类型的 **Mypy** 对目前日益增多的模块建立持续审查和安全边界管控，防范未然导入以及未声明的方法引用等高频风险。

> **3. 构建标准的自动化 CI 管道 (CD集成)**
> 本仓库包含 Android 应用结构、可跨端多开脚本和 Windows Native 分发流。目前编译高度依赖手动本地在系统唤起 PowerShell 脚本 (`build_windows_installer.ps1`等)。建议全面引入 GitHub Actions 工作流：
> 当打下类似 `v1.x` 最新版本 tag 时自动唤起基于 Ubuntu VM（用于 APK Gradle 编译） 以及 Windows VM（用于 MSIX/EXE安装器打包生成）实现发布产物的自动化整合上传与更新说明记录。

> **4. 回收前端组件与重复静态碎片**
> 现发现网关及端网桥间存在了冗余度极高的 `static` 静态层逻辑，不利于在前后端逻辑上维护。如果此交互控制台后续功能愈发丰满，推荐将其剥离为一个单页应用 SPA（诸如独立 Vue或 React 单轨），并且将其编译产物的唯一实体通过预处理或者静态路由的统一注册手段被其他微服务下发和服用以达成 UI 的绝对一致。

