from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import secrets
from typing import Any

from .adapter import BackendUnavailableError, CodexAdapter
from .attachments import (
    MAX_MESSAGE_ATTACHMENTS,
    AttachmentValidationError,
    store_image_attachment,
)
from .auth import PairingManager
from .desktop_automation import (
    DesktopAutomationSendError,
    DesktopAutomationUnavailableError,
    NullDesktopAutomationClient,
)
from .models import ApprovalRecord, AttachmentRecord, SessionMessage, SessionRecord
from .session_store import SessionStore
from .version import APP_VERSION


ACTIVE_THREAD_STATUSES = {
    "running",
    "waiting",
    "blocked",
    "needs-approval",
    "approval-required",
}
WAITING_THREAD_STATUSES = {
    "waiting",
    "blocked",
    "needs-approval",
    "approval-required",
}
THREAD_QUARANTINE_FILE = "thread-quarantine.json"
BROKEN_THREAD_HISTORY_MESSAGE = "This thread's local Codex history is corrupted, so it has been hidden from the mobile thread list."
MISSING_THREAD_MESSAGE = "This thread is no longer available and has been hidden from the mobile thread list."
BROKEN_THREAD_PATTERNS = (
    "state db discrepancy",
    "failed to open state db",
    "migration 23 was previously applied",
    "find_thread_path_by_id_str_in_subdir",
)
WAITING_STATUS_MESSAGE = "当前会话需要审批，请在手机端处理后继续。"
DEFAULT_INTERACTION_MODE = "default"
PLAN_INTERACTION_MODE = "plan"
PLAN_MODE_PROMPT_BLOCK_START = "<codex-mobile-plan-mode>"
PLAN_MODE_PROMPT_BLOCK_END = "</codex-mobile-plan-mode>"
PLAN_MODE_PROMPT_PREFIX = (
    f"{PLAN_MODE_PROMPT_BLOCK_START}\n"
    "Plan mode is active. Before making changes, propose a concrete plan, then "
    "MUST call requestUserInput and wait for the user's structured choice. "
    "Do not ask for approval only in prose. "
    "Ask exactly one structured question with id 'plan_decision' and at least these options: "
    "'implement the plan', 'revise the plan', and 'cancel'. "
    "If you need extra clarification, add more requestUserInput questions instead of asking only in assistant prose.\n"
    f"{PLAN_MODE_PROMPT_BLOCK_END}"
)
IMAGE_DESKTOP_UNSUPPORTED_MESSAGE = "图片消息请使用计划模式或 app-server 会话。"
DESKTOP_BLOCKED_MESSAGE = "请将 Codex 全屏显示并保持左侧线程栏可见。"
DESKTOP_SWITCHING_MESSAGE = "正在切换到目标线程。"
DESKTOP_ALIGNED_MESSAGE = "已切到目标线程。"
DESKTOP_NOT_FOUND_MESSAGE = "找不到目标线程，请保持 Codex 全屏且左侧线程栏可见。"
DESKTOP_NEW_THREAD_MESSAGE = "正在创建新的桌面线程。"
DESKTOP_ALIGN_REQUIRED_MESSAGE = "请先点击“继续此线程”完成桌面对齐，再发送消息。"
DESKTOP_TARGET_NOT_VISIBLE_MESSAGE = "目标线程不在桌面左侧顶部可见范围，请在 Codex 中让它出现后重试。"
DESKTOP_AMBIGUOUS_TARGET_MESSAGE = "识别到多个相似线程，请让目标线程在左栏中更清晰可见后重试。"
DESKTOP_OCR_UNAVAILABLE_MESSAGE = "桌面 OCR 不可用，请重新安装远控服务依赖。"
DESKTOP_PROJECT_NOT_FOUND_MESSAGE = "未找到对应项目，请保持 Codex 左侧项目列表展开后重试。"
DESKTOP_UIA_UNAVAILABLE_MESSAGE = "桌面无障碍接口不可用，请检查 Windows UIAutomation 组件。"
DESKTOP_VERIFY_FAILED_MESSAGE = "切换后验证失败，请确认桌面已切到目标线程后重试。"


DESKTOP_SERVICE_OFFLINE_MESSAGE = "电脑端桌面同步服务未启动，请打开或重启 Codesk for Windows 后重试。"


@dataclass(slots=True)
class BridgeServiceError(Exception):
    status_code: int
    detail: str


