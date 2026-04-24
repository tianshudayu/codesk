from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from threading import RLock

from .paths import AppPaths, ensure_runtime_dirs


DEFAULT_PORT = 8765


@dataclass(slots=True)
class PersistedConfig:
    port: int = DEFAULT_PORT
    pin_hash: str = ""
    pin_last_rotated_at: str = ""


class ConfigStore:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self._lock = RLock()
        ensure_runtime_dirs(paths)
        self._config = self._load()

    @property
    def config(self) -> PersistedConfig:
        with self._lock:
            return PersistedConfig(**asdict(self._config))

    @property
    def port(self) -> int:
        with self._lock:
            env_port = os.getenv("REMOTE_ASSIST_PORT")
            return int(env_port) if env_port else self._config.port

    def set_port(self, port: int) -> None:
        with self._lock:
            self._config.port = port
            self._save_unlocked()

    def set_pin(self, pin_hash: str, rotated_at: datetime) -> None:
        with self._lock:
            self._config.pin_hash = pin_hash
            self._config.pin_last_rotated_at = rotated_at.isoformat()
            self._save_unlocked()

    def pin_last_rotated_at(self) -> str:
        with self._lock:
            return self._config.pin_last_rotated_at

    def _load(self) -> PersistedConfig:
        if self.paths.config_file.exists():
            payload = json.loads(self.paths.config_file.read_text(encoding="utf-8"))
        else:
            payload = {}
        config = PersistedConfig(**{**asdict(PersistedConfig()), **payload})
        self.paths.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.config_file.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
        return config

    def _save_unlocked(self) -> None:
        self.paths.config_file.write_text(
            json.dumps(asdict(self._config), indent=2),
            encoding="utf-8",
        )
