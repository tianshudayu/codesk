from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_base_dir()
CONFIG_PATH = BASE_DIR / "codesk-client.json"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ERROR_ALREADY_EXISTS = 183
_SINGLE_INSTANCE_HANDLE = None
SW_RESTORE = 9


def _is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _urlopen_with_local_bypass(request_or_url, *, timeout: float):
    target_url = request_or_url.full_url if isinstance(request_or_url, urllib.request.Request) else str(request_or_url)
    if _is_loopback_url(target_url):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request_or_url, timeout=timeout)
    return urllib.request.urlopen(request_or_url, timeout=timeout)


def acquire_single_instance(name: str) -> bool:
    global _SINGLE_INSTANCE_HANDLE
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
    if not handle:
        return True
    _SINGLE_INSTANCE_HANDLE = handle
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def focus_existing_window() -> bool:
    hwnd = ctypes.windll.user32.FindWindowW(None, "Codesk for Windows")
    if not hwnd:
        return False
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    return True


I18N = {
    "en": {
        "windowTitle": "Codesk for Windows",
        "language": "中",
        "theme": "Light",
        "pairEyebrow": "Pair code",
        "pairTitle": "Enter this code on your phone",
        "pairSubtitle": "Open Codesk on Android and type this 6-digit code.",
        "pairCodeUnavailable": "------",
        "pairExpiresPrefix": "Expires",
        "pairFooter": "Keep this app running. Codesk will switch to connected state automatically.",
        "refreshCode": "Refresh code",
        "disconnectPhone": "Disconnect phone",
        "connectedEyebrow": "Connected",
        "connectedTitle": "Phone connected",
        "connectedSubtitle": "This computer is linked. Keep Codex Desktop in front while sending.",
        "connectedFooter": "Bridge online starts automatically. Leave this app in the tray.",
        "currentPhone": "Connected phone",
        "unknownPhone": "Unknown phone",
        "cloud": "Cloud",
        "desktop": "Codex Desktop",
        "cli": "Codex CLI",
        "open": "Open",
        "closed": "Closed",
        "ready": "Ready",
        "missing": "Missing",
        "openCloud": "Open Codesk",
        "restartAgent": "Restart Agent",
        "openWindow": "Open Codesk for Windows",
        "quit": "Quit",
        "runtimeMissing": "Codesk runtime is missing. Reinstall Codesk for Windows.",
        "agentStarted": "Codesk agent started.",
        "desktopSyncStarted": "Desktop sync service started.",
        "repairCli": "Repair Codex CLI",
        "cliRepairStarted": "Started Codex CLI repair.",
        "cliRepairMissing": "setup_codex_cli.ps1 is missing.",
        "openCodexManual": "Open Codex Desktop manually, then return here.",
        "refreshFailed": "Unable to refresh pair code.",
        "disconnectConfirmTitle": "Disconnect this phone?",
        "disconnectConfirmBody": "Codesk will remove the current phone binding and show a fresh pair code.",
        "disconnectDone": "Phone disconnected. A new pair code is ready.",
    },
    "zh-CN": {
        "windowTitle": "Codesk for Windows",
        "language": "EN",
        "theme": "白",
        "pairEyebrow": "配对码",
        "pairTitle": "在手机端输入这 6 位配对码",
        "pairSubtitle": "打开 Codesk Android App，输入首页的 6 位配对码完成连接。",
        "pairCodeUnavailable": "------",
        "pairExpiresPrefix": "有效期至",
        "pairFooter": "保持当前窗口开启。手机连接成功后，这里会自动切换成已连接状态。",
        "refreshCode": "刷新配对码",
        "disconnectPhone": "断开手机",
        "connectedEyebrow": "已连接",
        "connectedTitle": "已连接手机",
        "connectedSubtitle": "这台电脑已经和手机连接。发送时请保持 Codex Desktop 在前台。",
        "connectedFooter": "bridge online 与桌面同步会自动启动，保持本应用在托盘运行即可。",
        "currentPhone": "已连接手机",
        "unknownPhone": "未命名手机",
        "cloud": "云端",
        "desktop": "Codex Desktop",
        "cli": "Codex CLI",
        "open": "已打开",
        "closed": "未打开",
        "ready": "已就绪",
        "missing": "未就绪",
        "openCloud": "打开 Codesk",
        "restartAgent": "重启 Agent",
        "openWindow": "打开 Codesk for Windows",
        "quit": "退出",
        "runtimeMissing": "Codesk 运行时缺失，请重新安装 Codesk for Windows。",
        "agentStarted": "Codesk agent 已启动。",
        "desktopSyncStarted": "桌面同步服务已启动。",
        "repairCli": "修复 Codex CLI",
        "cliRepairStarted": "已开始修复 Codex CLI。",
        "cliRepairMissing": "缺少 setup_codex_cli.ps1。",
        "openCodexManual": "请手动打开 Codex Desktop，然后再回到这里。",
        "refreshFailed": "刷新配对码失败。",
        "disconnectConfirmTitle": "断开当前手机？",
        "disconnectConfirmBody": "这会解除当前手机绑定，并立即显示新的配对码。",
        "disconnectDone": "当前手机已断开，新的配对码已经生成。",
    },
}


