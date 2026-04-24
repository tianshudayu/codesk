# 远程编程辅助输入层

这是一个仅支持 Windows 的远程编程辅助工具，当前仓库继续承担 GUI 远控路线：手机端可以连接电脑、锁定单个窗口、实时预览该窗口，并通过点按、拖拽、滚动和文本发送来操作它。默认推荐同一 Wi-Fi 直连，云中继仍可继续使用。

## 当前能力

- `Ctrl+Alt+L` 锁定当前前台窗口
- `Ctrl+Alt+U` 解除锁定
- 手机端输入文本后，通过剪贴板加 `Ctrl+V` 粘贴到锁定窗口
- 手机端实时预览已锁定窗口
- 手机端在预览上单击切换焦点、拖动完成选区或拖拽
- 手机端辅助滚动区可持续滚动锁定窗口
- 同一时间只允许一个手机会话接入，继续使用 6 位 PIN 校验
- 同时保留局域网直连与 relay 中继两种连接方式

## GUI 路线启动

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m app.main
```

如需启用本地 relay：

```powershell
python -m relay_service.main
```

桌面端启动后会自动打开本机管理页：

```text
http://127.0.0.1:8765/admin
```

## 使用流程

1. 启动桌面端，必要时再启动 relay。
2. 在管理页查看当前 PIN 和手机访问地址。
3. 手机打开管理页提供的地址并输入 PIN。
4. 电脑把目标应用切到前台，按 `Ctrl+Alt+L` 锁定。
5. 手机端开始预览、点击、拖拽、滚动，或直接发送文本。

## 运行目录

- 配置文件：`%LOCALAPPDATA%\RemoteCodingAssist\config\settings.json`
- 日志文件：`%LOCALAPPDATA%\RemoteCodingAssist\logs\app.log`

## 依赖与打包

当前版本额外依赖：

- `mss`
- `Pillow`

Windows 打包：

```powershell
.\scripts\build.ps1
```

打包产物位于 `dist\RemoteCodingAssist\`。

## 独立 MCP 路线

与本仓库分离的 MCP 会话原型已经单独放在：

```text
E:\codex-mcp-mobile
```

这个独立原型负责验证“手机管理 Codex 会话”路线，不操作桌面窗口。它当前包含：

- 本地 bridge 服务
- H5/PWA 手机端原型
- 配对码鉴权
- 工作区白名单
- 会话创建、续聊、取消、SSE 事件流

当前默认使用 `DemoCodexAdapter` 跑通交互链路，后续再替换成真实 Codex 适配器。

## 文档

- [生产测试手册](E:\远程桌面\docs\生产测试手册.md)
- [云中继部署说明](E:\远程桌面\docs\云中继部署.md)
