from __future__ import annotations

import asyncio
import base64
from collections import deque
import contextlib
import io
import json
import logging
import os
import secrets
import sqlite3
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketDisconnect
import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_WINDOWS_INSTALLER_PATH = PROJECT_ROOT / ".dist" / "windows" / "Codesk-Setup.exe"
DEFAULT_WINDOWS_PAYLOAD_PATH = PROJECT_ROOT / ".dist" / "windows" / "Codesk-Setup-Payload.zip"
DEFAULT_ANDROID_APK_PATH = PROJECT_ROOT / ".dist" / "android" / "Codesk-Android.apk"
CLAIM_TOKEN_TTL = timedelta(hours=12)
PAIR_CODE_TTL = timedelta(minutes=10)
DEVICE_ACCESS_TTL = timedelta(days=30)
logger = logging.getLogger(__name__)


class MagicLinkRequest(BaseModel):
    email: str = Field(min_length=3)


class ClaimDeviceRequest(BaseModel):
    claim_code: str = Field(min_length=3, alias="claimCode")


class ClaimDeviceTokenRequest(BaseModel):
    claim_token: str = Field(min_length=16, alias="claimToken")


class PairingCodeRequest(BaseModel):
    device_id: str = Field(min_length=6, alias="deviceId")
    agent_token: str = Field(min_length=8, alias="agentToken")
    refresh: bool = False


class PairingConnectRequest(BaseModel):
    pair_code: str = Field(min_length=4, max_length=6, alias="pairCode")
    client_name: str | None = Field(default=None, alias="clientName")
    platform: str | None = None


class PairingDisconnectRequest(BaseModel):
    device_id: str | None = Field(default=None, alias="deviceId")
    agent_token: str | None = Field(default=None, alias="agentToken")


class AgentStatusRequest(BaseModel):
    device_id: str = Field(min_length=6, alias="deviceId")
    agent_token: str = Field(min_length=8, alias="agentToken")


class AgentRegisterRequest(BaseModel):
    machine_name: str = Field(min_length=1, alias="machineName")
    platform: str = Field(min_length=1)
    alias: str | None = None
    client_nonce: str | None = Field(default=None, alias="clientNonce")


class AgentEnrollRequest(AgentRegisterRequest):
    enrollment_token: str = Field(min_length=16, alias="enrollmentToken")


class AgentClaimLinkRequest(BaseModel):
    device_id: str = Field(min_length=6, alias="deviceId")
    agent_token: str = Field(min_length=8, alias="agentToken")


class SessionCreateRequest(BaseModel):
    device_id: str = Field(alias="deviceId")
    workspace: str
    prompt: str = Field(min_length=1)
    title: str | None = None
    interaction_mode: str | None = Field(default=None, alias="interactionMode")
    attachment_ids: list[str] | None = Field(default=None, alias="attachmentIds")


class SessionMessageRequest(BaseModel):
    device_id: str = Field(alias="deviceId")
    content: str = Field(min_length=1)
    interaction_mode: str | None = Field(default=None, alias="interactionMode")
    attachment_ids: list[str] | None = Field(default=None, alias="attachmentIds")


class ThreadResumeRequest(BaseModel):
    device_id: str = Field(alias="deviceId")
    prompt: str | None = None
    interaction_mode: str | None = Field(default=None, alias="interactionMode")
    attachment_ids: list[str] | None = Field(default=None, alias="attachmentIds")


class ApprovalResolveRequest(BaseModel):
    device_id: str = Field(alias="deviceId")
    action: str = Field(min_length=1)
    answers: list[dict[str, Any]] | None = None
    content: str | None = None


class ActiveSessionRequest(BaseModel):
    device_id: str = Field(alias="deviceId")
    session_id: str | None = Field(default=None, alias="sessionId")
    source: str | None = None


@dataclass(slots=True)
class UserRecord:
    user_id: str
    email: str


@dataclass(slots=True)
class PendingMagicLink:
    token: str
    email: str
    expires_at: datetime


@dataclass(slots=True)
class AccessSession:
    token: str
    user_id: str
    email: str
    expires_at: datetime


@dataclass(slots=True)
class DeviceAccessSession:
    token: str
    device_id: str
    client_name: str | None
    platform: str | None
    created_at: str
    expires_at: datetime


@dataclass(slots=True)
class DeviceRecord:
    device_id: str
    agent_token: str
    claim_code: str
    claim_token: str
    claim_url: str
    claim_expires_at: str | None
    alias: str
    machine_name: str
    platform: str
    created_at: str
    owner_user_id: str | None = None
    owner_email: str | None = None
    claimed_at: str | None = None
    pair_code_expires_at: str | None = None
    paired_client_name: str | None = None
    paired_client_platform: str | None = None
    paired_at: str | None = None
    online: bool = False
    last_seen_at: str | None = None
    last_status: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        device_state, device_message, recommended_action = describe_device_state(self)
        return {
            "deviceId": self.device_id,
            "alias": self.alias,
            "machineName": self.machine_name,
            "platform": self.platform,
            "claimed": bool(self.owner_user_id),
            "online": self.online,
            "createdAt": self.created_at,
            "claimedAt": self.claimed_at,
            "pairCode": self.claim_code,
            "pairCodeExpiresAt": self.pair_code_expires_at,
            "paired": bool(self.paired_at),
            "pairedClientName": self.paired_client_name,
            "pairedClientPlatform": self.paired_client_platform,
            "pairedAt": self.paired_at,
            "ownerEmail": self.owner_email,
            "lastSeenAt": self.last_seen_at,
            "desktopServiceReady": bool(self.last_status.get("desktopServiceReady")),
            "desktopReady": bool(self.last_status.get("desktopReady")),
            "codexForeground": bool(self.last_status.get("codexForeground")),
            "codexWindowControllable": bool(self.last_status.get("codexWindowControllable")),
            "desktopControllable": bool(self.last_status.get("codexWindowControllable")),
            "cloudConnected": self.online,
            "fullscreenSuggested": bool(self.last_status.get("fullscreenSuggested")),
            "backendAvailable": self.last_status.get("backendAvailable"),
            "deviceState": device_state,
            "deviceMessage": device_message,
            "recommendedAction": recommended_action,
            "lastStatus": self.last_status,
        }


@dataclass(slots=True)
class EnrollmentRecord:
    token: str
    user_id: str
    email: str
    expires_at: datetime
    created_at: str
    used_at: str | None = None


@dataclass(slots=True)
class AgentConnection:
    websocket: WebSocket
    desktop_websocket: WebSocket | None = None
    pending: dict[str, asyncio.Future[dict[str, Any]]] = field(default_factory=dict)
    desktop_watchers: set[WebSocket] = field(default_factory=set)
    ui_watchers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)
    event_watchers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)
    session_watchers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = field(default_factory=dict)
    ui_subscribed: bool = False
    session_subscribed: set[str] = field(default_factory=set)


@dataclass(slots=True)
class CloudState:
    users_by_email: dict[str, UserRecord] = field(default_factory=dict)
    pending_magic_links: dict[str, PendingMagicLink] = field(default_factory=dict)
    access_sessions: dict[str, AccessSession] = field(default_factory=dict)
    device_access_sessions: dict[str, DeviceAccessSession] = field(default_factory=dict)
    enrollments: dict[str, EnrollmentRecord] = field(default_factory=dict)
    devices: dict[str, DeviceRecord] = field(default_factory=dict)
    agent_connections: dict[str, AgentConnection] = field(default_factory=dict)
    event_counters: dict[str, int] = field(default_factory=dict)
    event_history: dict[str, deque[dict[str, Any]]] = field(default_factory=dict)


def describe_device_state(device: DeviceRecord) -> tuple[str, str, str]:
    status = device.last_status if isinstance(device.last_status, dict) else {}
    desktop_service_ready = bool(status.get("desktopServiceReady"))
    desktop_ready = bool(status.get("desktopReady"))
    codex_foreground = bool(status.get("codexForeground"))
    codex_controllable = bool(status.get("codexWindowControllable"))
    backend_available = status.get("backendAvailable")
    if not device.online:
        return ("offline", "Codesk for Windows is offline.", "open_client")
    if not desktop_service_ready:
        return ("connected_agent_only", "Codesk for Windows is online, but desktop sync is still starting.", "restart_client")
    if not backend_available:
        return ("desktop_not_ready", "Codex CLI or App Server is unavailable.", "repair_cli")
    if desktop_ready or (desktop_service_ready and codex_controllable):
        return ("ready", "Codex Desktop is ready.", "open_cloud")
    if codex_foreground and not codex_controllable:
        return ("desktop_not_ready", "Codex is open, but desktop control is not ready yet.", "restart_client")
    return ("desktop_not_ready", "Open Codex Desktop and keep it in front.", "open_codex")


