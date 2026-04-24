# Cloud Agent MVP

这是一版“手机网页 -> 云端控制面 -> Windows 本机 agent -> Codex Desktop”的最小可运行骨架。

## 组件

- `cloud_gateway.main`
  - 云端控制面
  - 负责邮箱登录、设备绑定、手机网页 API、agent 长连接、桌面控制代理
- `bridge.agent_main`
  - Windows 本机常驻 agent
  - 负责连接云端、同步本机会话、透传桌面自动化、自动拉起本机远控服务
- `E:\远程桌面\app.main`
  - 本机远控服务
  - 当前已支持自动接管前台 Codex 窗口，不再依赖手动组合键锁定

## 默认端口

- 云端控制面：`8892`
- 本机 bridge（旧本地模式，仍可单独运行）：`8890`
- 本机远控服务：`8765`

## 本地启动

### 1. 启动云端控制面

```powershell
python -m cloud_gateway.main
```

默认地址：

- [http://127.0.0.1:8892/](http://127.0.0.1:8892/)

### 2. 启动 Windows agent

```powershell
python -m bridge.agent_main
```

### 3. 本机远控服务

agent 会优先尝试自动拉起本机远控服务。

默认自动探测路径：

- `..\远程桌面\.venv\Scripts\python.exe -m app.main`

如果需要自定义启动命令：

```powershell
$env:CODEX_DESKTOP_AUTOMATION_COMMAND='E:\远程桌面\.venv\Scripts\python.exe -m app.main'
$env:CODEX_DESKTOP_AUTOMATION_CWD='E:\远程桌面'
```

## 关键环境变量

### 云端控制面

- `CODEX_CLOUD_PORT`
  - 默认 `8892`
- `CODEX_CLOUD_AUTH_MODE`
  - `dev` 或 `supabase`
  - 默认 `dev`
- `CODEX_CLOUD_SUPABASE_URL`
- `CODEX_CLOUD_SUPABASE_ANON_KEY`

### 本机 agent / bridge

- `CODEX_CLOUD_URL`
  - 默认 `http://127.0.0.1:8892`
- `CODEX_CLOUD_ENABLED`
  - 默认 `1`
- `CODEX_CLOUD_AGENT_IDENTITY_FILE`
  - agent 设备身份持久化路径

### 本机桌面自动化

- `CODEX_DESKTOP_AUTOMATION_URL`
  - 默认 `http://127.0.0.1:8765`
- `CODEX_DESKTOP_AUTOMATION_AUTOSTART`
  - 默认 `1`
- `CODEX_DESKTOP_AUTOMATION_COMMAND`
- `CODEX_DESKTOP_AUTOMATION_CWD`

## 当前约束

- 当前只支持 `Windows + Codex Desktop`
- 云端网页已支持：
  - 邮箱魔法链接登录
  - 设备绑定
  - 会话列表与消息发送
  - store-side 审批处理
  - 桌面预览 WebSocket 代理
  - 桌面待审批提示与预览入口
- 云端网页发送到现有会话时已启用 `requireDesktop`
  - 如果 Codex 不在前台或桌面不可控，会直接阻断
  - 不再悄悄降级到旧的 app-server 路径

## 备注

- 旧的本地 bridge 网页仍然保留，方便过渡和调试。
- `bridge.agent_main` 是新的“常驻代理”入口，更接近最终云端架构。
