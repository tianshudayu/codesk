from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .config_store import ConfigStore


PBKDF2_ITERATIONS = 120_000
MAX_FAILURES = 5
WINDOW_SECONDS = 60
LOCKOUT_SECONDS = 30


@dataclass(slots=True)
class PinVerification:
    ok: bool
    code: str | None = None
    message: str | None = None


class PinManager:
    def __init__(self, config_store: ConfigStore) -> None:
        self._config_store = config_store
        self._lock = RLock()
        self._current_pin = ""
        self._pin_hash = config_store.config.pin_hash
        self._pin_last_rotated_at = config_store.pin_last_rotated_at()
        self._failures: dict[str, list[float]] = {}
        self.rotate_pin()

    @property
    def current_pin(self) -> str:
        with self._lock:
            return self._current_pin

    @property
    def pin_last_rotated_at(self) -> str:
        with self._lock:
            return self._pin_last_rotated_at

    def rotate_pin(self) -> str:
        with self._lock:
            pin = f"{secrets.randbelow(900000) + 100000:06d}"
            rotated_at = datetime.now().astimezone()
            pin_hash = _hash_pin(pin)
            self._current_pin = pin
            self._pin_hash = pin_hash
            self._pin_last_rotated_at = rotated_at.isoformat()
            self._failures.clear()
            self._config_store.set_pin(pin_hash, rotated_at)
            return pin

    def verify_pin(self, client_host: str, pin: str) -> PinVerification:
        with self._lock:
            now = time.time()
            attempts = self._failures.setdefault(client_host, [])
            attempts[:] = [item for item in attempts if now - item <= WINDOW_SECONDS]
            if len(attempts) >= MAX_FAILURES:
                blocked_for = LOCKOUT_SECONDS - int(now - attempts[0])
                if blocked_for > 0:
                    return PinVerification(
                        False,
                        "pin_throttled",
                        f"PIN 输入错误次数过多，请约 {blocked_for} 秒后再试。",
                    )
                attempts.clear()
            if not pin or not _verify_pin(pin, self._pin_hash):
                attempts.append(now)
                return PinVerification(False, "invalid_pin", "会话 PIN 无效。")
            attempts.clear()
            return PinVerification(True)


def _hash_pin(pin: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _verify_pin(pin: str, encoded_hash: str) -> bool:
    try:
        _, iteration_text, salt_hex, digest_hex = encoded_hash.split("$", 3)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iteration_text),
    )
    return secrets.compare_digest(digest.hex(), digest_hex)