class CloudPersistence:
    def __init__(self, path: str | Path | None) -> None:
        self._path = Path(path) if path else None

    @property
    def enabled(self) -> bool:
        return self._path is not None and str(self._path) != ":memory:"

    def initialize(self) -> None:
        if self._path is None:
            return
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(self._connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS cloud_kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.commit()

    def load(self) -> CloudState:
        state = CloudState()
        if self._path is None:
            return state
        self.initialize()
        with contextlib.closing(self._connect()) as db:
            row = db.execute("SELECT value FROM cloud_kv WHERE key = 'snapshot'").fetchone()
        if row is None:
            return state
        payload = json.loads(row[0])
        for item in payload.get("users", []):
            if not isinstance(item, dict):
                continue
            email = str(item.get("email") or "").strip().lower()
            user_id = str(item.get("userId") or "")
            if email and user_id:
                state.users_by_email[email] = UserRecord(user_id=user_id, email=email)
        now = datetime.now().astimezone()
        for item in payload.get("pendingMagicLinks", []):
            if not isinstance(item, dict):
                continue
            expires_at = _parse_datetime(item.get("expiresAt"))
            token = str(item.get("token") or "")
            email = str(item.get("email") or "").strip().lower()
            if token and email and expires_at and expires_at > now:
                state.pending_magic_links[token] = PendingMagicLink(token=token, email=email, expires_at=expires_at)
        for item in payload.get("accessSessions", []):
            if not isinstance(item, dict):
                continue
            expires_at = _parse_datetime(item.get("expiresAt"))
            token = str(item.get("token") or "")
            email = str(item.get("email") or "").strip().lower()
            user_id = str(item.get("userId") or "")
            if token and email and user_id and expires_at and expires_at > now:
                state.access_sessions[token] = AccessSession(
                    token=token,
                    user_id=user_id,
                    email=email,
                    expires_at=expires_at,
                )
        for item in payload.get("deviceAccessSessions", []):
            if not isinstance(item, dict):
                continue
            expires_at = _parse_datetime(item.get("expiresAt"))
            token = str(item.get("token") or "")
            device_id = str(item.get("deviceId") or "")
            if token and device_id and expires_at and expires_at > now:
                state.device_access_sessions[token] = DeviceAccessSession(
                    token=token,
                    device_id=device_id,
                    client_name=item.get("clientName") if isinstance(item.get("clientName"), str) else None,
                    platform=item.get("platform") if isinstance(item.get("platform"), str) else None,
                    created_at=str(item.get("createdAt") or _now_iso()),
                    expires_at=expires_at,
                )
        for item in payload.get("devices", []):
            if not isinstance(item, dict):
                continue
            device_id = str(item.get("deviceId") or "")
            agent_token = str(item.get("agentToken") or "")
            if not device_id or not agent_token:
                continue
            state.devices[device_id] = DeviceRecord(
                device_id=device_id,
                agent_token=agent_token,
                claim_code=str(item.get("claimCode") or ""),
                claim_token=str(item.get("claimToken") or ""),
                claim_url=str(item.get("claimUrl") or ""),
                claim_expires_at=item.get("claimExpiresAt") if isinstance(item.get("claimExpiresAt"), str) else None,
                alias=str(item.get("alias") or item.get("machineName") or device_id),
                machine_name=str(item.get("machineName") or ""),
                platform=str(item.get("platform") or ""),
                created_at=str(item.get("createdAt") or _now_iso()),
                owner_user_id=item.get("ownerUserId") if isinstance(item.get("ownerUserId"), str) else None,
                owner_email=item.get("ownerEmail") if isinstance(item.get("ownerEmail"), str) else None,
                claimed_at=item.get("claimedAt") if isinstance(item.get("claimedAt"), str) else None,
                pair_code_expires_at=item.get("pairCodeExpiresAt") if isinstance(item.get("pairCodeExpiresAt"), str) else None,
                paired_client_name=item.get("pairedClientName") if isinstance(item.get("pairedClientName"), str) else None,
                paired_client_platform=item.get("pairedClientPlatform") if isinstance(item.get("pairedClientPlatform"), str) else None,
                paired_at=item.get("pairedAt") if isinstance(item.get("pairedAt"), str) else None,
                online=False,
                last_seen_at=item.get("lastSeenAt") if isinstance(item.get("lastSeenAt"), str) else None,
                last_status=item.get("lastStatus") if isinstance(item.get("lastStatus"), dict) else {},
            )
        for item in payload.get("enrollments", []):
            if not isinstance(item, dict):
                continue
            expires_at = _parse_datetime(item.get("expiresAt"))
            token = str(item.get("token") or "")
            user_id = str(item.get("userId") or "")
            email = str(item.get("email") or "").strip().lower()
            if token and user_id and email and expires_at and expires_at > now:
                state.enrollments[token] = EnrollmentRecord(
                    token=token,
                    user_id=user_id,
                    email=email,
                    expires_at=expires_at,
                    created_at=str(item.get("createdAt") or _now_iso()),
                    used_at=item.get("usedAt") if isinstance(item.get("usedAt"), str) else None,
                )
        return state

    def save(self, state: CloudState) -> None:
        if self._path is None:
            return
        self.initialize()
        payload = {
            "users": [
                {"userId": user.user_id, "email": user.email}
                for user in state.users_by_email.values()
            ],
            "pendingMagicLinks": [
                {"token": item.token, "email": item.email, "expiresAt": item.expires_at.isoformat()}
                for item in state.pending_magic_links.values()
            ],
            "accessSessions": [
                {
                    "token": item.token,
                    "userId": item.user_id,
                    "email": item.email,
                    "expiresAt": item.expires_at.isoformat(),
                }
                for item in state.access_sessions.values()
            ],
            "deviceAccessSessions": [
                {
                    "token": item.token,
                    "deviceId": item.device_id,
                    "clientName": item.client_name,
                    "platform": item.platform,
                    "createdAt": item.created_at,
                    "expiresAt": item.expires_at.isoformat(),
                }
                for item in state.device_access_sessions.values()
            ],
            "enrollments": [
                {
                    "token": item.token,
                    "userId": item.user_id,
                    "email": item.email,
                    "expiresAt": item.expires_at.isoformat(),
                    "createdAt": item.created_at,
                    "usedAt": item.used_at,
                }
                for item in state.enrollments.values()
            ],
            "devices": [
                {
                    "deviceId": item.device_id,
                    "agentToken": item.agent_token,
                    "claimCode": item.claim_code,
                    "claimToken": item.claim_token,
                    "claimUrl": item.claim_url,
                    "claimExpiresAt": item.claim_expires_at,
                    "alias": item.alias,
                    "machineName": item.machine_name,
                    "platform": item.platform,
                    "createdAt": item.created_at,
                    "ownerUserId": item.owner_user_id,
                    "ownerEmail": item.owner_email,
                    "claimedAt": item.claimed_at,
                    "pairCodeExpiresAt": item.pair_code_expires_at,
                    "pairedClientName": item.paired_client_name,
                    "pairedClientPlatform": item.paired_client_platform,
                    "pairedAt": item.paired_at,
                    "lastSeenAt": item.last_seen_at,
                    "lastStatus": item.last_status,
                }
                for item in state.devices.values()
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with contextlib.closing(self._connect()) as db:
            db.execute(
                "INSERT INTO cloud_kv(key, value) VALUES('snapshot', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (encoded,),
            )
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        if self._path is None:
            raise RuntimeError("persistence is disabled")
        return sqlite3.connect(str(self._path))


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class AuthManager:
    def __init__(self) -> None:
        self._mode = os.getenv("CODEX_CLOUD_AUTH_MODE", "dev").strip().lower() or "dev"
        self._supabase_url = os.getenv("CODEX_CLOUD_SUPABASE_URL", "").rstrip("/")
        self._supabase_anon_key = os.getenv("CODEX_CLOUD_SUPABASE_ANON_KEY", "")

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def public_config(self) -> dict[str, Any]:
        return {
            "authMode": self._mode,
            "supabaseUrl": self._supabase_url,
            "supabaseAnonKey": self._supabase_anon_key,
        }

    async def request_magic_link(self, state: CloudState, email: str, *, base_url: str) -> dict[str, Any]:
        normalized = email.strip().lower()
        if self._mode == "supabase":
            if not self._supabase_url or not self._supabase_anon_key:
                raise HTTPException(status_code=500, detail="Supabase auth is not configured.")
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self._supabase_url}/auth/v1/otp",
                    headers={"apikey": self._supabase_anon_key, "Content-Type": "application/json"},
                    json={
                        "email": normalized,
                        "create_user": True,
                        "options": {"email_redirect_to": f"{base_url}/"},
                    },
                )
            if response.status_code >= 400:
                raise HTTPException(status_code=400, detail=response.text)
            return {"ok": True, "mode": "supabase"}

        token = secrets.token_urlsafe(24)
        state.pending_magic_links[token] = PendingMagicLink(
            token=token,
            email=normalized,
            expires_at=datetime.now().astimezone() + timedelta(minutes=15),
        )
        return {"ok": True, "mode": "dev", "magicLink": f"{base_url}/auth/verify?token={quote(token)}"}

    async def verify_dev_magic_link(self, state: CloudState, token: str) -> AccessSession:
        pending = state.pending_magic_links.pop(token, None)
        if pending is None or pending.expires_at <= datetime.now().astimezone():
            raise HTTPException(status_code=400, detail="Magic link is invalid or expired.")
        user = state.users_by_email.get(pending.email)
        if user is None:
            user = UserRecord(user_id=secrets.token_urlsafe(8), email=pending.email)
            state.users_by_email[pending.email] = user
        session = AccessSession(
            token=secrets.token_urlsafe(32),
            user_id=user.user_id,
            email=user.email,
            expires_at=datetime.now().astimezone() + timedelta(hours=12),
        )
        state.access_sessions[session.token] = session
        return session

    async def verify_access_token(self, state: CloudState, token: str) -> UserRecord:
        if self._mode == "supabase":
            if not self._supabase_url or not self._supabase_anon_key:
                raise HTTPException(status_code=500, detail="Supabase auth is not configured.")
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self._supabase_url}/auth/v1/user",
                    headers={"apikey": self._supabase_anon_key, "Authorization": f"Bearer {token}"},
                )
            if response.status_code >= 400:
                raise HTTPException(status_code=401, detail="Invalid access token.")
            payload = response.json()
            email = str(payload.get("email") or "").strip().lower()
            if not email:
                raise HTTPException(status_code=401, detail="Authenticated user has no email.")
            user = state.users_by_email.get(email)
            if user is None:
                user = UserRecord(user_id=str(payload.get("id") or secrets.token_urlsafe(8)), email=email)
                state.users_by_email[email] = user
            return user

        now = datetime.now().astimezone()
        expired = [item for item, session in state.access_sessions.items() if session.expires_at <= now]
        for item in expired:
            state.access_sessions.pop(item, None)
        session = state.access_sessions.get(token)
        if session is None:
            raise HTTPException(status_code=401, detail="Invalid access token.")
        user = state.users_by_email.get(session.email)
        if user is None:
            user = UserRecord(user_id=session.user_id, email=session.email)
            state.users_by_email[user.email] = user
        return user