THEMES = {
    "dark": {
        "window": "#050508",
        "card": "#09090b",
        "line": "#27272a",
        "softLine": "rgba(255,255,255,0.08)",
        "text": "#ffffff",
        "muted": "#a1a1aa",
        "subtle": "#7b7b87",
        "accent": "#8a2be2",
        "accentText": "#ffffff",
        "ghostBg": "rgba(255,255,255,0.03)",
        "codeBg": "#111114",
        "codeText": "#faf5ff",
    },
    "light": {
        "window": "#f5f5f7",
        "card": "#ffffff",
        "line": "#ddddf0",
        "softLine": "rgba(16,16,20,0.08)",
        "text": "#111111",
        "muted": "#5b6170",
        "subtle": "#7b7f8d",
        "accent": "#7c3aed",
        "accentText": "#ffffff",
        "ghostBg": "#f4f4f8",
        "codeBg": "#f6f1ff",
        "codeText": "#35135e",
    },
}


def normalized_lang(value: str | None) -> str:
    return "zh-CN" if str(value or "").strip().lower().startswith("zh") else "en"


def normalized_theme(value: str | None) -> str:
    return "light" if str(value or "").strip().lower() == "light" else "dark"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(data)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def load_config() -> dict[str, Any]:
    return load_json(CONFIG_PATH)


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return BASE_DIR
    return BASE_DIR.parent.parent


def desktop_sync_executable(config: dict[str, Any]) -> Path | None:
    configured = str(config.get("desktopAutomationExe") or "").strip()
    if configured:
        candidate = Path(configured)
        if candidate.exists():
            return candidate
    bundled = BASE_DIR / "codesk-desktop-sync.exe"
    if bundled.exists():
        return bundled
    return None


def configured_automation_root(config: dict[str, Any]) -> Path | None:
    configured = str(config.get("desktopAutomationRoot") or "").strip()
    if configured:
        root = Path(configured)
        if (root / "app" / "main.py").exists():
            return root
    for candidate in (Path(r"E:\远程桌面"),):
        if (candidate / "app" / "main.py").exists():
            return candidate
    return None


def identity_path(config: dict[str, Any]) -> Path:
    configured = str(config.get("identityFile") or "").strip()
    if configured:
        return Path(configured)
    agent_root = Path(str(config.get("agentRoot") or "").strip())
    if agent_root:
        return agent_root / ".logs" / "cloud-agent.json"
    return BASE_DIR / "cloud-agent.json"


def load_agent_identity(config: dict[str, Any]) -> dict[str, Any]:
    return load_json(identity_path(config))


def save_agent_identity(config: dict[str, Any], payload: dict[str, Any]) -> None:
    save_json(identity_path(config), payload)


def codex_cli_ready() -> bool:
    codex_cmd = Path(os.environ.get("APPDATA", "")) / "npm" / "codex.cmd"
    return codex_cmd.exists()


def codex_desktop_open() -> bool:
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "(Get-Process Codex -ErrorAction SilentlyContinue | Measure-Object).Count",
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=startupinfo,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() not in ("", "0")
    except Exception:
        return False


def try_launch_codex_desktop() -> bool:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Codex" / "Codex.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Codex" / "Codex.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Codex" / "Codex.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            os.startfile(str(candidate))
            return True
    return False


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def desktop_automation_root(agent_root: Path | None) -> Path | None:
    if agent_root is None:
        return None
    sibling = agent_root.parent / "远程桌面"
    if (sibling / "app" / "main.py").exists():
        return sibling
    return None


