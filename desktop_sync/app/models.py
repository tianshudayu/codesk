from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(slots=True)
class LockedWindow:
    hwnd: int
    title: str
    process_name: str
    locked_at: datetime

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["locked_at"] = self.locked_at.isoformat()
        return payload


@dataclass(slots=True)
class CandidateAddress:
    address: str
    label: str
    is_recommended: bool = False

    def to_dict(self, port: int, token: str) -> dict[str, object]:
        base_url = f"http://{self.address}:{port}"
        return {
            "address": self.address,
            "label": self.label,
            "isRecommended": self.is_recommended,
            "remoteUrl": f"{base_url}/remote?token={token}",
        }