@dataclass(slots=True)
class ResolvedClient:
    user: UserRecord | None = None
    device_session: DeviceAccessSession | None = None

    @property
    def is_device_session(self) -> bool:
        return self.device_session is not None


auth_manager = AuthManager()


def public_base_url(request: Request) -> str:
    configured = os.getenv("CODEX_CLOUD_PUBLIC_URL", "").strip().rstrip("/")
    return configured or str(request.base_url).rstrip("/")


def public_base_url_from_scope(scope: Any) -> str:
    configured = os.getenv("CODEX_CLOUD_PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        return configured
    base_url = getattr(scope, "base_url", None)
    if base_url is not None:
        value = str(base_url).rstrip("/")
        if value.startswith("ws://"):
            return f"http://{value[5:]}"
        if value.startswith("wss://"):
            return f"https://{value[6:]}"
        return value
    raise RuntimeError("Public base URL is unavailable.")


def create_claim_ticket(base_url: str) -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now().astimezone() + CLAIM_TOKEN_TTL
    return token, f"{base_url}/claim?token={quote(token)}", expires_at.isoformat()


def claim_ticket_expired(device: DeviceRecord) -> bool:
    expires_at = _parse_datetime(device.claim_expires_at)
    if expires_at is None:
        return True
    return expires_at <= datetime.now().astimezone()


def claim_ticket_matches_base(device: DeviceRecord, base_url: str) -> bool:
    claim_url = (device.claim_url or "").strip()
    normalized = base_url.rstrip("/")
    return bool(claim_url) and claim_url.startswith(f"{normalized}/claim?")


def refresh_device_claim(device: DeviceRecord, base_url: str) -> None:
    token, claim_url, expires_at = create_claim_ticket(base_url)
    device.claim_token = token
    device.claim_url = claim_url
    device.claim_expires_at = expires_at


def clear_device_claim(device: DeviceRecord) -> None:
    device.claim_token = ""
    device.claim_url = ""
    device.claim_expires_at = None


def refresh_device_pair_code(device: DeviceRecord) -> str:
    device.claim_code = f"{secrets.randbelow(1000000):06d}"
    device.pair_code_expires_at = (datetime.now().astimezone() + PAIR_CODE_TTL).isoformat()
    return device.claim_code


def pair_code_expired(device: DeviceRecord) -> bool:
    expires_at = _parse_datetime(device.pair_code_expires_at)
    return expires_at is None or expires_at <= datetime.now().astimezone()


def invalidate_device_sessions(state: CloudState, device_id: str) -> None:
    stale = [token for token, session in state.device_access_sessions.items() if session.device_id == device_id]
    for token in stale:
        state.device_access_sessions.pop(token, None)


def create_device_access_session(
    state: CloudState,
    device: DeviceRecord,
    *,
    client_name: str | None,
    platform_name: str | None,
) -> DeviceAccessSession:
    invalidate_device_sessions(state, device.device_id)
    session = DeviceAccessSession(
        token=secrets.token_urlsafe(32),
        device_id=device.device_id,
        client_name=(client_name or "").strip() or None,
        platform=(platform_name or "").strip() or None,
        created_at=_now_iso(),
        expires_at=datetime.now().astimezone() + DEVICE_ACCESS_TTL,
    )
    state.device_access_sessions[session.token] = session
    return session


def verify_device_access_token(state: CloudState, token: str) -> DeviceAccessSession | None:
    now = datetime.now().astimezone()
    expired = [item for item, session in state.device_access_sessions.items() if session.expires_at <= now]
    for item in expired:
        state.device_access_sessions.pop(item, None)
    return state.device_access_sessions.get(token)


async def verify_client_access_token(state: CloudState, token: str) -> ResolvedClient:
    device_session = verify_device_access_token(state, token)
    if device_session is not None:
        return ResolvedClient(device_session=device_session)
    user = await auth_manager.verify_access_token(state, token)
    return ResolvedClient(user=user)


def assign_device_owner(device: DeviceRecord, user: UserRecord) -> None:
    device.owner_user_id = user.user_id
    device.owner_email = user.email
    device.claimed_at = datetime.now().astimezone().isoformat()
    clear_device_claim(device)


def release_device_owner(device: DeviceRecord, base_url: str) -> None:
    device.owner_user_id = None
    device.owner_email = None
    device.claimed_at = None
    refresh_device_claim(device, base_url)


def assign_device_pairing(device: DeviceRecord, *, client_name: str | None, platform_name: str | None) -> None:
    device.paired_client_name = (client_name or "").strip() or None
    device.paired_client_platform = (platform_name or "").strip() or None
    device.paired_at = _now_iso()


def release_device_pairing(state: CloudState, device: DeviceRecord) -> None:
    invalidate_device_sessions(state, device.device_id)
    device.paired_client_name = None
    device.paired_client_platform = None
    device.paired_at = None
    refresh_device_pair_code(device)


def device_welcome_payload(device: DeviceRecord) -> dict[str, Any]:
    return {
        "type": "agent.welcome",
        "deviceId": device.device_id,
        "claimed": bool(device.owner_user_id),
        "claimCode": device.claim_code,
        "pairCode": device.claim_code,
        "pairCodeExpiresAt": device.pair_code_expires_at,
        "claimToken": device.claim_token,
        "claimUrl": device.claim_url,
        "claimExpiresAt": device.claim_expires_at,
        "ownerEmail": device.owner_email,
        "pairedClientName": device.paired_client_name,
        "pairedClientPlatform": device.paired_client_platform,
        "pairedAt": device.paired_at,
    }


def windows_installer_path(download_root: Path | None = None) -> Path:
    configured = os.getenv("CODEX_CLOUD_WINDOWS_INSTALLER_PATH", "").strip()
    if configured:
        return Path(configured)
    root = download_root or PROJECT_ROOT / ".dist"
    return root / "windows" / "Codesk-Setup.exe"


def windows_payload_path(download_root: Path | None = None) -> Path:
    configured = os.getenv("CODEX_CLOUD_WINDOWS_PAYLOAD_PATH", "").strip()
    if configured:
        return Path(configured)
    root = download_root or PROJECT_ROOT / ".dist"
    return root / "windows" / "Codesk-Setup-Payload.zip"


def android_apk_path(download_root: Path | None = None) -> Path:
    configured = os.getenv("CODEX_CLOUD_ANDROID_APK_PATH", "").strip()
    if configured:
        return Path(configured)
    root = download_root or PROJECT_ROOT / ".dist"
    return root / "android" / "Codesk-Android.apk"


def create_device_record(
    *,
    base_url: str,
    machine_name: str,
    platform_name: str,
    alias: str | None,
    owner: UserRecord | None = None,
) -> DeviceRecord:
    now = datetime.now().astimezone().isoformat()
    claim_token, claim_url, claim_expires_at = create_claim_ticket(base_url)
    device = DeviceRecord(
        device_id=secrets.token_urlsafe(9),
        agent_token=secrets.token_urlsafe(24),
        claim_code="",
        claim_token=claim_token,
        claim_url=claim_url,
        claim_expires_at=claim_expires_at,
        alias=alias or machine_name,
        machine_name=machine_name,
        platform=platform_name,
        created_at=now,
        owner_user_id=owner.user_id if owner else None,
        owner_email=owner.email if owner else None,
        claimed_at=now if owner else None,
    )
    refresh_device_pair_code(device)
    if owner is not None:
        clear_device_claim(device)
    return device


def device_identity_payload(device: DeviceRecord) -> dict[str, Any]:
    return {
        "deviceId": device.device_id,
        "agentToken": device.agent_token,
        "claimCode": device.claim_code,
        "pairCode": device.claim_code,
        "pairCodeExpiresAt": device.pair_code_expires_at,
        "claimToken": device.claim_token,
        "claimUrl": device.claim_url,
        "claimExpiresAt": device.claim_expires_at,
        "claimed": bool(device.owner_user_id),
        "ownerEmail": device.owner_email,
        "pairedClientName": device.paired_client_name,
        "pairedClientPlatform": device.paired_client_platform,
        "pairedAt": device.paired_at,
    }


def next_event_id(state: CloudState, stream_key: str) -> str:
    value = state.event_counters.get(stream_key, 0) + 1
    state.event_counters[stream_key] = value
    return str(value)


def append_event_history(state: CloudState, device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    event_id = next_event_id(state, f"events:{device_id}")
    event = dict(payload)
    event.setdefault("eventId", event_id)
    history = state.event_history.setdefault(device_id, deque(maxlen=200))
    history.append(event)
    return event


async def emit_device_event(state: CloudState, device_id: str, payload: dict[str, Any]) -> None:
    connection = state.agent_connections.get(device_id)
    event = append_event_history(state, device_id, payload)
    if connection is None:
        return
    stale_queues: list[asyncio.Queue[dict[str, Any]]] = []
    for queue in list(connection.event_watchers):
        try:
            queue.put_nowait(dict(event))
        except Exception:
            stale_queues.append(queue)
    for queue in stale_queues:
        connection.event_watchers.discard(queue)


async def emit_pairing_event(state: CloudState, device: DeviceRecord, *, reason: str) -> None:
    connection = state.agent_connections.get(device.device_id)
    payload = {
        "type": "pairing.changed",
        "stream": "pairing",
        "deviceId": device.device_id,
        "reason": reason,
        "device": device.to_public_dict(),
    }
    if connection is not None:
        stale_queues: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in list(connection.ui_watchers):
            try:
                queue.put_nowait(dict(payload))
            except Exception:
                stale_queues.append(queue)
        for queue in stale_queues:
            connection.ui_watchers.discard(queue)
    await emit_device_event(
        state,
        device.device_id,
        payload,
    )


def powershell_single_quote(value: str) -> str:
    return value.replace("'", "''")


def normalized_interaction_mode(value: str | None) -> str:
    return "plan" if str(value or "").strip().lower() == "plan" else "default"


def session_requires_desktop(payload: dict[str, Any], interaction_mode: str | None = None) -> bool:
    if normalized_interaction_mode(interaction_mode) == "plan":
        return False
    route = str(payload.get("deliveryRoute") or "").strip().lower()
    if route:
        return route == "desktop_gui"
    desktop_state = str(payload.get("desktopTargetState") or "").strip().lower()
    if desktop_state in {"aligned", "switching", "blocked", "not_found", "unbound"}:
        return True
    return False


def build_windows_agent_install_script(cloud_url: str, enrollment_token: str) -> str:
    quoted_cloud = powershell_single_quote(cloud_url)
    quoted_token = powershell_single_quote(enrollment_token)
    return f"""$ErrorActionPreference = 'Stop'
$CloudUrl = '{quoted_cloud}'
$EnrollmentToken = '{quoted_token}'
$Root = Join-Path $env:LOCALAPPDATA 'Codesk\\agent'
$Zip = Join-Path $env:TEMP 'codesk-agent-source.zip'
$Source = Join-Path $Root 'source'
$StartScript = Join-Path $Root 'start-agent.ps1'

New-Item -ItemType Directory -Force -Path $Root | Out-Null
if (Test-Path $Source) {{ Remove-Item -Recurse -Force $Source }}
Invoke-WebRequest -Uri "$CloudUrl/api/downloads/windows-agent-source.zip" -OutFile $Zip -UseBasicParsing
Expand-Archive -LiteralPath $Zip -DestinationPath $Source -Force
Set-Location $Source

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {{
  throw 'Python is required. Please install Python 3.11+ and run this installer again.'
}}
python -m venv .venv
& .\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
& .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt

$StartContent = @"
`$env:CODEX_CLOUD_URL = '$CloudUrl'
`$env:CODEX_CLOUD_ENABLED = '1'
`$env:CODEX_CLOUD_ENROLLMENT_TOKEN = '$EnrollmentToken'
Set-Location '$Source'
& '$Source\\.venv\\Scripts\\python.exe' -m bridge.agent_main
"@
Set-Content -LiteralPath $StartScript -Value $StartContent -Encoding UTF8

$TaskName = 'Codesk Agent'
$TaskAction = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$StartScript`""
schtasks /Create /TN $TaskName /SC ONLOGON /TR $TaskAction /F | Out-Null
Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$StartScript`"" -WindowStyle Hidden
Start-Process $CloudUrl
Write-Host 'Codesk Agent installed and started.'
"""


def build_agent_source_zip() -> bytes:
    excluded_dirs = {".git", ".venv", ".logs", "__pycache__"}
    excluded_suffixes = {".pyc", ".pyo", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in PROJECT_ROOT.rglob("*"):
            relative = path.relative_to(PROJECT_ROOT)
            if any(part in excluded_dirs for part in relative.parts):
                continue
            if path.is_dir():
                continue
            if path.name.startswith("tmp-") or path.suffix.lower() in excluded_suffixes:
                continue
            archive.write(path, relative.as_posix())
    return buffer.getvalue()


def build_windows_client_bundle(cloud_url: str, enrollment_token: str | None = None) -> bytes:
    quoted_cloud = powershell_single_quote(cloud_url)
    quoted_token = powershell_single_quote(enrollment_token or "")
    setup_script = (PROJECT_ROOT / "scripts" / "setup_codex_cli.ps1").read_text(encoding="utf-8")
    client_assets_dir = PROJECT_ROOT / "clients" / "windows"
    tray_script = (client_assets_dir / "codesk_tray.py").read_text(encoding="utf-8")
    client_requirements = (client_assets_dir / "requirements.txt").read_text(encoding="utf-8")
    build_notes = (client_assets_dir / "BUILDING.txt").read_text(encoding="utf-8")
    install_script = f"""$ErrorActionPreference = 'Stop'
$CloudUrl = '{quoted_cloud}'
$EnrollmentToken = '{quoted_token}'
$BundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallRoot = Join-Path $env:LOCALAPPDATA 'Codesk'
$ClientRoot = Join-Path $InstallRoot 'client'
$AgentRoot = Join-Path $InstallRoot 'agent'
$AgentSource = Join-Path $AgentRoot 'source'
$IdentityPath = Join-Path $AgentRoot 'cloud-agent.json'
$AgentZip = Join-Path $env:TEMP 'codesk-agent-source.zip'
$ConfigPath = Join-Path $ClientRoot 'codesk-client.json'
$StartTrayScript = Join-Path $ClientRoot 'start-tray.ps1'

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ClientRoot | Out-Null
New-Item -ItemType Directory -Force -Path $AgentRoot | Out-Null
Copy-Item -Path (Join-Path $BundleRoot 'client\\*') -Destination $ClientRoot -Recurse -Force

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {{
  throw 'Python 3.11+ is required. Please install Python and run install.ps1 again.'
}}

Invoke-WebRequest -Uri "$CloudUrl/api/downloads/windows-agent-source.zip" -OutFile $AgentZip -UseBasicParsing
if (Test-Path $AgentSource) {{ Remove-Item -Recurse -Force $AgentSource }}
Expand-Archive -LiteralPath $AgentZip -DestinationPath $AgentSource -Force
Set-Location $AgentSource
python -m venv .venv
& .\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
& .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
& .\\.venv\\Scripts\\python.exe -m pip install -r "$ClientRoot\\requirements.txt"

$Config = @{{
  cloudUrl = $CloudUrl
  enrollmentToken = $EnrollmentToken
  agentRoot = $AgentSource
  identityFile = $IdentityPath
  installedAt = (Get-Date).ToString('o')
}}
$Config | ConvertTo-Json | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

$StartContent = @"
`$env:CODEX_CLOUD_URL = '$CloudUrl'
`$env:CODEX_CLOUD_ENABLED = '1'
`$env:CODEX_CLOUD_ENROLLMENT_TOKEN = '$EnrollmentToken'
`$env:CODEX_CLOUD_AGENT_IDENTITY_FILE = '$IdentityPath'
`$env:PYTHONUTF8 = '1'
Set-Location '$ClientRoot'
& '$AgentSource\\.venv\\Scripts\\pythonw.exe' '$ClientRoot\\codesk_tray.py'
"@
Set-Content -LiteralPath $StartTrayScript -Value $StartContent -Encoding UTF8

$PowerShellExe = (Get-Command powershell.exe).Source
$ShortcutArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$StartTrayScript`""
$WshShell = New-Object -ComObject WScript.Shell
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codesk for Windows.lnk'
$StartupShortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'Codesk Tray.lnk'
foreach ($ShortcutPath in @($DesktopShortcut, $StartupShortcut)) {{
  $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $PowerShellExe
  $Shortcut.Arguments = $ShortcutArgs
  $Shortcut.WorkingDirectory = $ClientRoot
  $Shortcut.Save()
}}

if (-not (Test-Path (Join-Path $env:APPDATA 'npm\\codex.cmd'))) {{
  Write-Host 'Codex CLI not found in %APPDATA%\\npm. You can run setup_codex_cli.ps1 from the installed client folder after install.'
}}

Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$StartTrayScript`"" -WindowStyle Hidden
if ($EnrollmentToken) {{
  Start-Process $CloudUrl
}}
Write-Host 'Codesk Windows Client installed. The tray app will keep the agent running after login.'
"""
    readme = f"""Codesk for Windows
===================

1. Extract this zip anywhere on your Windows PC.
2. Right-click install.ps1 and run with PowerShell.
3. The installer will:
   - download the latest Codesk agent source from {cloud_url}
   - create %LOCALAPPDATA%\\Codesk
   - create a desktop shortcut and startup entry
   - start Codesk for Windows
4. Keep Codesk for Windows running in the tray.
5. Open Codex Desktop and keep it in front when sending tasks from your phone.

{"This personalized bundle auto-connects this PC to your current Codesk account." if enrollment_token else "This generic bundle will ask you to sign in and connect this PC on first launch."}
If Codex CLI is missing, run the bundled setup_codex_cli.ps1 from the client folder.
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme)
        archive.writestr("install.ps1", install_script)
        archive.writestr("client/codesk_tray.py", tray_script)
        archive.writestr("client/requirements.txt", client_requirements)
        archive.writestr("client/BUILDING.txt", build_notes)
        archive.writestr("client/setup_codex_cli.ps1", setup_script)
    return buffer.getvalue()


def persist_state(request: Request) -> None:
    persistence = getattr(request.app.state, "persistence", None)
    if isinstance(persistence, CloudPersistence):
        persistence.save(request.app.state.cloud)


def persist_cloud_state(state: CloudState, persistence: CloudPersistence | None) -> None:
    if persistence is not None:
        persistence.save(state)


def decorate_session_payload(device: DeviceRecord, payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    status = device.last_status if isinstance(device.last_status, dict) else {}
    result["deviceId"] = device.device_id
    result["deviceOnline"] = device.online
    result["desktopServiceReady"] = bool(status.get("desktopServiceReady"))
    result["desktopReady"] = bool(status.get("desktopReady"))
    result["codexForeground"] = bool(status.get("codexForeground"))
    result["codexControllable"] = bool(status.get("codexWindowControllable"))
    result["fullscreenSuggested"] = bool(status.get("fullscreenSuggested"))
    desktop = status.get("desktopAutomation") if isinstance(status.get("desktopAutomation"), dict) else {}
    message = desktop.get("desktopControlMessage") if isinstance(desktop, dict) else None
    if isinstance(message, str) and message:
        result["desktopControlMessage"] = message
    return result


def decorate_session_list_payload(device: DeviceRecord, payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    items = payload.get("items")
    if isinstance(items, list):
        result["items"] = [
            decorate_session_payload(device, item)
            for item in items
            if isinstance(item, dict)
        ]
    return result


async def build_bootstrap_payload(state: CloudState, device: DeviceRecord | None, request: Request, client: ResolvedClient) -> dict[str, Any]:
    if client.user is not None:
        devices = [item.to_public_dict() for item in state.devices.values() if item.owner_user_id == client.user.user_id]
        me_payload: dict[str, Any] | None = {"email": client.user.email, "userId": client.user.user_id}
        auth_mode = "user"
    elif client.device_session is not None and device is not None:
        devices = [device.to_public_dict()]
        me_payload = None
        auth_mode = "device"
    else:
        devices = []
        me_payload = None
        auth_mode = "device"
    payload: dict[str, Any] = {
        "me": me_payload,
        "authMode": auth_mode,
        "devices": devices,
        "selectedDeviceId": device.device_id if device is not None else None,
        "device": device.to_public_dict() if device is not None else None,
        "activeSession": None,
        "sessions": {"items": []},
        "threads": {"items": []},
        "workspaces": {"items": []},
        "approvals": {"items": []},
        "currentSession": None,
    }
    if device is None:
        return payload

    jobs = await asyncio.gather(
        dispatch_rpc(state, device.device_id, "list_workspaces", {}),
        dispatch_rpc(state, device.device_id, "get_active_session", {}),
        dispatch_rpc(state, device.device_id, "list_sessions", {}),
        dispatch_rpc(state, device.device_id, "list_threads", {}),
        return_exceptions=True,
    )
    workspaces, active_session, sessions, threads = jobs
    if isinstance(workspaces, dict):
        payload["workspaces"] = workspaces
    if isinstance(active_session, dict):
        payload["activeSession"] = active_session
    if isinstance(sessions, dict):
        payload["sessions"] = decorate_session_list_payload(device, sessions)
    if isinstance(threads, dict):
        payload["threads"] = threads

    return payload


def create_app(persistence_path: str | Path | None = None, download_root: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Codex Cloud Gateway")
    if persistence_path is None:
        configured = os.getenv("CODEX_CLOUD_DB_PATH", "").strip()
        persistence_path = configured or PROJECT_ROOT / ".logs" / "cloud-gateway.sqlite3"
    persistence = CloudPersistence(persistence_path)
    app.state.persistence = persistence
    app.state.cloud = persistence.load()
    app.state.download_root = Path(download_root) if download_root is not None else PROJECT_ROOT / ".dist"
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware("http")
    async def cache_control(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "landing.html")

    @app.get("/app")
    async def app_shell() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        state = request.app.state.cloud
        return {"ok": True, "devices": len(state.devices), "agentsOnline": sum(1 for item in state.devices.values() if item.online)}

    @app.post("/api/auth/magic-link")
    async def request_magic_link(payload: MagicLinkRequest, request: Request) -> JSONResponse:
        result = await auth_manager.request_magic_link(request.app.state.cloud, payload.email, base_url=public_base_url(request))
        persist_state(request)
        return JSONResponse(result)

    @app.get("/api/auth/config")
    async def auth_config(request: Request) -> JSONResponse:
        payload = dict(auth_manager.public_config)
        payload["publicUrl"] = public_base_url(request)
        return JSONResponse(payload)

    @app.get("/auth/verify")
    async def verify_magic_link(token: str, request: Request, claim: str | None = None) -> RedirectResponse:
        session = await auth_manager.verify_dev_magic_link(request.app.state.cloud, token)
        persist_state(request)
        target = f"/app?access_token={quote(session.token)}"
        if claim:
            target = f"{target}&claim={quote(claim)}"
        return RedirectResponse(url=target, status_code=302)

    @app.get("/claim")
    async def claim_link(token: str) -> RedirectResponse:
        return RedirectResponse(url=f"/app?claim={quote(token)}", status_code=302)

    @app.get("/api/me")
    async def me(request: Request, user: UserRecord = Depends(require_user)) -> JSONResponse:
        return JSONResponse({"userId": user.user_id, "email": user.email, "authMode": auth_manager.mode})

    @app.get("/api/bootstrap")
    async def bootstrap(
        request: Request,
        client: ResolvedClient = Depends(require_client),
        device_id: str | None = Query(default=None, alias="deviceId"),
    ) -> JSONResponse:
        state = request.app.state.cloud
        device = require_accessible_device(state, client, device_id) if (device_id or client.device_session is not None) else None
        payload = await build_bootstrap_payload(state, device, request, client)
        return JSONResponse(payload)

    @app.post("/api/agent/register")
    async def register_agent(payload: AgentRegisterRequest, request: Request) -> JSONResponse:
        state = request.app.state.cloud
        device = create_device_record(
            base_url=public_base_url(request),
            machine_name=payload.machine_name,
            platform_name=payload.platform,
            alias=payload.alias,
        )
        state.devices[device.device_id] = device
        persist_state(request)
        return JSONResponse(device_identity_payload(device))

    @app.post("/api/enrollments")
    async def create_enrollment(request: Request, user: UserRecord = Depends(require_user)) -> JSONResponse:
        state = request.app.state.cloud
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now().astimezone() + timedelta(minutes=30)
        enrollment = EnrollmentRecord(
            token=token,
            user_id=user.user_id,
            email=user.email,
            expires_at=expires_at,
            created_at=_now_iso(),
        )
        state.enrollments[token] = enrollment
        persist_state(request)
        base_url = public_base_url(request)
        download_url = f"{base_url}/api/downloads/windows-agent?enrollment_token={quote(token)}"
        client_download_url = f"{base_url}/api/downloads/windows-client/latest?enrollment_token={quote(token)}"
        install_command = (
            "powershell -NoProfile -ExecutionPolicy Bypass -Command "
            f"\"iwr '{download_url}' -UseB | iex\""
        )
        return JSONResponse(
            {
                "ok": True,
                "enrollmentToken": token,
                "expiresAt": expires_at.isoformat(),
                "downloadUrl": download_url,
                "clientDownloadUrl": client_download_url,
                "installCommand": install_command,
            }
        )

    @app.post("/api/agent/enroll")
    async def enroll_agent(payload: AgentEnrollRequest, request: Request) -> JSONResponse:
        state = request.app.state.cloud
        enrollment = state.enrollments.get(payload.enrollment_token)
        if enrollment is None or enrollment.expires_at <= datetime.now().astimezone():
            raise HTTPException(status_code=404, detail="Enrollment token is invalid or expired.")
        if enrollment.used_at:
            raise HTTPException(status_code=409, detail="Enrollment token has already been used.")
        user = state.users_by_email.get(enrollment.email)
        if user is None:
            user = UserRecord(user_id=enrollment.user_id, email=enrollment.email)
            state.users_by_email[user.email] = user
        device = create_device_record(
            base_url=public_base_url(request),
            machine_name=payload.machine_name,
            platform_name=payload.platform,
            alias=payload.alias,
            owner=user,
        )
        state.devices[device.device_id] = device
        enrollment.used_at = _now_iso()
        persist_state(request)
        return JSONResponse(device_identity_payload(device))

    @app.post("/api/agent/claim-link")
    async def refresh_agent_claim_link(payload: AgentClaimLinkRequest, request: Request) -> JSONResponse:
        state = request.app.state.cloud
        device = state.devices.get(payload.device_id)
        if device is None or device.agent_token != payload.agent_token:
            raise HTTPException(status_code=401, detail="Invalid device credentials.")
        if not device.owner_user_id:
            base_url = public_base_url(request)
            if claim_ticket_expired(device) or not claim_ticket_matches_base(device, base_url):
                refresh_device_claim(device, base_url)
            persist_state(request)
        return JSONResponse(device_identity_payload(device))

    @app.post("/api/pairing/code")
    async def issue_pairing_code(payload: PairingCodeRequest, request: Request) -> JSONResponse:
        state = request.app.state.cloud
        device = state.devices.get(payload.device_id)
        if device is None or device.agent_token != payload.agent_token:
            raise HTTPException(status_code=401, detail="Invalid device credentials.")
        if payload.refresh or pair_code_expired(device):
            refresh_device_pair_code(device)
            persist_state(request)
            await notify_agent_claim_state(state, device)
            await emit_pairing_event(state, device, reason="code_refreshed")
        return JSONResponse(
            {
                "ok": True,
                "deviceId": device.device_id,
                "pairCode": device.claim_code,
                "expiresAt": device.pair_code_expires_at,
                "paired": bool(device.paired_at),
                "pairedClientName": device.paired_client_name,
                "pairedClientPlatform": device.paired_client_platform,
            }
        )

    @app.post("/api/pairing/connect")
    async def connect_pairing(payload: PairingConnectRequest, request: Request) -> JSONResponse:
        state = request.app.state.cloud
        pair_code = payload.pair_code.strip()
        device = next(
            (
                item
                for item in state.devices.values()
                if item.claim_code == pair_code and not pair_code_expired(item)
            ),
            None,
        )
        if device is None:
            raise HTTPException(status_code=404, detail="Pair code is invalid or expired.")
        assign_device_pairing(device, client_name=payload.client_name, platform_name=payload.platform)
        refresh_device_pair_code(device)
        session = create_device_access_session(
            state,
            device,
            client_name=payload.client_name,
            platform_name=payload.platform,
        )
        persist_state(request)
        await notify_agent_claim_state(state, device)
        await emit_pairing_event(state, device, reason="paired")
        return JSONResponse(
            {
                "ok": True,
                "accessToken": session.token,
                "deviceId": device.device_id,
                "device": device.to_public_dict(),
            }
        )

    @app.get("/api/pairing/status")
    async def pairing_status(
        request: Request,
        client: ResolvedClient = Depends(require_client),
        device_id: str | None = Query(default=None, alias="deviceId"),
    ) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        public_device = device.to_public_dict()
        return JSONResponse(
            {
                "ok": True,
                "deviceId": device.device_id,
                "paired": bool(device.paired_at),
                "pairedClientName": device.paired_client_name,
                "pairedClientPlatform": device.paired_client_platform,
                "pairedAt": device.paired_at,
                "online": device.online,
                "deviceState": public_device.get("deviceState"),
                "deviceMessage": public_device.get("deviceMessage"),
                "cloudConnected": public_device.get("cloudConnected"),
                "desktopServiceReady": public_device.get("desktopServiceReady"),
                "desktopControllable": public_device.get("desktopControllable"),
                "codexForeground": public_device.get("codexForeground"),
                "backendAvailable": public_device.get("backendAvailable"),
                "recommendedAction": public_device.get("recommendedAction"),
                "device": public_device,
            }
        )

    @app.post("/api/pairing/disconnect")
    async def disconnect_pairing(
        payload: PairingDisconnectRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        state = request.app.state.cloud
        device: DeviceRecord
        if payload.device_id and payload.agent_token:
            device = state.devices.get(payload.device_id)
            if device is None or device.agent_token != payload.agent_token:
                raise HTTPException(status_code=401, detail="Invalid device credentials.")
        else:
            token = extract_request_token(request, authorization)
            client = await verify_client_access_token(state, token)
            device = require_accessible_device(state, client, payload.device_id)
        release_device_pairing(state, device)
        persist_state(request)
        await notify_agent_claim_state(state, device)
        await emit_pairing_event(state, device, reason="disconnected")
        return JSONResponse({"ok": True, "device": device.to_public_dict()})

    @app.post("/api/agent/status")
    async def agent_status(payload: AgentStatusRequest, request: Request) -> JSONResponse:
        state = request.app.state.cloud
        device = state.devices.get(payload.device_id)
        if device is None or device.agent_token != payload.agent_token:
            raise HTTPException(status_code=401, detail="Invalid device credentials.")
        return JSONResponse(
            {
                "ok": True,
                "deviceId": device.device_id,
                "online": device.online,
                "device": device.to_public_dict(),
            }
        )

    @app.get("/api/downloads/windows-agent")
    async def download_windows_agent(enrollment_token: str = Query(alias="enrollment_token"), request: Request = None) -> Response:
        enrollment = request.app.state.cloud.enrollments.get(enrollment_token)
        if enrollment is None or enrollment.expires_at <= datetime.now().astimezone() or enrollment.used_at:
            raise HTTPException(status_code=404, detail="Enrollment token is invalid or expired.")
        script = build_windows_agent_install_script(public_base_url(request), enrollment_token)
        return Response(
            content=script,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="install-codesk-agent.ps1"'},
        )

    @app.get("/api/downloads/windows-client/latest")
    async def download_windows_client(
        enrollment_token: str | None = Query(default=None, alias="enrollment_token"),
        request: Request = None,
    ) -> Response:
        token = enrollment_token.strip() if isinstance(enrollment_token, str) else ""
        if token:
            enrollment = request.app.state.cloud.enrollments.get(token)
            if enrollment is None or enrollment.expires_at <= datetime.now().astimezone() or enrollment.used_at:
                raise HTTPException(status_code=404, detail="Enrollment token is invalid or expired.")
        artifact = windows_installer_path(request.app.state.download_root)
        if artifact.exists():
            return FileResponse(
                artifact,
                media_type="application/vnd.microsoft.portable-executable",
                filename="Codesk-Setup.exe",
            )
        data = build_windows_client_bundle(public_base_url(request), token or None)
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="Codesk-Windows-Client.zip"'},
        )

    @app.get("/api/downloads/windows-client/payload")
    async def download_windows_client_payload(request: Request) -> Response:
        artifact = windows_payload_path(request.app.state.download_root)
        if not artifact.exists():
            raise HTTPException(status_code=503, detail="Windows installer payload is unavailable.")
        return FileResponse(
            artifact,
            media_type="application/zip",
            filename="Codesk-Setup-Payload.zip",
        )

    @app.get("/api/downloads/android/latest")
    async def download_android_app(request: Request) -> Response:
        artifact = android_apk_path(request.app.state.download_root)
        if not artifact.exists():
            raise HTTPException(status_code=503, detail="Android app artifact is unavailable.")
        return FileResponse(
            artifact,
            media_type="application/vnd.android.package-archive",
            filename="Codesk-Android.apk",
        )

    @app.get("/api/downloads/windows-agent-source.zip")
    async def download_windows_agent_source() -> Response:
        data = build_agent_source_zip()
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="codesk-agent-source.zip"'},
        )

    @app.post("/api/devices/claim")
    async def claim_device(payload: ClaimDeviceRequest, request: Request, user: UserRecord = Depends(require_user)) -> JSONResponse:
        state = request.app.state.cloud
        device = next((item for item in state.devices.values() if item.claim_code == payload.claim_code), None)
        if device is None:
            raise HTTPException(status_code=404, detail="Claim code not found.")
        assign_device_owner(device, user)
        persist_state(request)
        await notify_agent_claim_state(state, device)
        return JSONResponse({"ok": True, "device": device.to_public_dict()})

    @app.post("/api/devices/claim-token")
    async def claim_device_token(payload: ClaimDeviceTokenRequest, request: Request, user: UserRecord = Depends(require_user)) -> JSONResponse:
        state = request.app.state.cloud
        device = next((item for item in state.devices.values() if item.claim_token == payload.claim_token), None)
        if device is None or claim_ticket_expired(device):
            raise HTTPException(status_code=404, detail="Claim token is invalid or expired.")
        if device.owner_user_id and device.owner_user_id != user.user_id:
            raise HTTPException(status_code=409, detail="This computer has already been claimed by another account.")
        assign_device_owner(device, user)
        persist_state(request)
        await notify_agent_claim_state(state, device)
        return JSONResponse({"ok": True, "device": device.to_public_dict()})

    @app.post("/api/devices/{device_id}/unbind")
    async def unbind_device(device_id: str, request: Request, user: UserRecord = Depends(require_user)) -> JSONResponse:
        state = request.app.state.cloud
        device = require_owned_device(state, user, device_id)
        invalidate_device_sessions(state, device.device_id)
        release_device_pairing(state, device)
        release_device_owner(device, public_base_url(request))
        persist_state(request)
        await notify_agent_claim_state(state, device)
        return JSONResponse({"ok": True, "device": device.to_public_dict()})

    @app.post("/api/agent/unbind")
    async def agent_unbind_device(payload: AgentClaimLinkRequest, request: Request) -> JSONResponse:
        state = request.app.state.cloud
        device = state.devices.get(payload.device_id)
        if device is None or device.agent_token != payload.agent_token:
            raise HTTPException(status_code=401, detail="Invalid agent token.")
        invalidate_device_sessions(state, device.device_id)
        release_device_pairing(state, device)
        release_device_owner(device, public_base_url(request))
        persist_state(request)
        await notify_agent_claim_state(state, device)
        return JSONResponse(
            {
                "ok": True,
                "deviceId": device.device_id,
                "claimCode": device.claim_code,
                "claimToken": device.claim_token,
                "claimUrl": device.claim_url,
                "claimExpiresAt": device.claim_expires_at,
                "claimed": False,
                "ownerEmail": None,
            }
        )

    @app.get("/api/devices")
    async def list_devices(request: Request, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        state = request.app.state.cloud
        if client.user is not None:
            items = [item.to_public_dict() for item in state.devices.values() if item.owner_user_id == client.user.user_id]
        elif client.device_session is not None:
            device = state.devices.get(client.device_session.device_id)
            items = [device.to_public_dict()] if device is not None else []
        else:
            items = []
        items.sort(
            key=lambda item: (
                item.get("deviceState") != "ready",
                not item.get("online", False),
                item.get("alias") or "",
            )
        )
        return JSONResponse({"items": items})

    @app.get("/api/workspaces")
    async def list_workspaces(device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "list_workspaces", {})
        return JSONResponse(result)

    @app.get("/api/ui/active-session")
    async def get_active_session(device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "get_active_session", {})
        return JSONResponse(result)

    @app.post("/api/ui/active-session")
    async def set_active_session(payload: ActiveSessionRequest, request: Request, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, payload.device_id)
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "set_active_session",
            {"sessionId": payload.session_id, "source": payload.source or "cloud_ui"},
        )
        return JSONResponse(result)

    @app.post("/api/attachments")
    async def upload_attachment(
        request: Request,
        device_id: str = Query(alias="deviceId"),
        file: UploadFile = File(...),
        client: ResolvedClient = Depends(require_client),
    ) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        data = await file.read()
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "upload_attachment",
            {
                "fileName": file.filename or "image",
                "mimeType": file.content_type or "",
                "dataBase64": base64.b64encode(data).decode("ascii"),
            },
            timeout=45.0,
        )
        return JSONResponse(result)

    @app.get("/api/attachments/{attachment_id}/preview")
    async def attachment_preview(
        attachment_id: str,
        device_id: str = Query(alias="deviceId"),
        request: Request = None,
        client: ResolvedClient = Depends(require_client),
    ) -> Response:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "get_attachment_preview",
            {"attachmentId": attachment_id},
            timeout=45.0,
        )
        raw = result.get("dataBase64") if isinstance(result.get("dataBase64"), str) else ""
        try:
            data = base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Invalid attachment preview payload.") from exc
        media_type = str(result.get("mimeType") or "application/octet-stream")
        return Response(content=data, media_type=media_type)

    @app.get("/api/sessions")
    async def list_sessions(device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "list_sessions", {})
        return JSONResponse(decorate_session_list_payload(device, result))

    @app.post("/api/sessions")
    async def create_session(payload: SessionCreateRequest, request: Request, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, payload.device_id)
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "create_session",
            {
                "workspace": payload.workspace,
                "prompt": payload.prompt,
                "title": payload.title,
                "interactionMode": payload.interaction_mode or "default",
                "attachmentIds": payload.attachment_ids or [],
                "requireDesktop": (payload.interaction_mode or "default").strip().lower() != "plan",
            },
        )
        return JSONResponse(decorate_session_payload(device, result))

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str, device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "get_session", {"sessionId": session_id})
        return JSONResponse(decorate_session_payload(device, result))

    @app.post("/api/sessions/{session_id}/messages")
    async def continue_session(session_id: str, payload: SessionMessageRequest, request: Request, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, payload.device_id)
        interaction_mode = normalized_interaction_mode(payload.interaction_mode)
        require_desktop = False
        if interaction_mode != "plan":
            current_session = await dispatch_rpc(
                request.app.state.cloud,
                device.device_id,
                "get_session",
                {"sessionId": session_id},
            )
            require_desktop = session_requires_desktop(current_session, interaction_mode)
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "continue_session",
            {
                "sessionId": session_id,
                "content": payload.content,
                "interactionMode": interaction_mode,
                "attachmentIds": payload.attachment_ids or [],
                "requireDesktop": require_desktop,
            },
        )
        if isinstance(result, dict):
            result = dict(result)
            result["deviceId"] = device.device_id
            result["deviceOnline"] = device.online
        return JSONResponse(result)

    @app.post("/api/sessions/{session_id}/desktop-align")
    async def align_desktop_session(session_id: str, device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "align_desktop_session",
            {"sessionId": session_id},
        )
        return JSONResponse(decorate_session_payload(device, result))

    @app.post("/api/sessions/{session_id}/cancel")
    async def cancel_session(session_id: str, device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "cancel_session", {"sessionId": session_id})
        return JSONResponse(result)

    @app.get("/api/sessions/{session_id}/approvals")
    async def list_approvals(session_id: str, device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "list_approvals", {"sessionId": session_id})
        return JSONResponse(result)

    @app.post("/api/sessions/{session_id}/approvals/{approval_id}/resolve")
    async def resolve_approval(session_id: str, approval_id: str, payload: ApprovalResolveRequest, request: Request, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, payload.device_id)
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "resolve_approval",
            {
                "sessionId": session_id,
                "approvalId": approval_id,
                "action": payload.action,
                "answers": payload.answers,
                "content": payload.content,
            },
        )
        return JSONResponse(result)

    @app.get("/api/sessions/{session_id}/events")
    async def session_events(session_id: str, device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> StreamingResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        connection = request.app.state.cloud.agent_connections.get(device.device_id)
        if connection is None:
            raise HTTPException(status_code=503, detail="Target device is offline.")
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        connection.session_watchers.setdefault(session_id, set()).add(queue)
        await ensure_session_subscription(connection, session_id)

        async def stream():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    event_id = next_event_id(request.app.state.cloud, f"session:{device.device_id}:{session_id}")
                    payload = dict(item)
                    payload.setdefault("eventId", event_id)
                    yield f"id: {event_id}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            finally:
                watchers = connection.session_watchers.get(session_id)
                if watchers is not None:
                    watchers.discard(queue)
                    if not watchers:
                        connection.session_watchers.pop(session_id, None)
                        connection.session_subscribed.discard(session_id)
                        with contextlib.suppress(Exception):
                            await send_to_agent(connection, {"type": "event.unsubscribe_session", "sessionId": session_id})

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/ui/events")
    async def ui_events(device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> StreamingResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        connection = request.app.state.cloud.agent_connections.get(device.device_id)
        if connection is None:
            raise HTTPException(status_code=503, detail="Target device is offline.")
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        connection.ui_watchers.add(queue)
        await ensure_ui_subscription(connection)

        async def stream():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    event_id = next_event_id(request.app.state.cloud, f"ui:{device.device_id}")
                    payload = dict(item)
                    payload.setdefault("eventId", event_id)
                    yield f"id: {event_id}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            finally:
                connection.ui_watchers.discard(queue)
                if not connection.ui_watchers:
                    connection.ui_subscribed = False
                    with contextlib.suppress(Exception):
                        await send_to_agent(connection, {"type": "event.unsubscribe_ui"})

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/events")
    async def events(
        device_id: str | None = Query(default=None, alias="deviceId"),
        request: Request = None,
        client: ResolvedClient = Depends(require_client),
        since: str | None = Query(default=None),
    ) -> StreamingResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        connection = request.app.state.cloud.agent_connections.get(device.device_id)
        if connection is None:
            raise HTTPException(status_code=503, detail="Target device is offline.")
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        connection.event_watchers.add(queue)
        await ensure_ui_subscription(connection)

        async def stream():
            try:
                history = request.app.state.cloud.event_history.get(device.device_id, deque())
                if since:
                    with contextlib.suppress(ValueError):
                        baseline = int(since)
                        for item in list(history):
                            event_id = int(str(item.get("eventId") or "0") or "0")
                            if event_id > baseline:
                                yield f"id: {item['eventId']}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"id: {item['eventId']}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
            finally:
                connection.event_watchers.discard(queue)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/threads")
    async def list_threads(device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "list_threads", {})
        return JSONResponse(result)

    @app.get("/api/threads/{thread_id}")
    async def get_thread(thread_id: str, device_id: str | None = Query(default=None, alias="deviceId"), request: Request = None, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, device_id)
        result = await dispatch_rpc(request.app.state.cloud, device.device_id, "get_thread", {"threadId": thread_id})
        return JSONResponse(result)

    @app.post("/api/threads/{thread_id}/resume")
    async def resume_thread(thread_id: str, payload: ThreadResumeRequest, request: Request, client: ResolvedClient = Depends(require_client)) -> JSONResponse:
        device = require_accessible_device(request.app.state.cloud, client, payload.device_id)
        result = await dispatch_rpc(
            request.app.state.cloud,
            device.device_id,
            "resume_thread",
            {
                "threadId": thread_id,
                "prompt": payload.prompt,
                "interactionMode": payload.interaction_mode or "default",
                "attachmentIds": payload.attachment_ids or [],
            },
        )
        return JSONResponse(decorate_session_payload(device, result))

    @app.websocket("/ws/agent/{device_id}")
    async def agent_socket(device_id: str, websocket: WebSocket) -> None:
        state = websocket.app.state.cloud
        device = state.devices.get(device_id)
        token = websocket.query_params.get("agent_token")
        await websocket.accept()
        if device is None or token != device.agent_token:
            await websocket.send_json({"type": "error", "message": "invalid agent token"})
            await websocket.close(code=4401)
            return
        existing = state.agent_connections.get(device_id)
        if existing is not None:
            with contextlib.suppress(Exception):
                await existing.websocket.close(code=4409)
        connection = AgentConnection(websocket=websocket)
        state.agent_connections[device_id] = connection
        device.online = True
        device.last_seen_at = _now_iso()
        if not device.owner_user_id:
            base_url = public_base_url_from_scope(websocket)
            if claim_ticket_expired(device) or not claim_ticket_matches_base(device, base_url):
                refresh_device_claim(device, base_url)
            persist_cloud_state(state, websocket.app.state.persistence)
        await websocket.send_json(device_welcome_payload(device))
        try:
            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    continue
                await handle_agent_message(state, device_id, message)
        except WebSocketDisconnect:
            pass
        finally:
            if state.agent_connections.get(device_id) is connection:
                state.agent_connections.pop(device_id, None)
                device.online = False
                device.last_seen_at = _now_iso()
                if connection.desktop_websocket is not None:
                    with contextlib.suppress(Exception):
                        await connection.desktop_websocket.close(code=4410)
                await emit_device_event(
                    state,
                    device_id,
                    {
                        "type": "device.status",
                        "stream": "device",
                        "deviceId": device_id,
                        "device": device.to_public_dict(),
                    },
                )

    @app.websocket("/ws/agent-desktop/{device_id}")
    async def agent_desktop_socket(device_id: str, websocket: WebSocket) -> None:
        state = websocket.app.state.cloud
        device = state.devices.get(device_id)
        token = websocket.query_params.get("agent_token")
        await websocket.accept()
        if device is None or token != device.agent_token:
            await websocket.send_json({"type": "error", "message": "invalid agent token"})
            await websocket.close(code=4401)
            return
        connection = state.agent_connections.get(device_id)
        if connection is None:
            await websocket.send_json({"type": "error", "message": "main agent channel is offline"})
            await websocket.close(code=4404)
            return
        if connection.desktop_websocket is not None:
            with contextlib.suppress(Exception):
                await connection.desktop_websocket.close(code=4409)
        connection.desktop_websocket = websocket
        try:
            await websocket.send_json({"type": "desktop.ready", "deviceId": device_id, "status": device.last_status})
            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    continue
                payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
                stale: list[WebSocket] = []
                for watcher in list(connection.desktop_watchers):
                    try:
                        await watcher.send_json(payload)
                    except Exception:
                        stale.append(watcher)
                for watcher in stale:
                    connection.desktop_watchers.discard(watcher)
        except WebSocketDisconnect:
            return
        finally:
            if connection.desktop_websocket is websocket:
                connection.desktop_websocket = None

    @app.websocket("/api/desktop/ws")
    async def desktop_socket(websocket: WebSocket, device_id: str = Query(alias="deviceId"), authorization: str | None = Header(default=None)) -> None:
        state = websocket.app.state.cloud
        token = extract_websocket_token(websocket, authorization)
        client = await verify_client_access_token(state, token)
        device = require_accessible_device(state, client, device_id)
        await websocket.accept()
        connection = state.agent_connections.get(device.device_id)
        if connection is None:
            await websocket.send_json({"type": "error", "code": "device_offline", "message": "Agent is offline."})
            await websocket.close(code=4404)
            return
        if connection.desktop_websocket is None:
            with contextlib.suppress(Exception):
                await send_to_agent(connection, {"type": "desktop.channel.open"})
            deadline = asyncio.get_running_loop().time() + 5.0
            while connection.desktop_websocket is None and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.1)
        if connection.desktop_websocket is None:
            await websocket.send_json({"type": "error", "code": "desktop_unavailable", "message": "Desktop preview channel is unavailable."})
            await websocket.close(code=4404)
            return
        connection.desktop_watchers.add(websocket)
        try:
            await websocket.send_json({"type": "ready", "deviceId": device.device_id, "status": device.last_status})
            while True:
                payload = await websocket.receive_json()
                if not isinstance(payload, dict):
                    await websocket.send_json({"type": "error", "code": "invalid_message", "message": "desktop websocket message must be a JSON object"})
                    continue
                await send_to_desktop_agent(connection, {"type": "desktop.command", "id": payload.get("id"), "payload": payload})
        except WebSocketDisconnect:
            return
        finally:
            connection.desktop_watchers.discard(websocket)
            if not connection.desktop_watchers:
                with contextlib.suppress(Exception):
                    await send_to_agent(connection, {"type": "desktop.channel.close"})

    return app


def extract_token(authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    raise HTTPException(status_code=401, detail="Missing access token.")


def extract_request_token(request: Request, authorization: str | None) -> str:
    query_token = request.query_params.get("access_token")
    if isinstance(query_token, str) and query_token.strip():
        return query_token.strip()
    return extract_token(authorization)


def extract_websocket_token(websocket: WebSocket, authorization: str | None) -> str:
    query_token = websocket.query_params.get("access_token")
    if isinstance(query_token, str) and query_token.strip():
        return query_token.strip()
    return extract_token(authorization)


async def require_user(request: Request, authorization: str | None = Header(default=None)) -> UserRecord:
    token = extract_request_token(request, authorization)
    return await auth_manager.verify_access_token(request.app.state.cloud, token)


async def require_client(request: Request, authorization: str | None = Header(default=None)) -> ResolvedClient:
    token = extract_request_token(request, authorization)
    return await verify_client_access_token(request.app.state.cloud, token)


def require_owned_device(state: CloudState, user: UserRecord, device_id: str) -> DeviceRecord:
    device = state.devices.get(device_id)
    if device is None or device.owner_user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Device not found.")
    return device


def require_accessible_device(state: CloudState, client: ResolvedClient, device_id: str | None) -> DeviceRecord:
    effective_device_id = (device_id or "").strip()
    if client.device_session is not None:
        if not effective_device_id:
            effective_device_id = client.device_session.device_id
        if effective_device_id != client.device_session.device_id:
            raise HTTPException(status_code=404, detail="Device not found.")
        device = state.devices.get(effective_device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found.")
        return device
    if client.user is None:
        raise HTTPException(status_code=401, detail="Missing access token.")
    if not effective_device_id:
        raise HTTPException(status_code=400, detail="Device id is required.")
    return require_owned_device(state, client.user, effective_device_id)


def rpc_timeout_for_action(action: str) -> float:
    return {
        "get_active_session": 6.0,
        "list_workspaces": 8.0,
        "list_sessions": 10.0,
        "get_session": 10.0,
        "list_threads": 12.0,
        "get_thread": 12.0,
        "list_approvals": 5.0,
        "align_desktop_session": 10.0,
        "create_session": 25.0,
        "continue_session": 25.0,
        "resume_thread": 25.0,
    }.get(action, 20.0)


async def dispatch_rpc(state: CloudState, device_id: str, action: str, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    connection = state.agent_connections.get(device_id)
    if connection is None:
        raise HTTPException(status_code=503, detail="Target device is offline.")
    request_id = secrets.token_urlsafe(8)
    future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
    connection.pending[request_id] = future
    if action in {"list_threads", "list_sessions", "resume_thread", "get_thread", "get_session"}:
        logger.warning(
            "dispatch_rpc start device=%s action=%s id=%s conn=%s pending=%s",
            device_id,
            action,
            request_id,
            hex(id(connection)),
            len(connection.pending),
        )
    await send_to_agent(connection, {"type": "rpc.request", "id": request_id, "action": action, "payload": payload})
    try:
        response = await asyncio.wait_for(future, timeout=timeout or rpc_timeout_for_action(action))
    except asyncio.TimeoutError as exc:
        connection.pending.pop(request_id, None)
        latest = state.agent_connections.get(device_id)
        logger.warning(
            "dispatch_rpc timeout device=%s action=%s id=%s conn=%s latest_conn=%s pending=%s",
            device_id,
            action,
            request_id,
            hex(id(connection)),
            hex(id(latest)) if latest is not None else None,
            len(connection.pending),
        )
        raise HTTPException(status_code=504, detail="Agent request timed out.") from exc
    if action in {"list_threads", "list_sessions", "resume_thread", "get_thread", "get_session"}:
        logger.warning(
            "dispatch_rpc done device=%s action=%s id=%s conn=%s ok=%s",
            device_id,
            action,
            request_id,
            hex(id(connection)),
            response.get("ok"),
        )
    if not response.get("ok"):
        error = response.get("error") if isinstance(response.get("error"), dict) else {}
        raise HTTPException(status_code=int(error.get("code") or 502), detail=str(error.get("message") or "Agent request failed."))
    result = response.get("result")
    return result if isinstance(result, dict) else {}


async def send_to_agent(connection: AgentConnection, payload: dict[str, Any]) -> None:
    await connection.websocket.send_json(payload)


async def send_to_desktop_agent(connection: AgentConnection, payload: dict[str, Any]) -> None:
    websocket = connection.desktop_websocket
    if websocket is None:
        raise HTTPException(status_code=503, detail="Desktop control channel is offline.")
    await websocket.send_json(payload)


async def notify_agent_claim_state(state: CloudState, device: DeviceRecord) -> None:
    connection = state.agent_connections.get(device.device_id)
    if connection is None:
        return
    with contextlib.suppress(Exception):
        await send_to_agent(connection, device_welcome_payload(device))


async def ensure_ui_subscription(connection: AgentConnection) -> None:
    if connection.ui_subscribed:
        return
    await send_to_agent(connection, {"type": "event.subscribe_ui"})
    connection.ui_subscribed = True


async def ensure_session_subscription(connection: AgentConnection, session_id: str) -> None:
    if session_id in connection.session_subscribed:
        return
    await send_to_agent(connection, {"type": "event.subscribe_session", "sessionId": session_id})
    connection.session_subscribed.add(session_id)


async def handle_agent_message(state: CloudState, device_id: str, message: dict[str, Any]) -> None:
    device = state.devices[device_id]
    device.last_seen_at = _now_iso()
    message_type = str(message.get("type") or "")
    connection = state.agent_connections.get(device_id)
    if connection is None:
        return
    if message_type == "rpc.response":
        future = connection.pending.pop(str(message.get("id") or ""), None)
        logger.warning(
            "handle_agent_message rpc.response device=%s id=%s conn=%s matched=%s pending=%s",
            device_id,
            str(message.get("id") or ""),
            hex(id(connection)),
            future is not None,
            len(connection.pending),
        )
        if future is not None and not future.done():
            future.set_result(message)
        return
    if message_type == "agent.keepalive":
        await send_to_agent(
            connection,
            {
                "type": "agent.keepalive.ack",
                "seq": message.get("seq"),
                "serverTs": time.time(),
            },
        )
        return
    if message_type == "agent.status":
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        device.last_status = payload
        stale_queues: list[asyncio.Queue[dict[str, Any]]] = []
        device_payload = {"type": "device.status", "deviceId": device_id, "device": device.to_public_dict()}
        for queue in list(connection.ui_watchers):
            try:
                queue.put_nowait(dict(device_payload))
            except Exception:
                stale_queues.append(queue)
        for queue in stale_queues:
            connection.ui_watchers.discard(queue)
        await emit_device_event(
            state,
            device_id,
            {
                "type": "device.status",
                "stream": "device",
                "deviceId": device_id,
                "device": device.to_public_dict(),
            },
        )
        return
    if message_type == "desktop.event":
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        stale: list[WebSocket] = []
        for watcher in list(connection.desktop_watchers):
            try:
                await watcher.send_json(payload)
            except Exception:
                stale.append(watcher)
        for watcher in stale:
                connection.desktop_watchers.discard(watcher)
        return
    if message_type == "ui.event":
        payload = message.get("event") if isinstance(message.get("event"), dict) else {}
        event = append_event_history(
            state,
            device_id,
            {
                "type": "ui.event",
                "stream": "ui",
                "deviceId": device_id,
                "event": payload,
            },
        )
        stale_queues: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in list(connection.ui_watchers):
            try:
                queue.put_nowait(payload)
            except Exception:
                stale_queues.append(queue)
        for queue in stale_queues:
            connection.ui_watchers.discard(queue)
        stale_unified: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in list(connection.event_watchers):
            try:
                queue.put_nowait(dict(event))
            except Exception:
                stale_unified.append(queue)
        for queue in stale_unified:
            connection.event_watchers.discard(queue)
        return
    if message_type == "session.event":
        session_id = str(message.get("sessionId") or "")
        payload = message.get("event") if isinstance(message.get("event"), dict) else {}
        event = append_event_history(
            state,
            device_id,
            {
                "type": "session.event",
                "stream": "session",
                "deviceId": device_id,
                "sessionId": session_id,
                "event": payload,
            },
        )
        watchers = connection.session_watchers.get(session_id, set())
        stale_queues: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in list(watchers):
            try:
                queue.put_nowait(payload)
            except Exception:
                stale_queues.append(queue)
        for queue in stale_queues:
            watchers.discard(queue)
        stale_unified: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in list(connection.event_watchers):
            try:
                queue.put_nowait(dict(event))
            except Exception:
                stale_unified.append(queue)
        for queue in stale_unified:
            connection.event_watchers.discard(queue)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


app = create_app()


def main() -> None:
    port = int(os.getenv("CODEX_CLOUD_PORT", "8892"))
    host = os.getenv("CODEX_CLOUD_HOST", "0.0.0.0")
    uvicorn.run("cloud_gateway.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