def configured_automation_root(config: dict[str, Any]) -> Path | None:  # type: ignore[no-redef]
    configured = str(config.get("desktopAutomationRoot") or "").strip()
    if configured:
        root = Path(configured)
        if (root / "app" / "main.py").exists():
            return root
    for candidate in (repo_root() / "desktop_sync", Path(r"E:\远程桌面")):
        if (candidate / "app" / "main.py").exists():
            return candidate
    return None


def desktop_automation_root(agent_root: Path | None) -> Path | None:  # type: ignore[no-redef]
    if agent_root is None:
        return None
    for sibling in (agent_root.parent / "desktop_sync", agent_root.parent / "远程桌面"):
        if (sibling / "app" / "main.py").exists():
            return sibling
    return None


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CodeskWindows/2.0",
            **(headers or {}),
        },
        method="POST",
    )
    with _urlopen_with_local_bypass(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def desktop_admin_state(url: str = "http://127.0.0.1:8765/api/admin/state") -> dict[str, Any] | None:
    try:
        with _urlopen_with_local_bypass(url, timeout=2) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def process_running(image_name: str) -> bool:
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"(Get-Process {image_name} -ErrorAction SilentlyContinue | Measure-Object).Count",
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=startupinfo,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() not in ("", "0")
    except Exception:
        return False


def kill_process_tree(image_name: str) -> None:
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        subprocess.run(
            ["taskkill.exe", "/IM", image_name, "/F", "/T"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=startupinfo,
            timeout=10,
            check=False,
        )
    except Exception:
        return


def kill_source_agent_processes() -> None:
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        script = (
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -like '*-m bridge.agent_main*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=startupinfo,
            timeout=10,
            check=False,
        )
    except Exception:
        return


class TrayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._config = load_config()
        self._lang = normalized_lang(self._config.get("lang"))
        self._theme = normalized_theme(self._config.get("theme"))
        self._agent_process: subprocess.Popen[str] | subprocess.Popen[bytes] | None = None
        self._primary_action = "refresh_code"
        self._secondary_action = "restart_agent"
        self._pair_action = "refresh_code"
        self._cloud_offline_polls = 0
        self._last_restart_at: datetime | None = None

        self.setWindowTitle(self.t("windowTitle"))
        self.setMinimumWidth(470)

        shell = QVBoxLayout(self)
        shell.setContentsMargins(22, 22, 22, 22)
        shell.setSpacing(14)

        self.card = QFrame()
        self.card.setObjectName("card")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addStretch(1)
        self.lang_button = QPushButton()
        self.lang_button.setObjectName("ghost")
        self.lang_button.setMinimumHeight(34)
        self.lang_button.clicked.connect(self.toggle_language)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("ghost")
        self.theme_button.setMinimumHeight(34)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.bind_button = QPushButton()
        self.bind_button.setObjectName("ghost")
        self.bind_button.setMinimumHeight(34)
        self.bind_button.clicked.connect(self.handle_pair_action)
        controls.addWidget(self.lang_button)
        controls.addWidget(self.theme_button)
        controls.addWidget(self.bind_button)

        self.eyebrow = QLabel()
        self.eyebrow.setObjectName("eyebrow")
        self.title_label = QLabel()
        self.title_label.setObjectName("title")
        self.title_label.setWordWrap(True)
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("subtitle")
        self.subtitle_label.setWordWrap(True)

        self.code_frame = QFrame()
        self.code_frame.setObjectName("codeFrame")
        code_layout = QVBoxLayout(self.code_frame)
        code_layout.setContentsMargins(18, 18, 18, 18)
        code_layout.setSpacing(10)
        self.code_label = QLabel()
        self.code_label.setObjectName("codeLabel")
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.code_hint = QLabel()
        self.code_hint.setObjectName("footer")
        self.code_hint.setAlignment(Qt.AlignCenter)
        self.code_hint.setWordWrap(True)
        code_layout.addWidget(self.code_label)
        code_layout.addWidget(self.code_hint)

        self.meta_label = QLabel()
        self.meta_label.setObjectName("meta")
        self.meta_label.setWordWrap(True)
        self.footer_label = QLabel()
        self.footer_label.setObjectName("footer")
        self.footer_label.setWordWrap(True)

        self.primary_button = QPushButton()
        self.primary_button.setObjectName("primary")
        self.primary_button.clicked.connect(self.handle_primary_action)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.secondary_button = QPushButton()
        self.secondary_button.setObjectName("ghost")
        self.secondary_button.clicked.connect(self.handle_secondary_action)
        self.repair_button = QPushButton()
        self.repair_button.setObjectName("ghost")
        self.repair_button.clicked.connect(self.repair_codex_cli)
        button_row.addWidget(self.secondary_button)
        button_row.addWidget(self.repair_button)

        card_layout.addLayout(controls)
        card_layout.addWidget(self.eyebrow)
        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.subtitle_label)
        card_layout.addWidget(self.code_frame)
        card_layout.addWidget(self.meta_label)
        card_layout.addWidget(self.primary_button)
        card_layout.addLayout(button_row)
        card_layout.addWidget(self.footer_label)
        shell.addWidget(self.card)

        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, self)
        self.setWindowIcon(icon)
        self.tray.setToolTip(self.t("windowTitle"))
        menu = QMenu()
        open_action = QAction(self.t("openWindow"), self)
        open_action.triggered.connect(self.show_window)
        restart_action = QAction(self.t("restartAgent"), self)
        restart_action.triggered.connect(self.restart_agent)
        open_cloud_action = QAction(self.t("openCloud"), self)
        open_cloud_action.triggered.connect(self.open_cloud)
        quit_action = QAction(self.t("quit"), self)
        quit_action.triggered.connect(QApplication.instance().quit)
        for action in (open_action, restart_action, open_cloud_action, quit_action):
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.apply_theme()
        self.append_footer("")
        QTimer.singleShot(120, self.bootstrap_after_show)

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def t(self, key: str) -> str:
        return str(I18N.get(self._lang, I18N["en"]).get(key, key))

    def theme_tokens(self) -> dict[str, str]:
        return THEMES[self._theme]

    def apply_theme(self) -> None:
        tokens = self.theme_tokens()
        self.setStyleSheet(
            f"""
            QWidget {{
                background: {tokens['window']};
                color: {tokens['text']};
                font-family: "Segoe UI", "Microsoft YaHei";
            }}
            QFrame#card {{
                background: {tokens['card']};
                border: 1px solid {tokens['line']};
                border-radius: 24px;
            }}
            QFrame#codeFrame {{
                background: {tokens['codeBg']};
                border: 1px solid {tokens['softLine']};
                border-radius: 22px;
            }}
            QLabel#eyebrow {{
                color: {tokens['muted']};
                font-size: 12px;
                letter-spacing: 0.18em;
                text-transform: uppercase;
            }}
            QLabel#title {{
                font-size: 28px;
                font-weight: 700;
                color: {tokens['text']};
            }}
            QLabel#subtitle {{
                font-size: 15px;
                color: {tokens['muted']};
                line-height: 1.5;
            }}
            QLabel#meta {{
                font-size: 13px;
                color: {tokens['text']};
                line-height: 1.6;
            }}
            QLabel#footer {{
                font-size: 12px;
                color: {tokens['subtle']};
                line-height: 1.5;
            }}
            QLabel#codeLabel {{
                font-size: 42px;
                font-weight: 700;
                color: {tokens['codeText']};
                letter-spacing: 0.18em;
                font-family: Consolas, "JetBrains Mono", monospace;
            }}
            QPushButton {{
                min-height: 46px;
                padding: 0 18px;
                border-radius: 16px;
                border: 1px solid {tokens['line']};
                background: {tokens['ghostBg']};
                color: {tokens['text']};
            }}
            QPushButton#primary {{
                background: {tokens['accent']};
                color: {tokens['accentText']};
                border: 0;
                font-weight: 600;
            }}
            QPushButton#ghost {{
                background: {tokens['ghostBg']};
                color: {tokens['text']};
            }}
            """
        )
        self.theme_button.setText(self.t("theme"))
        self.lang_button.setText(self.t("language"))

    def toggle_language(self) -> None:
        self._lang = "zh-CN" if self._lang == "en" else "en"
        self._config["lang"] = self._lang
        save_json(CONFIG_PATH, self._config)
        self.setWindowTitle(self.t("windowTitle"))
        self.tray.setToolTip(self.t("windowTitle"))
        self.apply_theme()
        self.refresh_status()

    def toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        self._config["theme"] = self._theme
        save_json(CONFIG_PATH, self._config)
        self.apply_theme()
        self.refresh_status()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()

    def append_footer(self, message: str) -> None:
        self.footer_label.setText(message)

    def bootstrap_after_show(self) -> None:
        self.ensure_agent_running()
        self.refresh_status()
        if not self.timer.isActive():
            self.timer.start(5000)

    def source_agent_root(self) -> Path | None:
        agent_root = Path(str(self._config.get("agentRoot") or "").strip())
        pythonw = agent_root / ".venv" / "Scripts" / "pythonw.exe"
        python = agent_root / ".venv" / "Scripts" / "python.exe"
        launcher = pythonw if pythonw.exists() else python
        if launcher.exists() and (agent_root / "bridge" / "agent_main.py").exists():
            return agent_root
        return None

    def agent_command(self) -> list[str]:
        packaged_agent = BASE_DIR / "codesk-agent.exe"
        if packaged_agent.exists():
            return [str(packaged_agent)]
        source_root = self.source_agent_root()
        if source_root is not None:
            pythonw = source_root / ".venv" / "Scripts" / "pythonw.exe"
            python = source_root / ".venv" / "Scripts" / "python.exe"
            launcher = pythonw if pythonw.exists() else python
            return [str(launcher), "-m", "bridge.agent_main"]
        fallback_root = Path(str(self._config.get("agentRoot") or "").strip())
        pythonw = fallback_root / ".venv" / "Scripts" / "pythonw.exe"
        python = fallback_root / ".venv" / "Scripts" / "python.exe"
        launcher = pythonw if pythonw.exists() else python
        return [str(launcher), "-m", "bridge.agent_main"]

    def agent_workdir(self) -> Path:
        packaged_agent = BASE_DIR / "codesk-agent.exe"
        if packaged_agent.exists():
            return BASE_DIR
        source_root = self.source_agent_root()
        if source_root is not None:
            return source_root
        return Path(str(self._config.get("agentRoot") or "").strip())

    def agent_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["CODEX_CLOUD_URL"] = str(self._config.get("cloudUrl") or "")
        env["CODEX_CLOUD_ENABLED"] = "1"
        env["NO_PROXY"] = "127.0.0.1,localhost,::1"
        env["no_proxy"] = "127.0.0.1,localhost,::1"
        env["REMOTE_ASSIST_NO_BROWSER"] = "1"
        identity_file = str(self._config.get("identityFile") or "").strip()
        if identity_file:
            env["CODEX_CLOUD_AGENT_IDENTITY_FILE"] = identity_file
            identity_parent = Path(identity_file).expanduser().resolve().parent
            env["CODEX_RUNTIME_ROOT"] = str(identity_parent)
        automation_exe = desktop_sync_executable(self._config)
        automation_root = configured_automation_root(self._config)
        source_root = self.source_agent_root()
        if automation_root is None:
            automation_root = desktop_automation_root(source_root)
        if automation_root is None:
            configured_root = Path(str(self._config.get("agentRoot") or "").strip())
            automation_root = desktop_automation_root(configured_root)
        if automation_exe is not None:
            env["CODEX_DESKTOP_AUTOMATION_COMMAND"] = f"\"{automation_exe}\""
            env["CODEX_DESKTOP_AUTOMATION_CWD"] = str(automation_exe.parent)
            env["CODEX_DESKTOP_AUTOMATION_AUTOSTART"] = "1"
            env["CODEX_DESKTOP_AUTOMATION_URL"] = "http://127.0.0.1:8765"
        elif automation_root is not None:
            automation_python = automation_root / ".venv" / "Scripts" / "python.exe"
            launcher = automation_python if automation_python.exists() else Path(sys.executable)
            env["CODEX_DESKTOP_AUTOMATION_COMMAND"] = f"\"{launcher}\" -m app.main"
            env["CODEX_DESKTOP_AUTOMATION_CWD"] = str(automation_root)
            env["CODEX_DESKTOP_AUTOMATION_AUTOSTART"] = "1"
            env["CODEX_DESKTOP_AUTOMATION_URL"] = "http://127.0.0.1:8765"
        env["PYTHONUTF8"] = "1"
        return env

    def ensure_desktop_automation_running(self) -> None:
        if desktop_admin_state() is not None:
            return
        desktop_env = os.environ.copy()
        desktop_env["REMOTE_ASSIST_NO_BROWSER"] = "1"
        desktop_env["NO_PROXY"] = "127.0.0.1,localhost,::1"
        desktop_env["no_proxy"] = "127.0.0.1,localhost,::1"
        automation_exe = desktop_sync_executable(self._config)
        automation_root = configured_automation_root(self._config)
        source_root = self.source_agent_root()
        if automation_root is None:
            automation_root = desktop_automation_root(source_root)
        if automation_root is None:
            configured_root = Path(str(self._config.get("agentRoot") or "").strip())
            automation_root = desktop_automation_root(configured_root)
        if automation_exe is not None:
            subprocess.Popen(
                [str(automation_exe)],
                cwd=str(automation_exe.parent),
                creationflags=CREATE_NO_WINDOW,
                env=desktop_env,
            )
            self.append_footer(self.t("desktopSyncStarted"))
            return
        if automation_root is None:
            return
        automation_python = automation_root / ".venv" / "Scripts" / "python.exe"
        launcher = automation_python if automation_python.exists() else Path(sys.executable)
        subprocess.Popen(
            [str(launcher), "-m", "app.main"],
            cwd=str(automation_root),
            creationflags=CREATE_NO_WINDOW,
            env=desktop_env,
        )
        self.append_footer(self.t("desktopSyncStarted"))

    def ensure_agent_running(self) -> None:
        self.ensure_desktop_automation_running()
        if self._agent_process and self._agent_process.poll() is None:
            return
        kill_source_agent_processes()
        if process_running("codesk-agent"):
            return
        workdir = self.agent_workdir()
        command = self.agent_command()
        if not workdir.exists() or not Path(command[0]).exists():
            self.append_footer(self.t("runtimeMissing"))
            return
        self._agent_process = subprocess.Popen(
            command,
            cwd=str(workdir),
            env=self.agent_env(),
            creationflags=CREATE_NO_WINDOW,
        )
        self.append_footer(self.t("agentStarted"))

    def restart_agent(self, *, auto_recover: bool = False, refresh_after: bool = True) -> None:
        if self._agent_process and self._agent_process.poll() is None:
            with contextlib.suppress(Exception):
                self._agent_process.terminate()
        self._agent_process = None
        kill_process_tree("codesk-agent.exe")
        kill_source_agent_processes()
        self._cloud_offline_polls = 0
        self._last_restart_at = datetime.now().astimezone()
        self.ensure_agent_running()
        if auto_recover:
            self.append_footer("Codesk agent reconnecting…")
        if refresh_after:
            self.refresh_status()

    def repair_codex_cli(self) -> None:
        script = BASE_DIR / "setup_codex_cli.ps1"
        if not script.exists():
            self.append_footer(self.t("cliRepairMissing"))
            return
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=str(BASE_DIR),
            creationflags=CREATE_NO_WINDOW,
        )
        self.append_footer(self.t("cliRepairStarted"))

    def open_cloud(self) -> None:
        url = str(self._config.get("cloudUrl") or "").strip()
        if url:
            webbrowser.open(url)

    def request_pairing_state(self, *, force_refresh: bool) -> dict[str, Any]:
        config = self._config
        identity = load_agent_identity(config)
        now = datetime.now().astimezone()
        if not force_refresh:
            last_refreshed = parse_iso(identity.get("pairingRefreshedAt"))
            expires_at = parse_iso(identity.get("pairCodeExpiresAt") or identity.get("claimExpiresAt"))
            still_fresh = last_refreshed is not None and (now - last_refreshed) < timedelta(seconds=15)
            code_valid = expires_at is None or (expires_at - now) > timedelta(seconds=20)
            if still_fresh and code_valid:
                return identity
        cloud_url = str(config.get("cloudUrl") or "").strip().rstrip("/")
        device_id = str(identity.get("deviceId") or "").strip()
        agent_token = str(identity.get("agentToken") or "").strip()
        if not cloud_url or not device_id or not agent_token:
            return identity
        payload = post_json(
            f"{cloud_url}/api/pairing/code",
            {
                "deviceId": device_id,
                "agentToken": agent_token,
                "refresh": bool(force_refresh),
            },
        )
        identity["pairCode"] = payload.get("pairCode")
        identity["pairCodeExpiresAt"] = payload.get("expiresAt")
        identity["paired"] = bool(payload.get("paired"))
        identity["pairedClientName"] = payload.get("pairedClientName")
        identity["pairedClientPlatform"] = payload.get("pairedClientPlatform")
        identity["pairingRefreshedAt"] = now.isoformat()
        save_agent_identity(config, identity)
        return identity

    def disconnect_pairing(self) -> dict[str, Any]:
        config = self._config
        identity = load_agent_identity(config)
        cloud_url = str(config.get("cloudUrl") or "").strip().rstrip("/")
        device_id = str(identity.get("deviceId") or "").strip()
        agent_token = str(identity.get("agentToken") or "").strip()
        if not cloud_url or not device_id or not agent_token:
            return identity
        payload = post_json(
            f"{cloud_url}/api/pairing/disconnect",
            {
                "deviceId": device_id,
                "agentToken": agent_token,
            },
        )
        device_payload = payload.get("device") if isinstance(payload.get("device"), dict) else {}
        identity["pairCode"] = device_payload.get("pairCode")
        identity["pairCodeExpiresAt"] = device_payload.get("pairCodeExpiresAt")
        identity["paired"] = bool(device_payload.get("paired"))
        identity["pairedClientName"] = device_payload.get("pairedClientName")
        identity["pairedClientPlatform"] = device_payload.get("pairedClientPlatform")
        save_agent_identity(config, identity)
        return identity

    def format_pair_code(self, value: str | None) -> str:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())[:6]
        if len(digits) != 6:
            return self.t("pairCodeUnavailable")
        return f"{digits[:3]} {digits[3:]}"

    def fetch_agent_status(self, identity: dict[str, Any]) -> dict[str, Any] | None:
        cloud_url = str(self._config.get("cloudUrl") or "").strip().rstrip("/")
        device_id = str(identity.get("deviceId") or "").strip()
        agent_token = str(identity.get("agentToken") or "").strip()
        if not cloud_url or not device_id or not agent_token:
            return None
        try:
            return post_json(
                f"{cloud_url}/api/agent/status",
                {"deviceId": device_id, "agentToken": agent_token},
            )
        except Exception:
            return None

    def current_model(self) -> dict[str, Any]:
        identity = load_agent_identity(self._config)
        try:
            identity = self.request_pairing_state(force_refresh=False)
        except Exception as exc:
            self.append_footer(f"{self.t('refreshFailed')} {exc}")
        agent_status = self.fetch_agent_status(identity)
        device_payload = agent_status.get("device") if isinstance(agent_status, dict) and isinstance(agent_status.get("device"), dict) else {}
        cloud_connected = bool(agent_status.get("online")) if isinstance(agent_status, dict) else bool(identity.get("connected"))
        if device_payload:
            identity["connected"] = cloud_connected
            if isinstance(device_payload.get("pairCode"), str):
                identity["pairCode"] = device_payload.get("pairCode")
            if isinstance(device_payload.get("pairCodeExpiresAt"), str):
                identity["pairCodeExpiresAt"] = device_payload.get("pairCodeExpiresAt")
            identity["paired"] = bool(device_payload.get("paired"))
            if isinstance(device_payload.get("pairedClientName"), str):
                identity["pairedClientName"] = device_payload.get("pairedClientName")
            if isinstance(device_payload.get("pairedClientPlatform"), str):
                identity["pairedClientPlatform"] = device_payload.get("pairedClientPlatform")
            save_agent_identity(self._config, identity)
        desktop_state = desktop_admin_state()
        desktop_service_ready = desktop_state is not None
        cli_ready = codex_cli_ready()
        codex_open = codex_desktop_open()
        paired = bool(identity.get("paired") or identity.get("pairedClientName"))
        paired_name = str(identity.get("pairedClientName") or "").strip() or self.t("unknownPhone")
        pair_code = self.format_pair_code(identity.get("pairCode") or identity.get("claimCode"))
        expires_at = parse_iso(identity.get("pairCodeExpiresAt") or identity.get("claimExpiresAt"))
        if expires_at is not None:
            code_hint = f"{self.t('pairExpiresPrefix')} {expires_at.strftime('%H:%M')}"
        else:
            code_hint = ""

        cloud_label = str(self._config.get("cloudUrl") or "not set").strip()
        meta = "\n".join(
            [
                f"{self.t('cloud')}: {cloud_label}",
                f"{self.t('currentPhone')}: {paired_name if paired else self.t('pairCodeUnavailable')}",
                f"{self.t('desktop')}: {self.t('open') if codex_open else self.t('closed')}",
                f"{self.t('cli')}: {self.t('ready') if cli_ready else self.t('missing')}",
            ]
        )
        should_restart_agent = False
        if cloud_connected:
            self._cloud_offline_polls = 0
        else:
            self._cloud_offline_polls += 1
            now = datetime.now().astimezone()
            cooled_down = self._last_restart_at is None or (now - self._last_restart_at) >= timedelta(seconds=25)
            if self._cloud_offline_polls >= 2 and cooled_down:
                should_restart_agent = True

        if not paired:
            return {
                "eyebrow": self.t("pairEyebrow"),
                "title": self.t("pairTitle"),
                "subtitle": self.t("pairSubtitle"),
                "code": pair_code,
                "codeHint": code_hint,
                "meta": meta,
                "footer": self.t("pairFooter"),
                "primary": self.t("refreshCode"),
                "primaryAction": "refresh_code",
                "secondary": self.t("restartAgent"),
                "secondaryAction": "restart_agent",
                "pairActionLabel": self.t("refreshCode"),
                "pairAction": "refresh_code",
                "shouldRestartAgent": should_restart_agent,
            }

        status_suffix = []
        if not cloud_connected:
            status_suffix.append("cloud reconnecting")
        if not desktop_service_ready:
            status_suffix.append("desktop sync starting")
        if not cli_ready:
            status_suffix.append("CLI missing")
        if not codex_open:
            status_suffix.append("Codex closed")
        subtitle = self.t("connectedSubtitle")
        if status_suffix:
            subtitle = subtitle + " " + " · ".join(status_suffix)
        return {
            "eyebrow": self.t("connectedEyebrow"),
            "title": self.t("connectedTitle"),
            "subtitle": subtitle,
            "code": paired_name,
            "codeHint": self.t("connectedFooter"),
            "meta": meta,
            "footer": self.t("connectedFooter"),
            "primary": self.t("openCloud"),
            "primaryAction": "cloud",
            "secondary": self.t("restartAgent"),
            "secondaryAction": "restart_agent",
            "pairActionLabel": self.t("disconnectPhone"),
            "pairAction": "disconnect",
            "shouldRestartAgent": should_restart_agent,
        }

    def handle_pair_action(self) -> None:
        if self._pair_action == "disconnect":
            answer = QMessageBox.question(
                self,
                self.t("disconnectConfirmTitle"),
                self.t("disconnectConfirmBody"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                self.disconnect_pairing()
                self.append_footer(self.t("disconnectDone"))
            except Exception as exc:
                self.append_footer(f"{self.t('refreshFailed')} {exc}")
            self.refresh_status()
            return
        try:
            self.request_pairing_state(force_refresh=True)
        except Exception as exc:
            self.append_footer(f"{self.t('refreshFailed')} {exc}")
        self.refresh_status()

    def handle_primary_action(self) -> None:
        if self._primary_action == "refresh_code":
            self.handle_pair_action()
            return
        if self._primary_action == "cloud":
            self.open_cloud()
            return
        if self._primary_action == "open_codex":
            if not try_launch_codex_desktop():
                self.append_footer(self.t("openCodexManual"))
            return
        self.refresh_status()

    def handle_secondary_action(self) -> None:
        if self._secondary_action == "restart_agent":
            self.restart_agent()
            return
        self.refresh_status()

    def refresh_status(self) -> None:
        self._config = load_config()
        model = self.current_model()
        self._primary_action = str(model.get("primaryAction") or "refresh_code")
        self._secondary_action = str(model.get("secondaryAction") or "restart_agent")
        self._pair_action = str(model.get("pairAction") or "refresh_code")
        self.eyebrow.setText(str(model.get("eyebrow") or self.t("windowTitle")))
        self.title_label.setText(str(model.get("title") or self.t("windowTitle")))
        self.subtitle_label.setText(str(model.get("subtitle") or ""))
        self.code_label.setText(str(model.get("code") or self.t("pairCodeUnavailable")))
        self.code_hint.setText(str(model.get("codeHint") or ""))
        self.meta_label.setText(str(model.get("meta") or ""))
        self.footer_label.setText(str(model.get("footer") or ""))
        self.primary_button.setText(str(model.get("primary") or self.t("refreshCode")))
        self.secondary_button.setText(str(model.get("secondary") or self.t("restartAgent")))
        self.repair_button.setText(self.t("repairCli"))
        self.lang_button.setText(self.t("language"))
        self.theme_button.setText(self.t("theme"))
        self.bind_button.setText(str(model.get("pairActionLabel") or self.t("refreshCode")))
        if bool(model.get("shouldRestartAgent")):
            self.restart_agent(auto_recover=True, refresh_after=False)

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.show_window()


def main() -> int:
    if not acquire_single_instance("Local\\CodeskTray"):
        focus_existing_window()
        return 0
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = TrayWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
