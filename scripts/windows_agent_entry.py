from __future__ import annotations

import ctypes
import json
import os
import sys
from pathlib import Path

from bridge.agent_main import main

ERROR_ALREADY_EXISTS = 183
_SINGLE_INSTANCE_HANDLE = None


def acquire_single_instance(name: str) -> bool:
    global _SINGLE_INSTANCE_HANDLE
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
    if not handle:
        return True
    _SINGLE_INSTANCE_HANDLE = handle
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _load_config() -> dict[str, object]:
    config_path = _base_dir() / "codesk-client.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _configured_automation_root(config: dict[str, object]) -> Path | None:
    configured = str(config.get("desktopAutomationRoot") or "").strip()
    if configured:
        root = Path(configured)
        if (root / "app" / "main.py").exists():
            return root
    for fallback in (Path(r"E:\codex-mcp-mobile\desktop_sync"), Path(r"E:\远程桌面")):
        if (fallback / "app" / "main.py").exists():
            return fallback
    return None


def _configure_env_from_install() -> None:
    config = _load_config()
    cloud_url = str(config.get("cloudUrl") or "").strip()
    if cloud_url and not os.getenv("CODEX_CLOUD_URL"):
        os.environ["CODEX_CLOUD_URL"] = cloud_url
    os.environ.setdefault("CODEX_CLOUD_ENABLED", "1")
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
    os.environ.setdefault("no_proxy", "127.0.0.1,localhost,::1")
    os.environ.setdefault("REMOTE_ASSIST_NO_BROWSER", "1")

    identity_file = str(config.get("identityFile") or "").strip()
    if identity_file and not os.getenv("CODEX_CLOUD_AGENT_IDENTITY_FILE"):
        os.environ["CODEX_CLOUD_AGENT_IDENTITY_FILE"] = identity_file
        identity_parent = Path(identity_file).expanduser().resolve().parent
        os.environ.setdefault("CODEX_RUNTIME_ROOT", str(identity_parent))

    enrollment_token = str(config.get("enrollmentToken") or "").strip()
    if enrollment_token and not os.getenv("CODEX_CLOUD_ENROLLMENT_TOKEN"):
        os.environ["CODEX_CLOUD_ENROLLMENT_TOKEN"] = enrollment_token

    automation_exe = str(config.get("desktopAutomationExe") or "").strip()
    if automation_exe and Path(automation_exe).exists():
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_COMMAND", f"\"{automation_exe}\"")
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_CWD", str(Path(automation_exe).resolve().parent))
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_AUTOSTART", "1")
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_URL", "http://127.0.0.1:8765")
        os.environ.setdefault("PYTHONUTF8", "1")
        return

    automation_root = _configured_automation_root(config)
    if automation_root is None:
        agent_root = Path(str(config.get("agentRoot") or "").strip())
        for candidate in (agent_root.parent / "desktop_sync", agent_root.parent / "远程桌面"):
            if (candidate / "app" / "main.py").exists():
                automation_root = candidate
                break
    if automation_root is not None:
        launcher = automation_root / ".venv" / "Scripts" / "python.exe"
        if not launcher.exists():
            launcher = Path(sys.executable).resolve()
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_COMMAND", f"\"{launcher}\" -m app.main")
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_CWD", str(automation_root))
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_AUTOSTART", "1")
        os.environ.setdefault("CODEX_DESKTOP_AUTOMATION_URL", "http://127.0.0.1:8765")
    os.environ.setdefault("PYTHONUTF8", "1")


if __name__ == "__main__":
    if not acquire_single_instance("Local\\CodeskAgent"):
        raise SystemExit(0)
    _configure_env_from_install()
    raise SystemExit(main())