class BridgeService:
    def __init__(
        self,
        *,
        pairing: PairingManager,
        store: SessionStore,
        adapter: CodexAdapter,
        workspace_roots: list[str],
        default_workspace_root: str,
        desktop_automation=None,
    ) -> None:
        self._pairing = pairing
        self._store = store
        self._adapter = adapter
        self._workspace_roots = workspace_roots
        self._default_workspace_root = default_workspace_root
        self._desktop_automation = desktop_automation or NullDesktopAutomationClient()
        self._mirror_task: asyncio.Task[None] | None = None
        self._mirror_stop = asyncio.Event()
        self._mirror_poll_started_at: dict[str, float] = {}
        self._mirror_signatures: dict[str, str] = {}
        self._desktop_bind_tasks: set[asyncio.Task[None]] = set()
        self._attachment_root = Path(default_workspace_root).resolve() / ".logs" / "attachments"
        self._thread_quarantine_path = Path(default_workspace_root).resolve() / ".logs" / THREAD_QUARANTINE_FILE
        self._quarantined_threads = self._load_thread_quarantine()

    async def _desktop_snapshot(self, *, refresh: bool = False) -> dict[str, Any]:
        if not refresh:
            return self._desktop_automation.snapshot()
        try:
            return await asyncio.wait_for(self._desktop_automation.refresh_state(), timeout=3.5)
        except Exception:
            return self._desktop_automation.snapshot()

    async def start_background_tasks(self) -> None:
        await self._desktop_automation.start()
        if self._mirror_task is None:
            self._mirror_stop.clear()
            self._mirror_task = asyncio.create_task(self._mirror_loop(), name="thread-mirror")

    async def stop_background_tasks(self) -> None:
        self._mirror_stop.set()
        if self._mirror_task is not None:
            self._mirror_task.cancel()
            try:
                await self._mirror_task
            except asyncio.CancelledError:
                pass
            self._mirror_task = None
        for task in list(self._desktop_bind_tasks):
            task.cancel()
        for task in list(self._desktop_bind_tasks):
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._desktop_bind_tasks.clear()
        await self._desktop_automation.close()

    async def health_payload(self) -> dict[str, Any]:
        backend = await self._adapter.healthcheck()
        return {
            "ok": True,
            "version": APP_VERSION,
            "backend": backend.backend,
            "backendAvailable": backend.available,
            "backendLastError": backend.last_error,
            "backendSuggestedFix": backend.suggested_fix,
        }

    async def admin_state_payload(self, *, relay: dict[str, Any] | None = None) -> dict[str, Any]:
        sessions = await self._store.list_sessions()
        backend = await self._adapter.healthcheck()
        active = await self._store.get_active_session()
        desktop_snapshot = await self._desktop_snapshot(refresh=True)
        return {
            "version": APP_VERSION,
            "pairCode": self._pairing.current_code,
            "workspaceRoots": self._workspace_roots,
            "sessionCount": len(sessions),
            "activeSessionId": active.get("activeSessionId"),
            "backend": backend.backend,
            "backendAvailable": backend.available,
            "backendLastError": backend.last_error,
            "backendSuggestedFix": backend.suggested_fix,
            "desktopAutomation": desktop_snapshot,
            "relay": relay or {"status": "disabled"},
        }

    def pair_device(self, code: str) -> dict[str, Any]:
        result = self._pairing.issue_token(code)
        if not result.ok or not result.token:
            raise BridgeServiceError(401, result.message or "配对失败。")
        return {"accessToken": result.token}

    def reset_pair_code(self) -> dict[str, Any]:
        return {"pairCode": self._pairing.rotate_code()}

    async def list_workspaces_payload(self) -> dict[str, Any]:
        if self._workspace_roots:
            return {"items": self._workspace_roots}

        threads = await self._list_threads_or_raise()
        items: list[str] = []
        seen: set[str] = set()
        for thread in threads:
            workspace = thread.get("workspace")
            if not isinstance(workspace, str) or not workspace or workspace in seen:
                continue
            seen.add(workspace)
            items.append(workspace)
        if not items:
            items.append(self._default_workspace_root)
        return {"items": items}

    async def list_sessions_payload(self) -> dict[str, Any]:
        await self._sync_running_threads()
        sessions = await self._store.list_sessions()
        active_session_id = await self._active_session_id()
        await self._ensure_active_session(sessions, active_session_id)
        active_session_id = await self._active_session_id()
        desktop_snapshot = await self._desktop_snapshot(refresh=True)
        sessions = await asyncio.gather(
            *[
                self._session_public_payload(
                    item,
                    active_session_id=active_session_id,
                    desktop_snapshot=desktop_snapshot,
                )
                for item in sessions
            ]
        )
        return {"items": sessions}

    async def get_session_payload(self, session_id: str) -> dict[str, Any]:
        session = await self._require_session(session_id)
        return await self._session_public_payload(
            session,
            active_session_id=await self._active_session_id(),
            desktop_snapshot=await self._desktop_snapshot(refresh=True),
        )

    async def get_active_session_payload(self) -> dict[str, Any]:
        active = await self._store.get_active_session()
        session_id = active.get("activeSessionId")
        if isinstance(session_id, str) and session_id:
            await self._require_session(session_id)
        return active

    async def set_active_session_payload(self, session_id: str | None, *, source: str = "ui") -> dict[str, Any]:
        if session_id is None or not session_id.strip():
            return await self._store.set_active_session(None, source=source)
        await self._require_session(session_id)
        return await self._store.set_active_session(session_id, source=source)

    async def upload_attachment_payload(
        self,
        *,
        file_name: str,
        mime_type: str,
        data: bytes,
    ) -> dict[str, Any]:
        try:
            attachment = store_image_attachment(
                root=self._attachment_root,
                file_name=file_name,
                mime_type=mime_type,
                data=data,
            )
        except AttachmentValidationError as exc:
            raise BridgeServiceError(400, exc.message) from exc
        except FileExistsError as exc:  # pragma: no cover - random id collision
            raise BridgeServiceError(500, "附件保存失败，请重试。") from exc
        await self._store.add_attachment(attachment)
        return attachment.to_public_dict(include_local_path=True)

    async def get_attachment_preview_payload(self, attachment_id: str) -> tuple[AttachmentRecord, Path]:
        attachment = await self._store.get_attachment(attachment_id)
        if attachment is None:
            raise BridgeServiceError(404, "附件不存在。")
        path = Path(attachment.local_path)
        if not path.exists() or not path.is_file():
            raise BridgeServiceError(404, "附件文件不存在。")
        return attachment, path

    async def align_desktop_session_payload(self, session_id: str) -> dict[str, Any]:
        session = await self._require_session(session_id)
        await self._store.set_active_session(session_id, source="desktop_align")
        session = await self._require_session(session_id)
        if not await self._desktop_transport_ready_for_session(session):
            blocked_message = self._desktop_blocked_message()
            await self._store.set_desktop_target(session_id, "blocked", blocked_message)
            raise BridgeServiceError(409, blocked_message)
        await self._desktop_focus_session_thread(session)
        await self._store.set_delivery_route(session_id, "desktop_gui")
        return await self._session_public_payload(
            await self._require_session(session_id),
            active_session_id=await self._active_session_id(),
            desktop_snapshot=self._desktop_automation.snapshot(),
        )

    async def create_session_payload(
        self,
        workspace: str,
        prompt: str,
        title: str | None = None,
        *,
        require_desktop: bool = False,
        interaction_mode: str | None = None,
        attachment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self._ensure_workspace_allowed(workspace)
        normalized_mode = self._normalized_interaction_mode(interaction_mode)
        use_desktop = require_desktop and normalized_mode != PLAN_INTERACTION_MODE
        attachments = await self._resolve_attachments(attachment_ids)
        if attachments and use_desktop:
            raise BridgeServiceError(400, IMAGE_DESKTOP_UNSUPPORTED_MESSAGE)
        backend_prompt = self._prompt_for_interaction_mode(
            self._prompt_with_attachment_references(prompt, attachments),
            normalized_mode,
        )

        session_title = title or prompt.splitlines()[0][:40]
        session = await self._store.create_session(
            workspace,
            session_title,
            "" if use_desktop else prompt,
            session_kind="new",
            interaction_mode=normalized_mode,
            plan_state="planning" if normalized_mode == PLAN_INTERACTION_MODE else "none",
            attachments=attachments,
        )
        await self._store.set_active_session(session.session_id, source="create_session")
        await self._publish_session_created(session)
        if use_desktop:
            session = await self._require_session(session.session_id)
            if not await self._desktop_transport_ready_for_session(session):
                blocked_message = self._desktop_blocked_message()
                await self._mark_session_failed(
                    session.session_id,
                    blocked_message,
                )
                raise BridgeServiceError(409, blocked_message)
            try:
                await self._continue_session_via_desktop(session, prompt, allow_fallback=False)
            except BridgeServiceError:
                await self._mark_session_failed(
                    session.session_id,
                    "桌面同步发送失败，请确认 Codex 已全屏且左侧线程栏可见。",
                )
                raise
            return await self._session_public_payload(
                await self._require_session(session.session_id),
                active_session_id=await self._active_session_id(),
                desktop_snapshot=await self._desktop_snapshot(refresh=True),
            )
        try:
            await self._adapter.start_session(session.session_id, backend_prompt)
        except BackendUnavailableError as exc:
            await self._handle_start_failure(session, str(exc) or "Codex 后端当前不可用。", 503)
        except Exception as exc:  # pragma: no cover - defensive
            await self._handle_start_failure(session, f"启动 Codex 会话失败：{exc}", 502)
        return await self._session_public_payload(
            await self._require_session(session.session_id),
            active_session_id=await self._active_session_id(),
            desktop_snapshot=self._desktop_automation.snapshot(),
        )

    async def continue_session_payload(
        self,
        session_id: str,
        content: str,
        *,
        require_desktop: bool = False,
        interaction_mode: str | None = None,
        attachment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        session = await self._require_session(session_id)
        await self._store.set_active_session(session_id, source="continue_session")
        session = await self._require_session(session_id)
        if session.status == "waiting":
            raise BridgeServiceError(400, WAITING_STATUS_MESSAGE)
        normalized_mode = self._normalized_interaction_mode(interaction_mode)
        attachments = await self._resolve_attachments(attachment_ids)
        backend_content = self._prompt_for_interaction_mode(
            self._prompt_with_attachment_references(content, attachments),
            normalized_mode,
        )
        await self._store.set_interaction_state(
            session_id,
            interaction_mode=normalized_mode,
            plan_state="planning" if normalized_mode == PLAN_INTERACTION_MODE else "none",
        )
        if normalized_mode == PLAN_INTERACTION_MODE:
            return await self._continue_session_via_adapter(
                session,
                content,
                adapter_content=backend_content,
                attachments=attachments,
                preserve_delivery_route=bool(
                    self._session_thread_id(session)
                    and session.delivery_route == "desktop_gui"
                ),
            )
        if attachments and require_desktop:
            raise BridgeServiceError(400, IMAGE_DESKTOP_UNSUPPORTED_MESSAGE)
        if require_desktop:
            if not await self._desktop_transport_ready_for_session(session):
                blocked_message = self._desktop_blocked_message()
                await self._store.set_desktop_target(session_id, "blocked", blocked_message)
                raise BridgeServiceError(409, blocked_message)
            if self._session_thread_id(session) and session.desktop_target_state != "aligned":
                await self._store.set_desktop_target(session_id, "blocked", DESKTOP_ALIGN_REQUIRED_MESSAGE)
                raise BridgeServiceError(409, DESKTOP_ALIGN_REQUIRED_MESSAGE)
            return await self._continue_session_via_desktop(session, content, allow_fallback=False)
        if await self._desktop_ready_for_session(session) and session.desktop_target_state == "aligned":
            if attachments:
                raise BridgeServiceError(400, IMAGE_DESKTOP_UNSUPPORTED_MESSAGE)
            return await self._continue_session_via_desktop(session, content)
        return await self._continue_session_via_adapter(
            session,
            content,
            adapter_content=backend_content,
            attachments=attachments,
        )

    async def cancel_session_payload(self, session_id: str) -> dict[str, Any]:
        await self._require_session(session_id)
        await self._store.set_active_session(session_id, source="cancel_session")
        await self._adapter.cancel_session(session_id)
        return {"ok": True}

    async def list_threads_payload(self) -> dict[str, Any]:
        return {"items": await self._list_threads_or_raise()}

    async def get_thread_payload(self, thread_id: str) -> dict[str, Any]:
        quarantined = self._quarantined_threads.get(thread_id)
        if quarantined is not None:
            raise BridgeServiceError(410, str(quarantined.get("message") or BROKEN_THREAD_HISTORY_MESSAGE))
        try:
            return await self._adapter.read_thread(thread_id, self._workspace_roots)
        except BackendUnavailableError as exc:
            quarantined_message = self._quarantine_thread_for_error(thread_id, exc)
            if quarantined_message is not None:
                raise BridgeServiceError(410, quarantined_message) from exc
            raise BridgeServiceError(503, str(exc) or "Codex 后端当前不可用。") from exc
        except RuntimeError as exc:
            quarantined_message = self._quarantine_thread_for_error(thread_id, exc)
            if quarantined_message is not None:
                raise BridgeServiceError(410, quarantined_message) from exc
            raise BridgeServiceError(400, str(exc)) from exc
        except Exception as exc:
            quarantined_message = self._quarantine_thread_for_error(thread_id, exc)
            if quarantined_message is not None:
                raise BridgeServiceError(410, quarantined_message) from exc
            raise BridgeServiceError(502, f"读取线程详情失败：{exc}") from exc

    async def resume_thread_payload(
        self,
        thread_id: str,
        prompt: str | None = None,
        *,
        interaction_mode: str | None = None,
        attachment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized_mode = self._normalized_interaction_mode(interaction_mode)
        attachments = await self._resolve_attachments(attachment_ids)
        quarantined = self._quarantined_threads.get(thread_id)
        if quarantined is not None:
            raise BridgeServiceError(410, str(quarantined.get("message") or BROKEN_THREAD_HISTORY_MESSAGE))
        existing = await self._store.find_session_by_thread_id(thread_id)
        if existing is not None:
            await self._store.set_active_session(existing.session_id, source="resume_thread")
            if (prompt and prompt.strip()) or attachments:
                await self.continue_session_payload(
                    existing.session_id,
                    (prompt or "").strip() or "请查看我发送的图片。",
                    interaction_mode=normalized_mode,
                    attachment_ids=[item.attachment_id for item in attachments],
                )
            return await self._session_public_payload(
                await self._require_session(existing.session_id),
                active_session_id=await self._active_session_id(),
                desktop_snapshot=self._desktop_automation.snapshot(),
            )

        detail: dict[str, Any] | None = None
        if not ((prompt and prompt.strip()) or attachments):
            try:
                summaries = await self._list_threads_or_raise()
            except BridgeServiceError:
                summaries = []
            detail = next(
                (
                    item
                    for item in summaries
                    if isinstance(item, dict) and str(item.get("threadId") or "") == thread_id
                ),
                None,
            )
        if detail is None:
            detail = await self.get_thread_payload(thread_id)
        title = detail.get("title") if isinstance(detail.get("title"), str) else "历史线程"
        workspace = detail.get("workspace")
        if not isinstance(workspace, str) or not workspace:
            raise BridgeServiceError(400, "线程缺少工作区信息，无法恢复。")
        initial_prompt = (prompt or "").strip() or ("请查看我发送的图片。" if attachments else "")
        session = await self._store.create_session(
            workspace,
            title,
            initial_prompt,
            status="running" if initial_prompt else "imported",
            source_thread_id=thread_id,
            session_kind="manual_resume",
            interaction_mode=normalized_mode,
            plan_state="planning" if normalized_mode == PLAN_INTERACTION_MODE else "none",
            attachments=attachments,
        )
        await self._store.set_active_session(session.session_id, source="resume_thread")
        await self._publish_session_created(session)
        if not initial_prompt and not attachments:
            return await self._session_public_payload(
                await self._require_session(session.session_id),
                active_session_id=await self._active_session_id(),
                desktop_snapshot=await self._desktop_snapshot(refresh=True),
            )
        try:
            backend_prompt = None
            if (prompt and prompt.strip()) or attachments:
                prompt_text = (prompt or "").strip() or "请查看我发送的图片。"
                backend_prompt = self._prompt_for_interaction_mode(
                    self._prompt_with_attachment_references(prompt_text, attachments),
                    normalized_mode,
                )
            await self._adapter.resume_thread(session.session_id, thread_id, backend_prompt)
        except BackendUnavailableError as exc:
            await self._handle_start_failure(session, str(exc) or "Codex 后端当前不可用。", 503)
        except RuntimeError as exc:
            await self._handle_start_failure(session, str(exc), 400)
        except Exception as exc:
            await self._handle_start_failure(session, f"恢复历史线程失败：{exc}", 502)
        return await self._session_public_payload(
            await self._require_session(session.session_id),
            active_session_id=await self._active_session_id(),
            desktop_snapshot=self._desktop_automation.snapshot(),
        )

    async def list_approvals_payload(self, session_id: str) -> dict[str, Any]:
        await self._require_session(session_id)
        items = [item.to_public_dict() for item in await self._store.list_approvals(session_id)]
        return {"items": items}

    async def inject_test_approval_payload(
        self,
        session_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        session = await self._require_session(session_id)
        await self._store.set_active_session(session_id, source="inject_test_approval")
        now = datetime.now().astimezone()
        approval = ApprovalRecord(
            approval_id=secrets.token_urlsafe(8),
            session_id=session_id,
            request_id=f"mock-{secrets.token_urlsafe(8)}",
            kind="item/permissions/requestApproval",
            title=title or "测试审批",
            summary=summary or "这是一个测试审批项，用于验证手机端审批显示与处理。",
            payload={
                "method": "item/permissions/requestApproval",
                "params": {
                    "permissions": {"shell": True},
                    "reason": "manual test approval",
                    "mock": True,
                    "resumeStatus": session.status,
                },
            },
            available_actions=["approve", "approve_session", "reject", "cancel"],
            status="pending",
            created_at=now,
        )
        await self._store.add_approval(approval)
        await self._store.set_status(session_id, "waiting", error=WAITING_STATUS_MESSAGE)
        await self._store.publish(
            session_id,
            {
                "type": "approval.required",
                "sessionId": session_id,
                "approval": approval.to_public_dict(),
                "timestamp": now.isoformat(),
            },
        )
        await self._store.publish(
            session_id,
            {
                "type": "session.waiting",
                "sessionId": session_id,
                "message": WAITING_STATUS_MESSAGE,
                "timestamp": now.isoformat(),
            },
        )
        return approval.to_public_dict()

    async def resolve_approval_payload(
        self,
        session_id: str,
        approval_id: str,
        action: str,
        *,
        answers: list[dict[str, Any]] | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        await self._require_session(session_id)
        await self._store.set_active_session(session_id, source="resolve_approval")
        existing = await self._store.get_approval(session_id, approval_id)
        if existing is None:
            raise BridgeServiceError(404, "审批不存在。")
        if self._is_mock_approval(existing):
            return await self._resolve_mock_approval(session_id, approval_id, action)
        try:
            approval = await self._adapter.resolve_approval(
                session_id,
                approval_id,
                action,
                answers=answers,
                content=content,
            )
        except BackendUnavailableError as exc:
            raise BridgeServiceError(503, str(exc) or "Codex 后端当前不可用。") from exc
        except RuntimeError as exc:
            raise BridgeServiceError(400, str(exc)) from exc
        return approval.to_public_dict()

    async def _resolve_mock_approval(self, session_id: str, approval_id: str, action: str) -> dict[str, Any]:
        approval = await self._store.resolve_approval(session_id, approval_id, action)
        if approval is None:
            raise BridgeServiceError(404, "审批不存在。")
        await self._store.set_status(session_id, self._mock_approval_resume_status(approval), error=None)
        await self._store.publish(
            session_id,
            {
                "type": "approval.resolved",
                "sessionId": session_id,
                "approvalId": approval_id,
                "requestId": approval.request_id,
                "resolution": action,
                "timestamp": datetime.now().astimezone().isoformat(),
            },
        )
        return approval.to_public_dict()

    async def _require_session(self, session_id: str) -> SessionRecord:
        session = await self._store.get_session(session_id)
        if session is None:
            raise BridgeServiceError(404, "会话不存在。")
        return session

    def _is_mock_approval(self, approval: ApprovalRecord) -> bool:
        params = approval.payload.get("params") if isinstance(approval.payload, dict) else None
        return bool(
            isinstance(params, dict)
            and params.get("mock") is True
            and isinstance(approval.request_id, str)
            and approval.request_id.startswith("mock-")
        )

    def _mock_approval_resume_status(self, approval: ApprovalRecord) -> str:
        params = approval.payload.get("params") if isinstance(approval.payload, dict) else None
        if isinstance(params, dict):
            resume_status = params.get("resumeStatus")
            if isinstance(resume_status, str) and resume_status:
                return resume_status
        return "completed"

    def _ensure_workspace_allowed(self, workspace: str) -> None:
        if not self._workspace_roots:
            return
        if workspace not in self._workspace_roots:
            raise BridgeServiceError(400, "工作区不在白名单内。")

    async def _list_threads_or_raise(self) -> list[dict[str, Any]]:
        try:
            threads = await self._adapter.list_threads(self._workspace_roots)
            return self._filter_quarantined_threads(threads)
        except BackendUnavailableError as exc:
            raise BridgeServiceError(503, str(exc) or "Codex 后端当前不可用。") from exc
        except RuntimeError as exc:
            raise BridgeServiceError(400, str(exc)) from exc
        except Exception as exc:
            raise BridgeServiceError(502, f"加载线程库失败：{exc}") from exc

    async def _sync_running_threads(self) -> None:
        threads = await self._list_threads_or_raise()
        active_session_id = await self._active_session_id()
        for thread in threads:
            thread_id = thread.get("threadId")
            if not isinstance(thread_id, str) or not thread_id:
                continue
            if not self._thread_is_active(thread):
                continue

            existing = await self._store.find_session_by_thread_id(thread_id)
            if existing is not None:
                await self._sync_session_status_from_thread(existing.session_id, thread)
                continue

            workspace = thread.get("workspace")
            if not isinstance(workspace, str) or not workspace:
                continue
            title = thread.get("title") if isinstance(thread.get("title"), str) and thread.get("title") else "运行中线程"
            session = await self._store.create_session(
                workspace,
                title,
                status=self._session_status_from_thread(thread),
                source_thread_id=thread_id,
                session_kind="auto_adopted",
            )
            await self._publish_session_created(session)
            try:
                await self._adapter.resume_thread(session.session_id, thread_id)
                await self._sync_session_status_from_thread(session.session_id, thread)
                if active_session_id is None:
                    await self._store.set_active_session(session.session_id, source="auto_adopted")
                    active_session_id = session.session_id
            except BackendUnavailableError as exc:
                await self._mark_session_failed(session.session_id, str(exc) or "Codex 后端当前不可用。")
                raise BridgeServiceError(503, str(exc) or "Codex 后端当前不可用。") from exc
            except RuntimeError as exc:
                await self._mark_session_failed(session.session_id, str(exc))
            except Exception as exc:  # pragma: no cover - defensive
                await self._mark_session_failed(session.session_id, f"自动接管线程失败：{exc}")

    async def _sync_session_status_from_thread(self, session_id: str, thread: dict[str, Any]) -> None:
        summary = thread.get("preview") if isinstance(thread.get("preview"), str) else None
        status = self._session_status_from_thread(thread)
        if status == "waiting":
            await self._store.set_status(session_id, "waiting", summary=summary, error=WAITING_STATUS_MESSAGE)
            return
        await self._store.set_status(session_id, status, summary=summary, error=None)

    async def _publish_session_created(self, session: SessionRecord) -> None:
        await self._store.publish(
            session.session_id,
            {
                "type": "session.created",
                "sessionId": session.session_id,
                "title": session.title,
                "sessionKind": session.session_kind,
                "timestamp": session.created_at.isoformat(),
            },
        )

    async def _publish_user_message(
        self,
        session_id: str,
        content: str,
        *,
        attachments: list[AttachmentRecord] | None = None,
    ) -> None:
        session = await self._require_session(session_id)
        await self._store.publish(
            session_id,
            {
                "type": "message.completed",
                "sessionId": session_id,
                "role": "user",
                "content": content,
                "attachments": [item.to_public_dict() for item in (attachments or [])],
                "timestamp": session.updated_at.isoformat(),
            },
        )

    async def _active_session_id(self) -> str | None:
        active = await self._store.get_active_session()
        session_id = active.get("activeSessionId")
        return session_id if isinstance(session_id, str) and session_id else None

    async def _ensure_active_session(self, sessions: list[SessionRecord], active_session_id: str | None) -> None:
        if active_session_id and any(item.session_id == active_session_id for item in sessions):
            return
        if not sessions:
            return
        preferred = next((item for item in sessions if item.status in {"running", "waiting"}), None)
        target = preferred or sessions[0]
        await self._store.set_active_session(target.session_id, source="auto_select")

    async def _continue_session_via_adapter(
        self,
        session: SessionRecord,
        content: str,
        *,
        record_user_message: bool = True,
        optimistic_cleanup: bool = False,
        adapter_content: str | None = None,
        attachments: list[AttachmentRecord] | None = None,
        preserve_delivery_route: bool = False,
    ) -> dict[str, Any]:
        await self._store.set_delivery_route(
            session.session_id,
            "desktop_gui" if preserve_delivery_route else "app_server",
        )
        try:
            await self._adapter.continue_session(session.session_id, adapter_content or content)
        except BackendUnavailableError as exc:
            if optimistic_cleanup:
                await self._store.remove_last_message(session.session_id, "user", content)
            await self._handle_runtime_failure(session.session_id, str(exc) or "Codex 后端当前不可用。", 503)
        except RuntimeError as exc:
            if optimistic_cleanup:
                await self._store.remove_last_message(session.session_id, "user", content)
            raise BridgeServiceError(400, str(exc)) from exc
        except Exception as exc:
            if optimistic_cleanup:
                await self._store.remove_last_message(session.session_id, "user", content)
            await self._handle_runtime_failure(session.session_id, f"继续会话失败：{exc}", 502)
        if record_user_message:
            await self._store.add_message(session.session_id, "user", content, attachments=attachments)
            await self._publish_user_message(session.session_id, content, attachments=attachments)
        if preserve_delivery_route and self._session_thread_id(session):
            self._mirror_signatures.pop(session.session_id, None)
            asyncio.create_task(self._mirror_active_session_once())
        return {"ok": True}

    async def _continue_session_via_desktop(
        self,
        session: SessionRecord,
        content: str,
        *,
        allow_fallback: bool = True,
    ) -> dict[str, Any]:
        await self._store.set_status(session.session_id, "running", error=None)
        await self._store.set_delivery_route(session.session_id, "desktop_gui")
        bind_baseline: dict[str, str] | None = None
        try:
            if self._session_thread_id(session):
                if session.desktop_target_state != "aligned":
                    await self._store.set_desktop_target(
                        session.session_id,
                        "blocked",
                        DESKTOP_ALIGN_REQUIRED_MESSAGE,
                    )
                    raise BridgeServiceError(409, DESKTOP_ALIGN_REQUIRED_MESSAGE)
            else:
                bind_baseline = await self._desktop_thread_snapshot()
                await self._desktop_start_new_thread(session)
        except BridgeServiceError:
            raise
        await self._store.add_message(session.session_id, "user", content)
        await self._publish_user_message(session.session_id, content)
        try:
            await self._desktop_automation.send_text(content, submit=True)
        except DesktopAutomationUnavailableError:
            blocked_message = self._desktop_blocked_message()
            await self._store.set_desktop_target(session.session_id, "blocked", blocked_message)
            if not allow_fallback:
                await self._store.remove_last_message(session.session_id, "user", content)
                raise BridgeServiceError(409, blocked_message) from None
            session = await self._require_session(session.session_id)
            return await self._continue_session_via_adapter(
                session,
                content,
                record_user_message=False,
                optimistic_cleanup=True,
            )
        except DesktopAutomationSendError as exc:
            await self._store.remove_last_message(session.session_id, "user", content)
            error_code = getattr(exc, "code", None)
            if error_code in {"codex_window_not_found", "window_not_locked", "window_missing", "window_not_visible", "focus_failed"}:
                message = str(exc) or self._desktop_blocked_message()
                await self._store.set_desktop_target(session.session_id, "blocked", message)
                raise BridgeServiceError(409, message) from exc
            await self._handle_runtime_failure(session.session_id, f"桌面同步发送失败：{exc}", 502)
        if bind_baseline is not None:
            self._schedule_desktop_thread_bind(session.session_id, bind_baseline)
        return {"ok": True}

    async def _desktop_send_ready_for_session(self, session: SessionRecord) -> bool:
        if session.session_id != await self._active_session_id():
            return False
        snapshot = await self._desktop_snapshot(refresh=True)
        return bool(
            snapshot.get("available")
            and snapshot.get("connected")
            and snapshot.get("authenticated")
            and (snapshot.get("codexWindowControllable") or snapshot.get("codexWindowLocked"))
        )

    async def _desktop_transport_ready_for_session(self, session: SessionRecord) -> bool:
        if session.session_id != await self._active_session_id():
            return False
        snapshot = await self._desktop_snapshot(refresh=True)
        return bool(
            snapshot.get("available")
            and snapshot.get("connected")
            and snapshot.get("authenticated")
        )

    def _desktop_blocked_message(self) -> str:
        snapshot = self._desktop_automation.snapshot()
        for key in ("desktopControlMessage", "lastError"):
            value = snapshot.get(key)
            if isinstance(value, str) and value.strip():
                return self._friendly_desktop_error_message(value.strip())
        return DESKTOP_BLOCKED_MESSAGE

    def _friendly_desktop_error_message(self, message: str) -> str:
        lowered = message.lower()
        if (
            "10061" in lowered
            or "connection refused" in lowered
            or "actively refused" in lowered
            or "unable to connect to the remote server" in lowered
            or "desktop automation is not connected" in lowered
            or "目标计算机积极拒绝" in message
            or "由于目标计算机积极拒绝" in message
        ):
            return DESKTOP_SERVICE_OFFLINE_MESSAGE
        return message

    async def _desktop_ready_for_session(self, session: SessionRecord) -> bool:
        if not self._session_thread_id(session):
            return False
        return await self._desktop_send_ready_for_session(session)

    def _schedule_desktop_thread_bind(self, session_id: str, baseline: dict[str, str] | None = None) -> None:
        task = asyncio.create_task(
            self._bind_desktop_session_to_latest_thread(session_id, baseline or {}),
            name=f"desktop-thread-bind:{session_id}",
        )
        self._desktop_bind_tasks.add(task)
        task.add_done_callback(self._desktop_bind_tasks.discard)

    def _schedule_desktop_thread_alignment(self, session_id: str) -> None:
        task = asyncio.create_task(
            self._align_desktop_session_in_background(session_id),
            name=f"desktop-thread-align:{session_id}",
        )
        self._desktop_bind_tasks.add(task)
        task.add_done_callback(self._desktop_bind_tasks.discard)

    async def _align_desktop_session_in_background(self, session_id: str) -> None:
        session = await self._store.get_session(session_id)
        if session is None or not self._session_thread_id(session):
            return
        try:
            await self._desktop_focus_session_thread(session)
        except BridgeServiceError:
            return

    async def _bind_desktop_session_to_latest_thread(self, session_id: str, baseline: dict[str, str]) -> None:
        for attempt in range(8):
            await asyncio.sleep(0.6 if attempt == 0 else 1.0)
            session = await self._store.get_session(session_id)
            if session is None or self._session_thread_id(session):
                return
            try:
                threads = await self._list_threads_or_raise()
            except Exception:
                continue
            candidate = self._desktop_bind_candidate(threads, baseline)
            if candidate is None:
                continue
            thread_id = str(candidate["threadId"])
            try:
                await self._adapter.resume_thread(session_id, thread_id)
                await self._store.set_delivery_route(session_id, "desktop_gui")
                await self._store.set_desktop_target(session_id, "aligned", DESKTOP_ALIGNED_MESSAGE)
                self._mirror_signatures.pop(session_id, None)
                await self._mirror_active_session_once()
                return
            except Exception:
                continue

    async def _session_public_payload(
        self,
        session: SessionRecord,
        *,
        active_session_id: str | None,
        desktop_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        payload = session.to_public_dict()
        is_active = session.session_id == active_session_id
        desktop_ready = bool(
            is_active
            and self._session_thread_id(session)
            and desktop_snapshot.get("available")
            and desktop_snapshot.get("connected")
            and desktop_snapshot.get("authenticated")
            and (desktop_snapshot.get("codexWindowControllable") or desktop_snapshot.get("codexWindowLocked"))
        )
        active_approvals = await self._store.list_approvals(session.session_id, active_only=True)
        pending_source: str | None = None
        if active_approvals:
            pending_source = "store"
        elif (
            is_active
            and session.status == "waiting"
            and self._session_thread_id(session)
            and (session.delivery_route == "desktop_gui" or desktop_ready)
        ):
            pending_source = "desktop"
        payload["isActive"] = is_active
        payload["desktopAutomationReady"] = desktop_ready
        payload["pendingApprovalSource"] = pending_source
        payload["desktopApprovalControllable"] = bool(
            pending_source == "desktop"
            and desktop_snapshot.get("previewSupported")
            and desktop_snapshot.get("available")
            and desktop_snapshot.get("connected")
            and desktop_snapshot.get("authenticated")
            and (desktop_snapshot.get("codexWindowControllable") or desktop_snapshot.get("codexWindowLocked"))
        )
        return payload

    async def _desktop_thread_snapshot(self) -> dict[str, str]:
        try:
            threads = await self._list_threads_or_raise()
        except BridgeServiceError:
            return {}
        snapshot: dict[str, str] = {}
        for item in threads:
            thread_id = item.get("threadId")
            if isinstance(thread_id, str) and thread_id:
                snapshot[thread_id] = str(item.get("updatedAt") or "")
        return snapshot

    def _desktop_bind_candidate(
        self,
        threads: list[dict[str, Any]],
        baseline: dict[str, str],
    ) -> dict[str, Any] | None:
        for item in threads:
            thread_id = item.get("threadId")
            if not isinstance(thread_id, str) or not thread_id:
                continue
            updated_at = str(item.get("updatedAt") or "")
            if thread_id not in baseline or baseline.get(thread_id) != updated_at:
                return item
        return None

    async def _desktop_focus_session_thread(
        self,
        session: SessionRecord,
        *,
        target: dict[str, Any] | None = None,
    ) -> None:
        thread_id = self._session_thread_id(session)
        if not thread_id:
            await self._store.set_desktop_target(session.session_id, "unbound", "当前会话尚未绑定线程。")
            raise BridgeServiceError(409, "当前会话尚未绑定线程。")
        resolved_target = target
        if resolved_target is None:
            threads = await self._list_threads_or_raise()
            resolved_target = next(
                (
                    item
                    for item in threads
                    if isinstance(item.get("threadId"), str) and str(item.get("threadId")) == thread_id
                ),
                None,
            )
        if resolved_target is None:
            await self._store.set_desktop_target(session.session_id, "not_found", DESKTOP_NOT_FOUND_MESSAGE)
            raise BridgeServiceError(409, DESKTOP_NOT_FOUND_MESSAGE)
        await self._store.set_desktop_target(session.session_id, "switching", DESKTOP_SWITCHING_MESSAGE)
        try:
            target_workspace = (
                resolved_target.get("workspace")
                if isinstance(resolved_target.get("workspace"), str) and resolved_target.get("workspace")
                else session.workspace
            )
            ack = await self._desktop_automation.send_command(
                {
                    "type": "codex.thread.focus",
                    "threadId": thread_id,
                    "workspace": target_workspace,
                    "title": resolved_target.get("title"),
                },
                expect_ack=True,
                timeout=12.0,
            )
        except DesktopAutomationUnavailableError as exc:
            blocked_message = self._desktop_blocked_message()
            await self._store.set_desktop_target(session.session_id, "blocked", blocked_message)
            raise BridgeServiceError(409, blocked_message) from exc
        except DesktopAutomationSendError as exc:
            error_code = getattr(exc, "code", None)
            if error_code in {"codex_window_not_found", "window_not_locked", "window_missing", "window_not_visible", "focus_failed"}:
                message = str(exc) or self._desktop_blocked_message()
                await self._store.set_desktop_target(session.session_id, "blocked", message)
                raise BridgeServiceError(409, message) from exc
            if error_code == "uia_unavailable":
                message = str(exc) or DESKTOP_UIA_UNAVAILABLE_MESSAGE
                await self._store.set_desktop_target(session.session_id, "blocked", message)
            elif error_code == "project_not_found":
                message = str(exc) or DESKTOP_PROJECT_NOT_FOUND_MESSAGE
                await self._store.set_desktop_target(session.session_id, "not_found", message)
            elif error_code in {"ambiguous_target", "ambiguous_project"}:
                message = str(exc) or DESKTOP_AMBIGUOUS_TARGET_MESSAGE
                await self._store.set_desktop_target(session.session_id, "not_found", message)
            elif error_code in {"target_not_visible", "invalid_message"}:
                message = str(exc) or DESKTOP_TARGET_NOT_VISIBLE_MESSAGE
                await self._store.set_desktop_target(session.session_id, "not_found", message)
            elif error_code == "verify_failed":
                message = str(exc) or DESKTOP_VERIFY_FAILED_MESSAGE
                await self._store.set_desktop_target(session.session_id, "blocked", message)
            else:
                message = DESKTOP_NOT_FOUND_MESSAGE
                await self._store.set_desktop_target(session.session_id, "not_found", message)
            raise BridgeServiceError(409, message) from exc
        confidence = _float_or_none(ack.get("confidence") if isinstance(ack, dict) else None)
        matched_text = ack.get("matchedText") if isinstance(ack, dict) and isinstance(ack.get("matchedText"), str) else None
        await self._store.set_desktop_target(
            session.session_id,
            "aligned",
            DESKTOP_ALIGNED_MESSAGE,
            confidence=confidence,
            matched_text=matched_text,
        )

    async def _desktop_start_new_thread(self, session: SessionRecord) -> None:
        await self._store.set_desktop_target(session.session_id, "switching", DESKTOP_NEW_THREAD_MESSAGE)
        try:
            await self._desktop_automation.send_command(
                {
                    "type": "codex.thread.new",
                    "sessionId": session.session_id,
                    "workspace": session.workspace,
                },
                expect_ack=True,
                timeout=10.0,
            )
        except DesktopAutomationUnavailableError as exc:
            blocked_message = self._desktop_blocked_message()
            await self._store.set_desktop_target(session.session_id, "blocked", blocked_message)
            raise BridgeServiceError(409, blocked_message) from exc
        except DesktopAutomationSendError as exc:
            error_code = getattr(exc, "code", None)
            if error_code == "uia_unavailable":
                message = str(exc) or DESKTOP_UIA_UNAVAILABLE_MESSAGE
            elif error_code == "new_thread_button_not_found":
                message = str(exc) or DESKTOP_BLOCKED_MESSAGE
            elif error_code == "verify_failed":
                message = str(exc) or DESKTOP_VERIFY_FAILED_MESSAGE
            else:
                message = str(exc) or DESKTOP_BLOCKED_MESSAGE
            await self._store.set_desktop_target(session.session_id, "blocked", message)
            raise BridgeServiceError(409, message) from exc
        await self._store.set_desktop_target(session.session_id, "aligned", DESKTOP_ALIGNED_MESSAGE)

    async def _mirror_loop(self) -> None:
        while not self._mirror_stop.is_set():
            try:
                delay = await self._mirror_active_session_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                delay = 1.5
            try:
                await asyncio.wait_for(self._mirror_stop.wait(), timeout=max(0.2, delay))
            except asyncio.TimeoutError:
                continue

    async def _mirror_active_session_once(self) -> float:
        active_session_id = await self._active_session_id()
        if not active_session_id:
            return 1.0
        session = await self._store.get_session(active_session_id)
        if session is None:
            return 1.0
        thread_id = self._session_thread_id(session)
        if not thread_id:
            return 1.0

        interval = self._thread_poll_interval(session)
        loop = asyncio.get_running_loop()
        now = loop.time()
        previous = self._mirror_poll_started_at.get(active_session_id)
        if previous is not None:
            remaining = interval - (now - previous)
            if remaining > 0:
                return remaining
        self._mirror_poll_started_at = {active_session_id: now}

        try:
            detail = await self._adapter.read_thread(thread_id, self._workspace_roots)
        except BackendUnavailableError:
            return interval
        except RuntimeError as exc:
            quarantined_message = self._quarantine_thread_for_error(thread_id, exc)
            if quarantined_message is not None:
                await self._store.set_status(active_session_id, "failed", error=quarantined_message)
                return max(interval, 5.0)
            return interval
        except Exception:
            return interval

        signature = self._thread_signature(detail)
        if self._mirror_signatures.get(active_session_id) == signature:
            return interval

        mirrored_at = datetime.now().astimezone()
        status = self._mirror_status_from_thread(detail, session)
        changed, updated = await self._store.apply_thread_mirror(
            active_session_id,
            title=self._thread_title(detail, session),
            status=status,
            summary=self._thread_summary(detail, session),
            error=self._mirror_error_for_status(detail, status, session),
            messages=self._mirror_messages_from_thread(detail),
            synced_at=mirrored_at,
        )
        self._mirror_signatures[active_session_id] = signature
        if changed and updated is not None:
            await self._store.publish(
                active_session_id,
                {
                    "type": "thread.mirrored",
                    "sessionId": active_session_id,
                    "threadId": thread_id,
                    "status": status,
                    "timestamp": mirrored_at.isoformat(),
                },
            )
        return interval

    def _thread_poll_interval(self, session: SessionRecord) -> float:
        if session.status in {"running", "waiting"}:
            return 1.0
        return 2.5

    def _thread_signature(self, detail: dict[str, Any]) -> str:
        payload = {
            "threadId": detail.get("threadId"),
            "title": detail.get("title"),
            "status": detail.get("status"),
            "preview": detail.get("preview"),
            "turns": detail.get("turns"),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha1(encoded).hexdigest()

    def _thread_title(self, detail: dict[str, Any], session: SessionRecord) -> str:
        title = detail.get("title")
        if isinstance(title, str) and title.strip():
            return title
        return session.title

    def _thread_summary(self, detail: dict[str, Any], session: SessionRecord) -> str | None:
        preview = detail.get("preview")
        if isinstance(preview, str):
            return preview
        return session.result_summary

    def _mirror_messages_from_thread(self, detail: dict[str, Any]) -> list[SessionMessage]:
        messages: list[SessionMessage] = []
        for turn in detail.get("turns", []):
            if not isinstance(turn, dict):
                continue
            commentary: list[str] = []
            assistant: list[str] = []
            for item in turn.get("items", []):
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type") or "")
                if item_type == "userMessage":
                    text = self._message_text_from_item(item)
                    if text:
                        messages.append(
                            SessionMessage(
                                role="user",
                                content=text,
                                created_at=datetime.now().astimezone(),
                            )
                        )
                    continue
                if item_type != "agentMessage":
                    continue
                text = self._message_text_from_item(item)
                if not text:
                    continue
                phase = str(item.get("phase") or "").strip().lower()
                if phase == "commentary":
                    commentary.append(text)
                else:
                    assistant.append(text)
            if assistant:
                for text in assistant:
                    messages.append(
                        SessionMessage(
                            role="assistant",
                            content=text,
                            created_at=datetime.now().astimezone(),
                        )
                    )
            elif commentary:
                messages.append(
                    SessionMessage(
                        role="assistant",
                        content="\n\n".join(commentary),
                        created_at=datetime.now().astimezone(),
                    )
                )
        return messages

    def _message_text_from_item(self, item: dict[str, Any]) -> str:
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            return self._strip_plan_mode_prompt(text.strip())
        content = item.get("content")
        if isinstance(content, list):
            parts = [
                str(part.get("text") or "").strip()
                for part in content
                if isinstance(part, dict) and str(part.get("text") or "").strip()
            ]
            if parts:
                return self._strip_plan_mode_prompt("\n".join(parts))
        return ""

    def _mirror_status_from_thread(self, detail: dict[str, Any], session: SessionRecord) -> str:
        status = self._normalized_thread_status(detail)
        if status in WAITING_THREAD_STATUSES:
            return "waiting"
        if status == "running":
            return "running"
        if status in {"cancelled", "canceled", "interrupted"}:
            return "cancelled"
        if status in {"failed", "error"}:
            return "failed"
        if status == "completed":
            return "completed"
        if status in {"idle", "notloaded", "not-loaded", ""}:
            if self._thread_has_turns(detail) or session.status in {"running", "waiting", "completed", "failed", "cancelled"}:
                return "completed"
            return "imported"
        if self._thread_has_turns(detail):
            return "completed"
        return session.status or "imported"

    def _mirror_error_for_status(
        self,
        detail: dict[str, Any],
        status: str,
        session: SessionRecord,
    ) -> str | None:
        if status == "waiting":
            return WAITING_STATUS_MESSAGE
        if status == "failed":
            for turn in reversed(detail.get("turns", [])):
                if not isinstance(turn, dict):
                    continue
                error = turn.get("error")
                if isinstance(error, str) and error.strip():
                    return error
            return session.last_error
        return None

    def _thread_has_turns(self, detail: dict[str, Any]) -> bool:
        turns = detail.get("turns")
        return isinstance(turns, list) and any(isinstance(turn, dict) for turn in turns)

    def _session_thread_id(self, session: SessionRecord) -> str | None:
        thread_id = session.source_thread_id or session.backend_session_id
        return thread_id if isinstance(thread_id, str) and thread_id else None

    def _normalized_interaction_mode(self, interaction_mode: str | None) -> str:
        value = str(interaction_mode or DEFAULT_INTERACTION_MODE).strip().lower()
        return PLAN_INTERACTION_MODE if value == PLAN_INTERACTION_MODE else DEFAULT_INTERACTION_MODE

    async def _resolve_attachments(self, attachment_ids: list[str] | None) -> list[AttachmentRecord]:
        ids = [str(item).strip() for item in (attachment_ids or []) if str(item).strip()]
        if not ids:
            return []
        if len(ids) > MAX_MESSAGE_ATTACHMENTS:
            raise BridgeServiceError(400, "单条消息最多支持 4 张图片。")
        unique_ids = list(dict.fromkeys(ids))
        attachments = await self._store.get_attachments(unique_ids)
        if len(attachments) != len(unique_ids):
            raise BridgeServiceError(400, "图片附件不存在或已失效。")
        return attachments

    def _prompt_with_attachment_references(self, content: str, attachments: list[AttachmentRecord]) -> str:
        if not attachments:
            return content
        request = content.strip() or "请查看我发送的图片。"
        lines = ["# Files mentioned by the user:"]
        for attachment in attachments:
            lines.append(f"## {attachment.file_name}: {attachment.local_path}")
        lines.extend(["", "## My request for Codex:", request])
        return "\n".join(lines)

    def _prompt_for_interaction_mode(self, content: str, interaction_mode: str) -> str:
        if interaction_mode != PLAN_INTERACTION_MODE:
            return content
        return f"{content}\n\n{PLAN_MODE_PROMPT_PREFIX}"

    def _strip_plan_mode_prompt(self, content: str) -> str:
        start = content.find(PLAN_MODE_PROMPT_BLOCK_START)
        end = content.find(PLAN_MODE_PROMPT_BLOCK_END)
        if start == -1 or end == -1 or end < start:
            return content
        end += len(PLAN_MODE_PROMPT_BLOCK_END)
        stripped = f"{content[:start].rstrip()}\n{content[end:].lstrip()}".strip()
        return stripped or content[:start].strip()

    async def _mark_session_failed(self, session_id: str, message: str) -> None:
        session = await self._require_session(session_id)
        updated = await self._store.set_status(session_id, "failed", error=message)
        await self._store.publish(
            session_id,
            {
                "type": "session.failed",
                "sessionId": session_id,
                "message": message,
                "timestamp": (updated or session).updated_at.isoformat(),
            },
        )

    def _thread_is_active(self, thread: dict[str, Any]) -> bool:
        return self._normalized_thread_status(thread) in ACTIVE_THREAD_STATUSES

    def _session_status_from_thread(self, thread: dict[str, Any]) -> str:
        status = self._normalized_thread_status(thread)
        if status in WAITING_THREAD_STATUSES:
            return "waiting"
        if status == "running":
            return "running"
        return "imported"

    def _normalized_thread_status(self, thread: dict[str, Any]) -> str:
        status = thread.get("status")
        if isinstance(status, str):
            return status.strip().lower()
        return ""

    async def _handle_start_failure(self, session: SessionRecord, message: str, status_code: int) -> None:
        updated = await self._store.set_status(session.session_id, "failed", error=message)
        await self._store.publish(
            session.session_id,
            {
                "type": "session.failed",
                "sessionId": session.session_id,
                "message": message,
                "timestamp": (updated or session).updated_at.isoformat(),
            },
        )
        raise BridgeServiceError(status_code, message)

    async def _handle_runtime_failure(self, session_id: str, message: str, status_code: int) -> None:
        session = await self._require_session(session_id)
        updated = await self._store.set_status(session_id, "failed", error=message)
        await self._store.publish(
            session_id,
            {
                "type": "session.failed",
                "sessionId": session_id,
                "message": message,
                "timestamp": (updated or session).updated_at.isoformat(),
            },
        )
        raise BridgeServiceError(status_code, message)

    def _load_thread_quarantine(self) -> dict[str, dict[str, Any]]:
        try:
            if not self._thread_quarantine_path.exists():
                return {}
            payload = json.loads(self._thread_quarantine_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        quarantined: dict[str, dict[str, Any]] = {}
        for thread_id, meta in payload.items():
            if not isinstance(thread_id, str) or not thread_id:
                continue
            if not isinstance(meta, dict):
                continue
            quarantined[thread_id] = {
                "message": str(meta.get("message") or BROKEN_THREAD_HISTORY_MESSAGE),
                "reason": str(meta.get("reason") or "unknown"),
                "title": str(meta.get("title") or ""),
                "workspace": str(meta.get("workspace") or ""),
                "updatedAt": str(meta.get("updatedAt") or ""),
            }
        return quarantined

    def _save_thread_quarantine(self) -> None:
        try:
            self._thread_quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._thread_quarantine_path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(self._quarantined_threads, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp_path.replace(self._thread_quarantine_path)
        except Exception:
            return None

    def _filter_quarantined_threads(self, threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        changed = False
        for thread in threads:
            thread_id = thread.get("threadId")
            if not isinstance(thread_id, str) or not thread_id:
                continue
            if thread_id in self._quarantined_threads:
                continue
            path_value = thread.get("path")
            if isinstance(path_value, str) and path_value and not Path(path_value).exists():
                self._quarantine_thread(
                    thread_id,
                    message=MISSING_THREAD_MESSAGE,
                    reason="missing_path",
                    thread=thread,
                )
                changed = True
                continue
            filtered.append(thread)
        if changed:
            self._save_thread_quarantine()
        return filtered

    def _quarantine_thread_for_error(self, thread_id: str, exc: Exception) -> str | None:
        reason, message = self._classify_thread_error(exc)
        if reason is None or message is None:
            return None
        self._quarantine_thread(thread_id, message=message, reason=reason)
        self._save_thread_quarantine()
        return message

    def _quarantine_thread(
        self,
        thread_id: str,
        *,
        message: str,
        reason: str,
        thread: dict[str, Any] | None = None,
    ) -> None:
        title = ""
        workspace = ""
        updated_at = ""
        if isinstance(thread, dict):
            title = str(thread.get("title") or "")
            workspace = str(thread.get("workspace") or "")
            updated_at = str(thread.get("updatedAt") or "")
        self._quarantined_threads[thread_id] = {
            "message": message,
            "reason": reason,
            "title": title,
            "workspace": workspace,
            "updatedAt": updated_at,
        }

    def _classify_thread_error(self, exc: Exception) -> tuple[str | None, str | None]:
        message = str(exc or "").strip()
        if not message:
            return None, None
        normalized = message.lower()
        if any(pattern in normalized for pattern in BROKEN_THREAD_PATTERNS):
            return "history_corrupted", BROKEN_THREAD_HISTORY_MESSAGE
        if (
            "未找到对应线程" in message
            or "thread not found" in normalized
            or "no such thread" in normalized
            or "not found" in normalized and "thread" in normalized
        ):
            return "missing", MISSING_THREAD_MESSAGE
        return None, None


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
