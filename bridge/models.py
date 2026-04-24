from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AttachmentRecord:
    attachment_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime
    local_path: str

    def to_public_dict(self, *, include_local_path: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "attachmentId": self.attachment_id,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
            "createdAt": self.created_at.isoformat(),
            "previewUrl": f"/api/attachments/{self.attachment_id}/preview",
        }
        if include_local_path:
            payload["localPath"] = self.local_path
        return payload


@dataclass(slots=True)
class SessionMessage:
    role: str
    content: str
    created_at: datetime
    attachments: list[AttachmentRecord] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "content": self.content,
            "createdAt": self.created_at.isoformat(),
            "attachments": [attachment.to_public_dict() for attachment in self.attachments],
        }


@dataclass(slots=True)
class ApprovalRecord:
    approval_id: str
    session_id: str
    request_id: str
    kind: str
    title: str
    summary: str
    payload: dict[str, Any]
    available_actions: list[str]
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "approvalId": self.approval_id,
            "sessionId": self.session_id,
            "requestId": self.request_id,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "payload": self.payload,
            "availableActions": list(self.available_actions),
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
            "resolvedAt": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution,
        }


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    workspace: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[SessionMessage] = field(default_factory=list)
    result_summary: str | None = None
    last_error: str | None = None
    event_history: list[dict[str, object]] = field(default_factory=list)
    backend: str | None = None
    backend_session_id: str | None = None
    backend_run_id: str | None = None
    source_thread_id: str | None = None
    session_kind: str = "new"
    delivery_route: str = "app_server"
    last_thread_sync_at: datetime | None = None
    desktop_target_state: str = "unbound"
    desktop_target_message: str | None = None
    desktop_target_confidence: float | None = None
    desktop_target_matched_text: str | None = None
    interaction_mode: str = "default"
    plan_state: str = "none"

    def to_public_dict(self) -> dict[str, object]:
        return {
            "sessionId": self.session_id,
            "workspace": self.workspace,
            "title": self.title,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "messages": [message.to_public_dict() for message in self.messages],
            "resultSummary": self.result_summary,
            "lastError": self.last_error,
            "backend": self.backend,
            "backendSessionId": self.backend_session_id,
            "backendRunId": self.backend_run_id,
            "sourceThreadId": self.source_thread_id,
            "sessionKind": self.session_kind,
            "deliveryRoute": self.delivery_route,
            "lastThreadSyncAt": self.last_thread_sync_at.isoformat() if self.last_thread_sync_at else None,
            "desktopTargetState": self.desktop_target_state,
            "desktopTargetMessage": self.desktop_target_message,
            "desktopTargetConfidence": self.desktop_target_confidence,
            "desktopTargetMatchedText": self.desktop_target_matched_text,
            "interactionMode": self.interaction_mode,
            "planState": self.plan_state,
        }
