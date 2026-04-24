from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .version import APP_NAME


@dataclass(frozen=True, slots=True)
class AppPaths:
    storage_dir: Path
    config_dir: Path
    logs_dir: Path
    config_file: Path
    log_file: Path
    bundle_root: Path
    static_dir: Path


def resolve_runtime_paths() -> AppPaths:
    local_appdata = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    storage_dir = local_appdata / APP_NAME
    config_dir = storage_dir / "config"
    logs_dir = storage_dir / "logs"
    config_file = config_dir / "settings.json"
    log_file = logs_dir / "app.log"
    bundle_root = _resolve_bundle_root()
    static_dir = bundle_root / "app" / "static"
    return AppPaths(
        storage_dir=storage_dir,
        config_dir=config_dir,
        logs_dir=logs_dir,
        config_file=config_file,
        log_file=log_file,
        bundle_root=bundle_root,
        static_dir=static_dir,
    )


def ensure_runtime_dirs(paths: AppPaths) -> None:
    paths.storage_dir.mkdir(parents=True, exist_ok=True)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)


def _resolve_bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent
