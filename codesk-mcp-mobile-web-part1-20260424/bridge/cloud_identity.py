from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _default_identity_path() -> Path:
    configured = os.getenv("CODEX_CLOUD_AGENT_IDENTITY_FILE", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / ".logs" / "cloud-agent.json"


@dataclass(slots=True)
class CloudAgentIdentity:
    device_id: str
    agent_token: str
    claim_code: str | None = None
    claim_token: str | None = None
    claim_url: str | None = None
    claim_expires_at: str | None = None
    cloud_url: str | None = None
    claimed: bool = False
    owner_email: str | None = None
    connected: bool = False
    last_error: str | None = None
    last_connected_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "deviceId": self.device_id,
            "agentToken": self.agent_token,
            "claimCode": self.claim_code,
            "claimToken": self.claim_token,
            "claimUrl": self.claim_url,
            "claimExpiresAt": self.claim_expires_at,
            "cloudUrl": self.cloud_url,
            "claimed": self.claimed,
            "ownerEmail": self.owner_email,
            "connected": self.connected,
            "lastError": self.last_error,
            "lastConnectedAt": self.last_connected_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CloudAgentIdentity":
        return cls(
            device_id=str(payload.get("deviceId") or ""),
            agent_token=str(payload.get("agentToken") or ""),
            claim_code=payload.get("claimCode") if isinstance(payload.get("claimCode"), str) else None,
            claim_token=payload.get("claimToken") if isinstance(payload.get("claimToken"), str) else None,
            claim_url=payload.get("claimUrl") if isinstance(payload.get("claimUrl"), str) else None,
            claim_expires_at=payload.get("claimExpiresAt") if isinstance(payload.get("claimExpiresAt"), str) else None,
            cloud_url=payload.get("cloudUrl") if isinstance(payload.get("cloudUrl"), str) else None,
            claimed=bool(payload.get("claimed")),
            owner_email=payload.get("ownerEmail") if isinstance(payload.get("ownerEmail"), str) else None,
            connected=bool(payload.get("connected")),
            last_error=payload.get("lastError") if isinstance(payload.get("lastError"), str) else None,
            last_connected_at=payload.get("lastConnectedAt") if isinstance(payload.get("lastConnectedAt"), str) else None,
        )


class CloudIdentityStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_identity_path()

    def load(self) -> CloudAgentIdentity | None:
        if not self._path.exists():
            return None
        try:
            raw = self._path.read_text(encoding="utf-8-sig")
            if not raw.strip():
                return None
            payload = json.loads(raw)
        except Exception:
            return None
        identity = CloudAgentIdentity.from_dict(payload)
        if not identity.device_id or not identity.agent_token:
            return None
        return identity

    def save(self, identity: CloudAgentIdentity) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(identity.to_dict(), ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self._path.parent,
            delete=False,
        ) as handle:
            handle.write(data)
            temp_path = Path(handle.name)
        temp_path.replace(self._path)

    def clear(self) -> None:
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
