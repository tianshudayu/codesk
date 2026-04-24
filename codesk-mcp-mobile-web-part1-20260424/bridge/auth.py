from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class AuthResult:
    ok: bool
    code: str | None = None
    message: str | None = None
    token: str | None = None


class PairingManager:
    def __init__(self, token_ttl_hours: int = 12) -> None:
        self._lock = threading.RLock()
        self._current_code = self._generate_code()
        self._tokens: dict[str, datetime] = {}
        self._token_ttl = timedelta(hours=token_ttl_hours)

    @property
    def current_code(self) -> str:
        with self._lock:
            return self._current_code

    def rotate_code(self) -> str:
        with self._lock:
            self._current_code = self._generate_code()
            self._tokens.clear()
            return self._current_code

    def issue_token(self, code: str) -> AuthResult:
        with self._lock:
            if code != self._current_code:
                return AuthResult(False, "invalid_pair_code", "配对码无效。")
            token = secrets.token_urlsafe(24)
            self._tokens[token] = datetime.now().astimezone() + self._token_ttl
            return AuthResult(True, token=token)

    def verify_token(self, token: str) -> bool:
        with self._lock:
            now = datetime.now().astimezone()
            expired = [item for item, expires_at in self._tokens.items() if expires_at <= now]
            for item in expired:
                self._tokens.pop(item, None)
            expires_at = self._tokens.get(token)
            return expires_at is not None and expires_at > now

    @staticmethod
    def _generate_code() -> str:
        return f"{secrets.randbelow(1000000):06d}"
