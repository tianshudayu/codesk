from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path


def runtime_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def runtime_payload_dir() -> Path:
    return runtime_root() / "payload"


def runtime_config_path() -> Path:
    return runtime_root() / "installer-config.json"


def powershell_script(command: str) -> list[str]:
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]


def creation_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def run_hidden(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )


def create_shortcut(shortcut_path: Path, target_path: Path, working_directory: Path) -> None:
    shortcut = str(shortcut_path).replace("'", "''")
    target = str(target_path).replace("'", "''")
    workdir = str(working_directory).replace("'", "''")
    command = (
        "$WshShell = New-Object -ComObject WScript.Shell;"
        f"$Shortcut = $WshShell.CreateShortcut('{shortcut}');"
        f"$Shortcut.TargetPath = '{target}';"
        f"$Shortcut.WorkingDirectory = '{workdir}';"
        "$Shortcut.Save();"
    )
    subprocess.run(powershell_script(command), check=True, creationflags=creation_flags())


def show_message(title: str, message: str, style: int = 0) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, title, style)


def stop_codesk_processes() -> None:
    for image_name in ("codesk-tray.exe", "codesk-agent.exe", "codesk-desktop-sync.exe"):
        run_hidden(["taskkill", "/IM", image_name, "/F", "/T"], check=False)
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*codex.cmd app-server*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    subprocess.run(
        powershell_script(command),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )


def detect_desktop_automation_root() -> str | None:
    candidates = [
        Path(r"E:\codex-mcp-mobile\desktop_sync"),
        Path(r"E:\远程桌面"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Codesk" / "desktop-automation",
    ]
    for candidate in candidates:
        if (candidate / "app" / "main.py").exists():
            return str(candidate)
    return None


def copy_with_retry(source: Path, target: Path, retries: int = 20, delay_seconds: float = 0.5) -> None:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            shutil.copy2(source, target)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay_seconds)
    if last_error:
        raise RuntimeError(
            f"Unable to update {target.name} because Codesk is still running. "
            "Please close Codesk for Windows and try again."
        ) from last_error


def download_payload(config: dict[str, object]) -> Path:
    cloud_url = str(config.get("cloudUrl") or "").strip().rstrip("/")
    if not cloud_url:
        raise RuntimeError("Installer configuration is missing cloud URL.")
    temp_root = Path(tempfile.mkdtemp(prefix="codesk-installer-"))
    archive_path = temp_root / "payload.zip"
    payload_url = f"{cloud_url}/api/downloads/windows-client/payload"
    with urllib.request.urlopen(payload_url, timeout=120) as response, archive_path.open("wb") as target:
        shutil.copyfileobj(response, target)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(temp_root)
    return temp_root


def install() -> None:
    config_payload = runtime_config_path()
    if not config_payload.exists():
        raise RuntimeError("Installer configuration is missing.")

    config = json.loads(config_payload.read_text(encoding="utf-8-sig"))
    payload_root = runtime_root()
    temp_payload_root: Path | None = None
    bundled_payload = runtime_payload_dir()
    if not bundled_payload.exists():
        temp_payload_root = download_payload(config)
        payload_root = temp_payload_root
    payload_dir = payload_root
    client_payload = payload_dir / "client"
    if not client_payload.exists():
        raise RuntimeError("Installer payload is incomplete.")
    install_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Codesk"
    client_root = install_root / "client"
    agent_root = install_root / "agent"
    identity_file = agent_root / "cloud-agent.json"
    install_root.mkdir(parents=True, exist_ok=True)
    client_root.mkdir(parents=True, exist_ok=True)
    agent_root.mkdir(parents=True, exist_ok=True)

    stop_codesk_processes()
    time.sleep(1.0)

    for item in client_payload.iterdir():
        target = client_root / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            copy_with_retry(item, target)

    client_config = {
        "cloudUrl": config.get("cloudUrl", ""),
        "agentRoot": str(agent_root),
        "identityFile": str(identity_file),
        "installedAt": datetime.now().astimezone().isoformat(),
    }
    desktop_sync_exe = client_root / "codesk-desktop-sync.exe"
    if desktop_sync_exe.exists():
        client_config["desktopAutomationExe"] = str(desktop_sync_exe)
    else:
        desktop_automation_root = detect_desktop_automation_root()
        if desktop_automation_root:
            client_config["desktopAutomationRoot"] = desktop_automation_root
    (client_root / "codesk-client.json").write_text(
        json.dumps(client_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    tray_exe = client_root / "codesk-tray.exe"
    if not tray_exe.exists():
        raise RuntimeError("codesk-tray.exe is missing from the installer payload.")

    desktop_shortcut = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / "Codesk for Windows.lnk"
    startup_shortcut = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "Codesk Tray.lnk"
    )
    create_shortcut(desktop_shortcut, tray_exe, client_root)
    create_shortcut(startup_shortcut, tray_exe, client_root)

    subprocess.Popen([str(tray_exe)], cwd=str(client_root), creationflags=creation_flags())
    show_message(
        "Codesk for Windows",
        "Codesk for Windows has been installed. Open the app and enter the 6-digit pair code on your phone.",
    )
    if temp_payload_root is not None:
        shutil.rmtree(temp_payload_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        install()
    except Exception as exc:  # pragma: no cover - runtime installer path
        show_message("Codesk installer", str(exc), 0x10)
        raise
