from __future__ import annotations

import asyncio
import secrets
from datetime import datetime

from .models import ApprovalRecord, AttachmentRecord, SessionMessage, SessionRecord


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._approvals: dict[str, dict[str, ApprovalRecord]] = {}
        self._attachments: dict[str, AttachmentRecord] = {}
        self._approval_request_map: dict[str, tuple[str, str]] = {}
        self._subscribers: dict[str, dict[str, asyncio.Queue[dict[str, object]]]] = {}
        self._ui_subscribers: dict[str, asyncio.Queue[dict[str, object]]] = {}
        self._active_session_id: str | None = None
        self._active_session_source: str | None = None
        self._active_session_updated_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        workspace: str,
        title: str,
        initial_prompt: str = "",
        *,
        status: str = "running",
        source_thread_id: str | None = None,
        session_kind: str = "new",
        interaction_mode: str = "default",
        plan_state: str = "none",
        attachments: list[AttachmentRecord] | None = None,
    ) -> SessionRecord:
        async with self._lock:
            now = datetime.now().astimezone()
            session = SessionRecord(
                session_id=secrets.token_urlsafe(9),
                workspace=workspace,
                title=title,
                status=status,
                created_at=now,
                updated_at=now,
                source_thread_id=source_thread_id,
                session_kind=session_kind,
                interaction_mode=interaction_mode,
                plan_state=plan_state,
            )
            if initial_prompt:
                session.messages.append(
                    SessionMessage(
                        role="user",
                        content=initial_prompt,
                        created_at=now,
                        attachments=list(attachments or []),
                    )
                )
            self._sessions[session.session_id] = session
            self._approvals[session.session_id] = {}
            self._subscribers[session.session_id] = {}
        await self.publish_ui_event({"type": "sessions.changed", "reason": "created", "sessionId": session.session_id})
        return session

    async def list_sessions(self) -> list[SessionRecord]:
        async with self._lock:
            return sorted(self._sessions.values(), key=lambda item: item.updated_at, reverse=True)

    async def get_session(self, session_id: str) -> SessionRecord | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def get_active_session(self) -> dict[str, object]:
        async with self._lock:
            return {
                "activeSessionId": self._active_session_id,
                "source": self._active_session_source,
                "updatedAt": self._active_session_updated_at.isoformat() if self._active_session_updated_at else None,
            }

    async def set_active_session(self, session_id: str | None, *, source: str) -> dict[str, object]:
        async with self._lock:
            if session_id is not None and session_id not in self._sessions:
                raise KeyError(session_id)
            now = datetime.now().astimezone()
            self._active_session_id = session_id
            self._active_session_source = source
            self._active_session_updated_at = now
            payload = {
                "activeSessionId": session_id,
                "source": source,
                "updatedAt": now.isoformat(),
            }
        await self.publish_ui_event({"type": "activeSession.changed", **payload})
        return payload

    async def find_session_by_thread_id(self, thread_id: str) -> SessionRecord | None:
        async with self._lock:
            matched = [
                session
                for session in self._sessions.values()
                if session.source_thread_id == thread_id or session.backend_session_id == thread_id
            ]
            if not matched:
                return None
            matched.sort(key=lambda item: item.updated_at, reverse=True)
            return matched[0]

    async def add_attachment(self, attachment: AttachmentRecord) -> AttachmentRecord:
        async with self._lock:
            self._attachments[attachment.attachment_id] = attachment
        return attachment

    async def get_attachment(self, attachment_id: str) -> AttachmentRecord | None:
        async with self._lock:
            return self._attachments.get(attachment_id)

    async def get_attachments(self, attachment_ids: list[str]) -> list[AttachmentRecord]:
        async with self._lock:
            return [
                self._attachments[attachment_id]
                for attachment_id in attachment_ids
                if attachment_id in self._attachments
            ]

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        attachments: list[AttachmentRecord] | None = None,
    ) -> SessionRecord | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            now = datetime.now().astimezone()
            session.messages.append(
                SessionMessage(
                    role=role,
                    content=content,
                    created_at=now,
                    attachments=list(attachments or []),
                )
            )
            session.updated_at = now
        await self.publish_ui_event({"type": "sessions.changed", "reason": "message", "sessionId": session_id})
        return session

    async def remove_last_message(self, session_id: str, role: str, content: str) -> SessionRecord | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            for index in range(len(session.messages) - 1, -1, -1):
                message = session.messages[index]
                if message.role == role and message.content == content:
                    session.messages.pop(index)
                    session.updated_at = datetime.now().astimezone()
                    break
            else:
                return session
        await self.publish_ui_event({"type": "sessions.changed", "reason": "message_removed", "sessionId": session_id})
        return session

    async def set_status(
        self,
        session_id: str,
        status: str,
        *,
        summary: str | None = None,
        error: str | None = None,
    ) -> SessionRecord | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.status = status
            session.updated_at = datetime.now().astimezone()
            if summary is not None:
                session.result_summary = summary
            if error is not None:
                session.last_error = error
            elif status in {"running", "completed", "imported"}:
                session.last_error = None
        await self.publish_ui_event({"type": "sessions.changed", "reason": "status", "sessionId": session_id})
        return session

    async def set_backend_context(
        self,
        session_id: str,
        *,
        backend: str | None = None,
        backend_session_id: str | None = None,
        backend_run_id: str | None = None,
        source_thread_id: str | None = None,
    ) -> SessionRecord | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.updated_at = datetime.now().astimezone()
            if backend is not None:
                session.backend = backend
            if backend_session_id is not None:
                session.backend_session_id = backend_session_id
            if backend_run_id is not None:
                session.backend_run_id = backend_run_id
            if source_thread_id is not None:
                session.source_thread_id = source_thread_id
        await self.publish_ui_event({"type": "sessions.changed", "reason": "backend_context", "sessionId": session_id})
        return session

    async def set_delivery_route(self, session_id: str, delivery_route: str) -> SessionRecord | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.delivery_route == delivery_route:
                return session
            session.delivery_route = delivery_route
            session.updated_at = datetime.now().astimezone()
        await self.publish_ui_event({"type": "sessions.changed", "reason": "delivery_route", "sessionId": session_id})
        return session

    async def set_interaction_state(
        self,
        session_id: str,
        *,
        interaction_mode: str | None = None,
        plan_state: str | None = None,
    ) -> SessionRecord | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            changed = False
            if interaction_mode is not None and session.interaction_mode != interaction_mode:
                session.interaction_mode = interaction_mode
                changed = True
            if plan_state is not None and session.plan_state != plan_state:
                session.plan_state = plan_state
                changed = True
            if not changed:
                return session
            session.updated_at = datetime.now().astimezone()
        await self.publish_ui_event({"type": "sessions.changed", "reason": "interaction_state", "sessionId": session_id})
        return session

    async def set_desktop_target(
        self,
        session_id: str,
        state: str,
        message: str | None = None,
        *,
        confidence: float | None = None,
        matched_text: str | None = None,
    ) -> SessionRecord | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if (
                session.desktop_target_state == state
                and session.desktop_target_message == message
                and session.desktop_target_confidence == confidence
                and session.desktop_target_matched_text == matched_text
            ):
                return session
            session.desktop_target_state = state
            session.desktop_target_message = message
            session.desktop_target_confidence = confidence
            session.desktop_target_matched_text = matched_text
            session.updated_at = datetime.now().astimezone()
        await self.publish_ui_event({"type": "sessions.changed", "reason": "desktop_target", "sessionId": session_id})
        return session

    async def apply_thread_mirror(
        self,
        session_id: str,
        *,
        title: str,
        status: str,
        summary: str | None,
        error: str | None,
        messages: list[SessionMessage],
        synced_at: datetime,
    ) -> tuple[bool, SessionRecord | None]:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False, None
            content_changed = (
                session.title != title
                or session.status != status
                or session.result_summary != summary
                or session.last_error != error
                or not _messages_equal(session.messages, messages)
            )
            session.last_thread_sync_at = synced_at
            if not content_changed:
                return False, session
            session.title = title
            session.status = status
            session.result_summary = summary
            session.last_error = error
            session.messages = [
                SessionMessage(
                    role=item.role,
                    content=item.content,
                    created_at=item.created_at,
                    attachments=list(item.attachments),
                )
                for item in messages
            ]
            session.updated_at = synced_at
        await self.publish_ui_event({"type": "sessions.changed", "reason": "thread_mirror", "sessionId": session_id})
        return True, session

    async def add_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        async with self._lock:
            approvals = self._approvals.setdefault(approval.session_id, {})
            approvals[approval.approval_id] = approval
            self._approval_request_map[approval.request_id] = (approval.session_id, approval.approval_id)
            session = self._sessions.get(approval.session_id)
            if session is not None:
                session.updated_at = datetime.now().astimezone()
        await self.publish_ui_event({"type": "sessions.changed", "reason": "approval_added", "sessionId": approval.session_id})
        return approval

    async def get_approval(self, session_id: str, approval_id: str) -> ApprovalRecord | None:
        async with self._lock:
            return self._approvals.get(session_id, {}).get(approval_id)

    async def list_approvals(self, session_id: str, *, active_only: bool = False) -> list[ApprovalRecord]:
        async with self._lock:
            approvals = list(self._approvals.get(session_id, {}).values())
        approvals.sort(key=lambda item: item.created_at, reverse=True)
        if active_only:
            return [item for item in approvals if item.status == "pending"]
        return approvals

    async def resolve_approval(self, session_id: str, approval_id: str, resolution: str) -> ApprovalRecord | None:
        async with self._lock:
            approval = self._approvals.get(session_id, {}).get(approval_id)
            if approval is None:
                return None
            approval.status = "resolved"
            approval.resolution = resolution
            approval.resolved_at = datetime.now().astimezone()
            session = self._sessions.get(session_id)
            if session is not None:
                session.updated_at = approval.resolved_at
            self._approval_request_map.pop(approval.request_id, None)
        await self.publish_ui_event({"type": "sessions.changed", "reason": "approval_resolved", "sessionId": session_id})
        return approval

    async def resolve_approval_by_request_id(self, request_id: str, resolution: str) -> ApprovalRecord | None:
        async with self._lock:
            mapping = self._approval_request_map.get(request_id)
            if mapping is None:
                return None
            session_id, approval_id = mapping
            approval = self._approvals.get(session_id, {}).get(approval_id)
            if approval is None:
                self._approval_request_map.pop(request_id, None)
                return None
            approval.status = "resolved"
            approval.resolution = resolution
            approval.resolved_at = datetime.now().astimezone()
            session = self._sessions.get(session_id)
            if session is not None:
                session.updated_at = approval.resolved_at
            self._approval_request_map.pop(request_id, None)
        await self.publish_ui_event({"type": "sessions.changed", "reason": "approval_request_resolved", "sessionId": session_id})
        return approval

    async def publish(self, session_id: str, event: dict[str, object]) -> None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            session.event_history.append(event)
            session.event_history = session.event_history[-200:]
            subscribers = list(self._subscribers.get(session_id, {}).values())
        for queue in subscribers:
            await queue.put(event)

    async def publish_ui_event(self, event: dict[str, object]) -> None:
        async with self._lock:
            subscribers = list(self._ui_subscribers.values())
        for queue in subscribers:
            await queue.put(event)

    async def subscribe(self, session_id: str) -> tuple[str | None, asyncio.Queue[dict[str, object]] | None, list[dict[str, object]]]:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None, None, []
            subscriber_id = secrets.token_urlsafe(6)
            queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
            self._subscribers.setdefault(session_id, {})[subscriber_id] = queue
            return subscriber_id, queue, list(session.event_history)

    async def subscribe_ui(self) -> tuple[str, asyncio.Queue[dict[str, object]]]:
        async with self._lock:
            subscriber_id = secrets.token_urlsafe(6)
            queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
            self._ui_subscribers[subscriber_id] = queue
            return subscriber_id, queue

    async def unsubscribe(self, session_id: str, subscriber_id: str) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(session_id)
            if subscribers is None:
                return
            subscribers.pop(subscriber_id, None)

    async def unsubscribe_ui(self, subscriber_id: str) -> None:
        async with self._lock:
            self._ui_subscribers.pop(subscriber_id, None)


def _messages_equal(left: list[SessionMessage], right: list[SessionMessage]) -> bool:
    if len(left) != len(right):
        return False
    for left_item, right_item in zip(left, right):
        if left_item.role != right_item.role or left_item.content != right_item.content:
            return False
    return True
