from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import ApprovalRecord
from .session_store import SessionStore
from .version import APP_NAME, APP_VERSION


APP_SERVER_STREAM_LIMIT = 16 * 1024 * 1024
APPROVAL_REQUEST_METHODS = {
    "item/commandExecution/requestApproval",
    "item/fileChange/requestApproval",
    "item/permissions/requestApproval",
    "item/tool/requestUserInput",
    "mcpServer/elicitation/request",
    "execCommandApproval",
    "applyPatchApproval",
}


@dataclass(slots=True)
class BackendHealth:
    backend: str
    available: bool
    last_error: str | None = None
    suggested_fix: str | None = None


@dataclass(slots=True)
class CommandResolution:
    command: list[str]
    preflight_error: str | None = None
    suggested_fix: str | None = None


class BackendUnavailableError(RuntimeError):
    pass


class CodexAdapter(ABC):
    backend_name = "unknown"

    def __init__(self, store: SessionStore) -> None:
        self._store = store

    @abstractmethod
    async def start_session(self, session_id: str, prompt: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def continue_session(self, session_id: str, prompt: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def cancel_session(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_threads(self, workspace_roots: list[str]) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def read_thread(self, thread_id: str, workspace_roots: list[str]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def resume_thread(self, session_id: str, thread_id: str, prompt: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def resolve_approval(
        self,
        session_id: str,
        approval_id: str,
        action: str,
        *,
        answers: list[dict[str, Any]] | None = None,
        content: str | None = None,
    ) -> ApprovalRecord:
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> BackendHealth:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class DemoCodexAdapter(CodexAdapter):
    backend_name = "demo"

    def __init__(self, store: SessionStore) -> None:
        super().__init__(store)
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start_session(self, session_id: str, prompt: str) -> None:
        await self._store.set_backend_context(session_id, backend=self.backend_name)
        await self._replace_task(session_id, prompt, follow_up=False)

    async def continue_session(self, session_id: str, prompt: str) -> None:
        await self._replace_task(session_id, prompt, follow_up=True)

    async def cancel_session(self, session_id: str) -> None:
        task = self._tasks.pop(session_id, None)
        if task is not None:
            task.cancel()
        await self._store.set_status(session_id, "cancelled", error="已由手机端取消。")
        await self._store.publish(
            session_id,
            {
                "type": "session.failed",
                "sessionId": session_id,
                "message": "会话已取消。",
                "timestamp": _now_iso(),
            },
        )

    async def list_threads(self, workspace_roots: list[str]) -> list[dict[str, Any]]:
        return []

    async def read_thread(self, thread_id: str, workspace_roots: list[str]) -> dict[str, Any]:
        raise RuntimeError("Demo 后端不支持读取历史线程。")

    async def resume_thread(self, session_id: str, thread_id: str, prompt: str | None = None) -> None:
        raise RuntimeError("Demo 后端不支持恢复历史线程。")

    async def resolve_approval(
        self,
        session_id: str,
        approval_id: str,
        action: str,
        *,
        answers: list[dict[str, Any]] | None = None,
        content: str | None = None,
    ) -> ApprovalRecord:
        raise RuntimeError("Demo 后端不支持审批。")

    async def healthcheck(self) -> BackendHealth:
        return BackendHealth(backend=self.backend_name, available=True)

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _replace_task(self, session_id: str, prompt: str, *, follow_up: bool) -> None:
        existing = self._tasks.pop(session_id, None)
        if existing is not None:
            existing.cancel()
        task = asyncio.create_task(self._run_script(session_id, prompt, follow_up=follow_up))
        self._tasks[session_id] = task

    async def _run_script(self, session_id: str, prompt: str, *, follow_up: bool) -> None:
        summary = f"已处理任务：{prompt[:42]}{'…' if len(prompt) > 42 else ''}"
        try:
            await self._store.set_status(session_id, "running", error=None)
            await self._store.publish(
                session_id,
                {
                    "type": "tool.started",
                    "sessionId": session_id,
                    "name": "workspace_scan",
                    "timestamp": _now_iso(),
                },
            )
            await asyncio.sleep(0.05)
            await self._store.publish(
                session_id,
                {
                    "type": "tool.completed",
                    "sessionId": session_id,
                    "name": "workspace_scan",
                    "timestamp": _now_iso(),
                    "summary": "已完成工作区上下文扫描。",
                },
            )

            response = (
                f"我已收到你的任务：{prompt}\n\n"
                "这是 Demo 适配层返回的流式消息，后续可在这里替换成真实 Codex App Server。"
            )
            if follow_up:
                response = f"继续处理你的追问：{prompt}\n\n这是 Demo 适配层返回的流式消息。"
            midpoint = max(1, len(response) // 2)
            await self._store.publish(
                session_id,
                {
                    "type": "message.delta",
                    "sessionId": session_id,
                    "role": "assistant",
                    "delta": response[:midpoint],
                    "timestamp": _now_iso(),
                },
            )
            await asyncio.sleep(0.05)
            await self._store.publish(
                session_id,
                {
                    "type": "message.delta",
                    "sessionId": session_id,
                    "role": "assistant",
                    "delta": response[midpoint:],
                    "timestamp": _now_iso(),
                },
            )
            await self._store.add_message(session_id, "assistant", response)
            await self._store.publish(
                session_id,
                {
                    "type": "message.completed",
                    "sessionId": session_id,
                    "role": "assistant",
                    "content": response,
                    "timestamp": _now_iso(),
                },
            )
            await self._store.set_status(session_id, "completed", summary=summary, error=None)
            await self._store.publish(
                session_id,
                {
                    "type": "session.completed",
                    "sessionId": session_id,
                    "summary": summary,
                    "timestamp": _now_iso(),
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._store.set_status(session_id, "failed", error=str(exc))
            await self._store.publish(
                session_id,
                {
                    "type": "session.failed",
                    "sessionId": session_id,
                    "message": str(exc),
                    "timestamp": _now_iso(),
                },
            )


class AppServerAdapter(CodexAdapter):
    backend_name = "app_server"

    def __init__(
        self,
        store: SessionStore,
        *,
        command: str | list[str] | None = None,
        cwd: str | None = None,
        request_timeout: float = 45.0,
        startup_timeout: float = 10.0,
    ) -> None:
        super().__init__(store)
        resolution = _resolve_command(command)
        self._command = resolution.command
        self._preflight_error = resolution.preflight_error
        self._suggested_fix = resolution.suggested_fix
        self._cwd = cwd
        self._request_timeout = request_timeout
        self._startup_timeout = startup_timeout
        self._lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._wait_task: asyncio.Task[None] | None = None
        self._initialized = False
        self._last_error: str | None = None
        self._closed = False
        self._stderr_lines: deque[str] = deque(maxlen=20)
        self._thread_to_session: dict[str, str] = {}
        self._message_buffers: dict[str, list[str]] = {}
        self._waiting_sessions: set[str] = set()
        self._cancel_requested: set[str] = set()
        self._blocking_pipes = False

    async def start_session(self, session_id: str, prompt: str) -> None:
        await self._ensure_available()
        session = await self._store.get_session(session_id)
        if session is None:
            raise RuntimeError("会话不存在。")

        await self._store.set_status(session_id, "running", error=None)
        result = await self._call(
            "thread/start",
            {
                "model": os.getenv("CODEX_APP_SERVER_MODEL") or None,
                "modelProvider": None,
                "cwd": session.workspace,
                "approvalPolicy": _approval_policy(),
                "sandbox": _sandbox_mode(),
                "config": None,
                "baseInstructions": None,
                "developerInstructions": None,
                "personality": None,
                "ephemeral": False,
                "dynamicTools": None,
                "mockExperimentalField": None,
                "experimentalRawEvents": False,
                "persistExtendedHistory": False,
                "serviceTier": None,
            },
        )
        thread = result.get("thread") if isinstance(result, dict) else None
        thread_id = thread.get("id") if isinstance(thread, dict) else None
        if not thread_id:
            raise RuntimeError("Codex App Server 未返回 thread id。")
        self._bind_thread(session_id, thread_id)
        await self._store.set_backend_context(
            session_id,
            backend=self.backend_name,
            backend_session_id=thread_id,
            backend_run_id="",
        )
        self._message_buffers.pop(session_id, None)
        self._waiting_sessions.discard(session_id)
        self._cancel_requested.discard(session_id)
        await self._start_turn(session_id, thread_id, session.workspace, prompt)

    async def continue_session(self, session_id: str, prompt: str) -> None:
        await self._ensure_available()
        session = await self._store.get_session(session_id)
        if session is None:
            raise RuntimeError("会话不存在。")
        if not session.backend_session_id:
            raise RuntimeError("当前会话还没有关联到 Codex App Server 线程。")
        if session.status == "waiting":
            raise RuntimeError("当前会话正在等待审批，请先处理审批。")

        await self._store.set_status(session_id, "running", error=None)
        self._waiting_sessions.discard(session_id)
        self._cancel_requested.discard(session_id)
        await self._continue_or_start_turn(session_id, session.backend_session_id, session.workspace, prompt)

    async def cancel_session(self, session_id: str) -> None:
        session = await self._store.get_session(session_id)
        if session is None:
            return
        self._cancel_requested.add(session_id)
        if session.backend_session_id and session.backend_run_id:
            with contextlib.suppress(Exception):
                await self._call(
                    "turn/interrupt",
                    {
                        "threadId": session.backend_session_id,
                        "turnId": session.backend_run_id,
                    },
                )
        await self._store.set_status(session_id, "cancelled", error="已由手机端取消。")
        await self._store.publish(
            session_id,
            {
                "type": "session.failed",
                "sessionId": session_id,
                "message": "会话已取消。",
                "timestamp": _now_iso(),
            },
        )

    async def list_threads(self, workspace_roots: list[str]) -> list[dict[str, Any]]:
        await self._ensure_available()
        roots = [_normalize_workspace(root) for root in workspace_roots]
        cursor: str | None = None
        items: list[dict[str, Any]] = []

        while True:
            params: dict[str, Any] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = await self._call("thread/list", params)
            batch = result.get("data")
            if isinstance(batch, list):
                items.extend(item for item in batch if isinstance(item, dict))
            cursor = result.get("nextCursor") if isinstance(result, dict) else None
            if not cursor:
                break

        filtered = [item for item in items if _thread_allowed(item, roots)]
        filtered.sort(key=lambda item: _thread_timestamp(item, "updatedAt"), reverse=True)
        return [_convert_thread_summary(item) for item in filtered]

    async def read_thread(self, thread_id: str, workspace_roots: list[str]) -> dict[str, Any]:
        await self._ensure_available()
        result = await self._call("thread/read", {"threadId": thread_id, "includeTurns": True})
        thread = result.get("thread") if isinstance(result, dict) else None
        if not isinstance(thread, dict):
            raise RuntimeError("未找到对应线程。")
        if not _thread_allowed(thread, [_normalize_workspace(root) for root in workspace_roots]):
            raise RuntimeError("该线程不在白名单工作区内。")
        return _convert_thread_detail(thread)

    async def resume_thread(self, session_id: str, thread_id: str, prompt: str | None = None) -> None:
        await self._ensure_available()
        session = await self._store.get_session(session_id)
        if session is None:
            raise RuntimeError("会话不存在。")
        result = await self._call("thread/resume", {"threadId": thread_id})
        thread = result.get("thread") if isinstance(result, dict) else None
        if not isinstance(thread, dict):
            raise RuntimeError("恢复历史线程失败，未返回线程信息。")

        self._bind_thread(session_id, thread_id)
        workspace = _normalize_workspace(result.get("cwd") or thread.get("cwd") or session.workspace)
        await self._store.set_backend_context(
            session_id,
            backend=self.backend_name,
            backend_session_id=thread_id,
            backend_run_id="",
            source_thread_id=thread_id,
        )
        await self._store.publish(
            session_id,
            {
                "type": "thread.imported",
                "sessionId": session_id,
                "threadId": thread_id,
                "title": _thread_title(thread),
                "summary": _thread_preview(thread),
                "timestamp": _now_iso(),
            },
        )
        if prompt and prompt.strip():
            await self._store.set_status(session_id, "running", error=None)
            await self._continue_or_start_turn(session_id, thread_id, workspace, prompt.strip())
            return
        summary = _thread_preview(thread) or "已导入历史线程。"
        await self._store.set_status(session_id, "imported", summary=summary, error=None)

    async def resolve_approval(
        self,
        session_id: str,
        approval_id: str,
        action: str,
        *,
        answers: list[dict[str, Any]] | None = None,
        content: str | None = None,
    ) -> ApprovalRecord:
        approval = await self._store.get_approval(session_id, approval_id)
        if approval is None:
            raise RuntimeError("审批不存在。")
        if approval.status != "pending":
            return approval

        result_payload = _approval_resolution_payload(
            approval,
            action,
            answers=answers,
            content=content,
        )
        await self._send_server_response(approval.request_id, result_payload)
        resolved = await self._store.resolve_approval(session_id, approval_id, action)
        if resolved is None:
            raise RuntimeError("审批状态更新失败。")
        await self._store.set_status(session_id, "running", error=None)
        session = await self._store.get_session(session_id)
        if session is not None and session.interaction_mode == "plan":
            await self._store.set_interaction_state(session_id, plan_state="executing")
        await self._store.publish(
            session_id,
            {
                "type": "approval.resolved",
                "sessionId": session_id,
                "approvalId": approval_id,
                "requestId": approval.request_id,
                "resolution": action,
                "timestamp": _now_iso(),
            },
        )
        return resolved

    async def healthcheck(self) -> BackendHealth:
        if self._preflight_error:
            return BackendHealth(
                backend=self.backend_name,
                available=False,
                last_error=self._preflight_error,
                suggested_fix=self._suggested_fix,
            )
        try:
            await self._ensure_connection()
            await self._call("configRequirements/read", None)
            self._last_error = None
            return BackendHealth(backend=self.backend_name, available=True)
        except Exception as exc:
            self._last_error = str(exc)
            return BackendHealth(
                backend=self.backend_name,
                available=False,
                last_error=self._last_error,
                suggested_fix=self._suggested_fix or _suggested_fix_for_error(self._last_error),
            )

    async def close(self) -> None:
        self._closed = True
        await self._shutdown_transport("Bridge 已关闭。")

    async def _ensure_available(self) -> None:
        health = await self.healthcheck()
        if not health.available:
            raise BackendUnavailableError(health.last_error or "Codex App Server 当前不可用。")

    async def _continue_or_start_turn(self, session_id: str, thread_id: str, workspace: str, prompt: str) -> None:
        session = await self._store.get_session(session_id)
        if session is not None and session.backend_run_id and session.status == "running":
            try:
                await self._steer_turn(session_id, thread_id, session.backend_run_id, prompt)
                return
            except Exception:
                pass
        await self._start_turn(session_id, thread_id, workspace, prompt)

    async def _start_turn(self, session_id: str, thread_id: str, workspace: str, prompt: str) -> None:
        result = await self._call(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
                "cwd": workspace,
                "approvalPolicy": _approval_policy(),
                "sandboxPolicy": _sandbox_policy(workspace),
                "model": os.getenv("CODEX_APP_SERVER_MODEL") or None,
                "effort": None,
                "serviceTier": None,
                "summary": "auto",
                "personality": None,
                "outputSchema": None,
                "collaborationMode": None,
            },
        )
        turn = result.get("turn") if isinstance(result, dict) else None
        turn_id = turn.get("id") if isinstance(turn, dict) else None
        await self._store.set_backend_context(session_id, backend_run_id=turn_id or "")
        self._message_buffers.pop(session_id, None)

    async def _steer_turn(self, session_id: str, thread_id: str, turn_id: str, prompt: str) -> None:
        result = await self._call(
            "turn/steer",
            {
                "threadId": thread_id,
                "turnId": turn_id,
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
            },
        )
        turn = result.get("turn") if isinstance(result, dict) else None
        new_turn_id = turn.get("id") if isinstance(turn, dict) else None
        if new_turn_id:
            await self._store.set_backend_context(session_id, backend_run_id=new_turn_id)

    async def _ensure_connection(self) -> None:
        if self._preflight_error:
            raise BackendUnavailableError(self._preflight_error)

        async with self._lock:
            if self._initialized and self._process is not None and self._process.returncode is None:
                return
            if self._process is None or self._process.returncode is not None:
                await self._prepare_transport_locked()

        try:
            await self._request_over_transport(
                "initialize",
                {
                    "clientInfo": {
                        "name": APP_NAME,
                        "title": "Codex MCP Mobile",
                        "version": APP_VERSION,
                    },
                    "capabilities": {
                        "experimentalApi": True,
                        "optOutNotificationMethods": [],
                    },
                },
                timeout=self._startup_timeout,
                require_initialized=False,
            )
            async with self._lock:
                self._initialized = True
                self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            await self._shutdown_transport(str(exc))
            raise BackendUnavailableError(f"Codex App Server 初始化失败：{exc}") from exc

    async def _prepare_transport_locked(self) -> None:
        await self._shutdown_transport_locked(None)
        try:
            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")
            env.setdefault("PYTHONUTF8", "1")
            launch_command = _wrap_windows_script_command(self._command)
            creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
            self._blocking_pipes = False
            try:
                process = await asyncio.create_subprocess_exec(
                    *launch_command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self._cwd,
                    env=env,
                    limit=APP_SERVER_STREAM_LIMIT,
                    creationflags=creation_flags,
                )
            except PermissionError as exc:
                if os.name != "nt" or getattr(exc, "winerror", None) != 5:
                    raise
                process = subprocess.Popen(
                    launch_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self._cwd,
                    env=env,
                    bufsize=0,
                    creationflags=creation_flags,
                )
                self._blocking_pipes = True
        except Exception as exc:
            raise BackendUnavailableError(f"无法启动 Codex App Server：{exc}") from exc

        if process.stdin is None or process.stdout is None or process.stderr is None:
            process.kill()
            raise BackendUnavailableError("Codex App Server 未暴露可用的标准输入输出。")

        self._process = process
        self._reader_task = asyncio.create_task(self._reader_loop(process))
        self._stderr_task = asyncio.create_task(self._stderr_loop(process))
        self._wait_task = asyncio.create_task(self._wait_loop(process))
        self._initialized = False
        self._last_error = None

    async def _call(self, method: str, params: Any, *, timeout: float | None = None) -> dict[str, Any]:
        await self._ensure_connection()
        return await self._request_over_transport(method, params, timeout=timeout, require_initialized=True)

    async def _request_over_transport(
        self,
        method: str,
        params: Any,
        *,
        timeout: float | None,
        require_initialized: bool,
    ) -> dict[str, Any]:
        request_id = f"{method}:{uuid4()}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        async with self._lock:
            process = self._process
            if process is None or process.stdin is None or process.returncode is not None:
                raise BackendUnavailableError("Codex App Server 连接已断开。")
            if require_initialized and not self._initialized:
                raise BackendUnavailableError("Codex App Server 尚未完成初始化。")
            self._pending[request_id] = future
        payload = {"id": request_id, "method": method, "params": params}
        try:
            await self._send_payload(payload)
            response = await asyncio.wait_for(future, timeout=timeout or self._request_timeout)
        except Exception:
            async with self._lock:
                self._pending.pop(request_id, None)
            raise

        error = response.get("error")
        if error:
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(message or f"{method} 调用失败。")
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    async def _send_payload(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            process = self._process
            if process is None or process.stdin is None or process.returncode is not None:
                raise BackendUnavailableError("Codex App Server 连接已断开。")
            stdin = process.stdin

        async with self._write_lock:
            raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            if self._blocking_pipes:
                await asyncio.to_thread(stdin.write, raw)
                await asyncio.to_thread(stdin.flush)
            else:
                stdin.write(raw)
                await stdin.drain()

    async def _send_server_response(self, request_id: str, result: dict[str, Any]) -> None:
        await self._send_payload({"id": request_id, "result": result})

    async def _send_server_error(self, request_id: str, message: str) -> None:
        await self._send_payload({"id": request_id, "error": {"code": -32000, "message": message}})

    async def _reader_loop(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        try:
            while True:
                try:
                    line = await _read_process_line(process.stdout)
                except ValueError as exc:
                    self._last_error = str(exc)
                    break
                if not line:
                    break
                raw = line.decode("utf-8", errors="replace").strip()
                if not raw:
                    continue
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(message, dict):
                    continue
                if "id" in message and "method" not in message:
                    await self._resolve_pending(message)
                    continue
                if "id" in message and isinstance(message.get("method"), str):
                    await self._handle_server_request(message)
                    continue
                if isinstance(message.get("method"), str):
                    await self._handle_notification(message)
        finally:
            if not self._closed:
                await self._handle_transport_lost(process, self._transport_error_message(process))

    async def _stderr_loop(self, process: asyncio.subprocess.Process) -> None:
        assert process.stderr is not None
        while True:
            line = await _read_process_line(process.stderr)
            if not line:
                return
            raw = line.decode("utf-8", errors="replace").strip()
            if raw:
                self._stderr_lines.append(raw)

    async def _wait_loop(self, process: asyncio.subprocess.Process) -> None:
        await _wait_for_process(process)
        if not self._closed:
            await self._handle_transport_lost(process, self._transport_error_message(process))

    async def _resolve_pending(self, message: dict[str, Any]) -> None:
        async with self._lock:
            future = self._pending.pop(str(message.get("id")), None)
        if future is not None and not future.done():
            future.set_result(message)

    async def _handle_server_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method"))
        request_id = str(message.get("id"))
        params = message.get("params")
        if not isinstance(params, dict):
            await self._send_server_error(request_id, "Unsupported server request payload.")
            return
        session_id = self._session_id_from_params(params)
        if method in APPROVAL_REQUEST_METHODS and session_id:
            await self._record_approval(session_id, request_id, method, params)
            return
        await self._send_server_error(request_id, f"Unsupported server request: {method}")

    async def _record_approval(
        self,
        session_id: str,
        request_id: str,
        method: str,
        params: dict[str, Any],
    ) -> None:
        approval_id = secrets_token()
        approval = ApprovalRecord(
            approval_id=approval_id,
            session_id=session_id,
            request_id=request_id,
            kind=method,
            title=_approval_title(method, params),
            summary=_approval_summary(method, params),
            payload=_approval_payload(method, params),
            available_actions=_approval_actions(method),
            status="pending",
            created_at=datetime.now().astimezone(),
        )
        await self._store.add_approval(approval)
        await self._store.set_status(session_id, "waiting", error=_approval_wait_message(method))
        session = await self._store.get_session(session_id)
        if session is not None and session.interaction_mode == "plan":
            await self._store.set_interaction_state(session_id, plan_state="waiting_approval")
        await self._store.publish(
            session_id,
            {
                "type": "approval.required",
                "sessionId": session_id,
                "approval": approval.to_public_dict(),
                "timestamp": _now_iso(),
            },
        )
        await self._store.publish(
            session_id,
            {
                "type": "session.waiting",
                "sessionId": session_id,
                "message": _approval_wait_message(method),
                "timestamp": _now_iso(),
            },
        )

    async def _handle_notification(self, message: dict[str, Any]) -> None:
        method = str(message.get("method"))
        params = message.get("params")
        if not isinstance(params, dict):
            return
        session_id = self._session_id_from_params(params)

        if method == "turn/started" and session_id:
            turn = params.get("turn")
            turn_id = turn.get("id") if isinstance(turn, dict) else None
            if turn_id:
                await self._store.set_backend_context(session_id, backend_run_id=turn_id)
            await self._store.set_status(session_id, "running", error=None)
            return

        if method == "item/agentMessage/delta" and session_id:
            delta = str(params.get("delta") or "")
            if not delta:
                return
            self._message_buffers.setdefault(session_id, []).append(delta)
            await self._store.publish(
                session_id,
                {
                    "type": "message.delta",
                    "sessionId": session_id,
                    "role": "assistant",
                    "delta": delta,
                    "timestamp": _now_iso(),
                },
            )
            return

        if method == "item/started" and session_id:
            await self._handle_item_started(session_id, params)
            return

        if method == "item/completed" and session_id:
            await self._handle_item_completed(session_id, params)
            return

        if method == "turn/plan/updated" and session_id:
            await self._store.publish(
                session_id,
                {
                    "type": "turn.plan.updated",
                    "sessionId": session_id,
                    "plan": params.get("plan"),
                    "timestamp": _now_iso(),
                },
            )
            return

        if method == "turn/diff/updated" and session_id:
            await self._store.publish(
                session_id,
                {
                    "type": "turn.diff.updated",
                    "sessionId": session_id,
                    "diff": params.get("diff"),
                    "timestamp": _now_iso(),
                },
            )
            return

        if method in {"item/commandExecution/outputDelta", "command/exec/outputDelta"} and session_id:
            delta = _extract_output_delta(params)
            if delta:
                await self._store.publish(
                    session_id,
                    {
                        "type": "command.output.delta",
                        "sessionId": session_id,
                        "delta": delta,
                        "timestamp": _now_iso(),
                    },
                )
            return

        if method == "item/fileChange/outputDelta" and session_id:
            delta = _extract_output_delta(params)
            if delta:
                await self._store.publish(
                    session_id,
                    {
                        "type": "filechange.output.delta",
                        "sessionId": session_id,
                        "delta": delta,
                        "timestamp": _now_iso(),
                    },
                )
            return

        if method == "serverRequest/resolved":
            request_id = str(params.get("requestId") or "")
            if request_id:
                resolved = await self._store.resolve_approval_by_request_id(request_id, "resolved")
                if resolved is not None:
                    await self._store.publish(
                        resolved.session_id,
                        {
                            "type": "approval.resolved",
                            "sessionId": resolved.session_id,
                            "approvalId": resolved.approval_id,
                            "requestId": request_id,
                            "resolution": resolved.resolution,
                            "timestamp": _now_iso(),
                        },
                    )
            return

        if method == "turn/completed" and session_id:
            await self._handle_turn_completed(session_id, params)
            return

        if "approval" in method.lower() and session_id:
            await self._publish_waiting(session_id)
            return

        if method == "error" and session_id:
            await self._store.set_status(session_id, "failed", error="Codex App Server 返回错误。")
            await self._store.publish(
                session_id,
                {
                    "type": "session.failed",
                    "sessionId": session_id,
                    "message": "Codex App Server 返回错误。",
                    "timestamp": _now_iso(),
                },
            )

    async def _handle_item_started(self, session_id: str, params: dict[str, Any]) -> None:
        item = params.get("item")
        if not isinstance(item, dict):
            return
        item_type = str(item.get("type") or "")
        if item_type == "agentMessage":
            return
        await self._store.publish(
            session_id,
            {
                "type": "tool.started",
                "sessionId": session_id,
                "name": _tool_name(item),
                "timestamp": _now_iso(),
            },
        )

    async def _handle_item_completed(self, session_id: str, params: dict[str, Any]) -> None:
        item = params.get("item")
        if not isinstance(item, dict):
            return
        item_type = str(item.get("type") or "")
        if item_type == "agentMessage":
            content = str(item.get("text") or "")
            if not content:
                content = "".join(self._message_buffers.pop(session_id, []))
            else:
                self._message_buffers.pop(session_id, None)
            if not content:
                return
            await self._store.add_message(session_id, "assistant", content)
            await self._store.publish(
                session_id,
                {
                    "type": "message.completed",
                    "sessionId": session_id,
                    "role": "assistant",
                    "content": content,
                    "timestamp": _now_iso(),
                },
            )
            return

        await self._store.publish(
            session_id,
            {
                "type": "tool.completed",
                "sessionId": session_id,
                "name": _tool_name(item),
                "summary": _tool_summary(item),
                "timestamp": _now_iso(),
            },
        )

    async def _handle_turn_completed(self, session_id: str, params: dict[str, Any]) -> None:
        turn = params.get("turn")
        status = _turn_status(turn)
        normalized = status.lower()

        if session_id in self._cancel_requested or normalized in {"cancelled", "canceled", "interrupted"}:
            self._cancel_requested.discard(session_id)
            self._waiting_sessions.discard(session_id)
            return

        if normalized in {"waiting", "blocked", "needs-approval", "approval-required"}:
            await self._publish_waiting(session_id)
            return

        if normalized != "completed":
            self._waiting_sessions.discard(session_id)
            message = f"Codex 会话未正常完成：{status or 'unknown'}。"
            await self._store.set_status(session_id, "failed", error=message)
            session = await self._store.get_session(session_id)
            if session is not None and session.interaction_mode == "plan":
                await self._store.set_interaction_state(session_id, plan_state="failed")
            await self._store.publish(
                session_id,
                {
                    "type": "session.failed",
                    "sessionId": session_id,
                    "message": message,
                    "timestamp": _now_iso(),
                },
            )
            return

        self._waiting_sessions.discard(session_id)
        await self._store.set_backend_context(session_id, backend_run_id="")
        session = await self._store.get_session(session_id)
        summary = _session_summary(session)
        await self._store.set_status(session_id, "completed", summary=summary, error=None)
        if session is not None and session.interaction_mode == "plan":
            await self._store.set_interaction_state(session_id, plan_state="completed")
        await self._store.publish(
            session_id,
            {
                "type": "session.completed",
                "sessionId": session_id,
                "summary": summary,
                "timestamp": _now_iso(),
            },
        )

    async def _publish_waiting(self, session_id: str) -> None:
        if session_id in self._waiting_sessions:
            return
        self._waiting_sessions.add(session_id)
        message = "当前会话需要审批，请在手机端处理后继续。"
        await self._store.set_status(session_id, "waiting", error=message)
        session = await self._store.get_session(session_id)
        if session is not None and session.interaction_mode == "plan":
            await self._store.set_interaction_state(session_id, plan_state="waiting_approval")
        await self._store.publish(
            session_id,
            {
                "type": "session.waiting",
                "sessionId": session_id,
                "message": message,
                "timestamp": _now_iso(),
            },
        )

    async def _handle_transport_lost(self, process: asyncio.subprocess.Process, reason: str) -> None:
        async with self._lock:
            if self._process is not process:
                return
            self._last_error = reason
            self._initialized = False
            pending = list(self._pending.values())
            self._pending.clear()
            self._process = None
            self._reader_task = None
            self._stderr_task = None
            self._wait_task = None
        for future in pending:
            if not future.done():
                future.set_exception(BackendUnavailableError(reason))
        active_session_ids = list(set(self._thread_to_session.values()))
        for session_id in active_session_ids:
            session = await self._store.get_session(session_id)
            if session is None or session.status not in {"running", "waiting"}:
                continue
            await self._store.set_status(session_id, "failed", error=reason)
            await self._store.publish(
                session_id,
                {
                    "type": "session.failed",
                    "sessionId": session_id,
                    "message": reason,
                    "timestamp": _now_iso(),
                },
            )

    async def _shutdown_transport(self, reason: str | None) -> None:
        async with self._lock:
            await self._shutdown_transport_locked(reason)

    async def _shutdown_transport_locked(self, reason: str | None) -> None:
        process = self._process
        reader_task = self._reader_task
        stderr_task = self._stderr_task
        wait_task = self._wait_task
        self._process = None
        self._reader_task = None
        self._stderr_task = None
        self._wait_task = None
        self._initialized = False
        pending = list(self._pending.values())
        self._pending.clear()

        for future in pending:
            if not future.done():
                future.set_exception(BackendUnavailableError(reason or "Codex App Server 已断开。"))

        current = asyncio.current_task()
        for task in (reader_task, stderr_task, wait_task):
            if task is not None and task is not current:
                task.cancel()
        for task in (reader_task, stderr_task, wait_task):
            if task is not None and task is not current:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        if process is not None and process.returncode is None:
            process.terminate()
            try:
                with contextlib.suppress(ProcessLookupError):
                    await asyncio.wait_for(_wait_for_process(process), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                with contextlib.suppress(ProcessLookupError):
                    await _wait_for_process(process)

        self._last_error = reason

    def _bind_thread(self, session_id: str, thread_id: str) -> None:
        self._thread_to_session[thread_id] = session_id

    def _session_id_from_params(self, params: dict[str, Any]) -> str | None:
        for key in ("threadId", "conversationId"):
            value = params.get(key)
            if isinstance(value, str) and value:
                session_id = self._thread_to_session.get(value)
                if session_id:
                    return session_id
        thread = params.get("thread")
        if isinstance(thread, dict):
            thread_id = thread.get("id")
            if isinstance(thread_id, str):
                return self._thread_to_session.get(thread_id)
        return None

    def _transport_error_message(self, process: asyncio.subprocess.Process | None) -> str:
        stderr = " | ".join(self._stderr_lines)
        if process is None or process.returncode is None:
            return stderr or "Codex App Server 连接已断开。"
        base = f"Codex App Server 已退出，退出码 {process.returncode}。"
        return f"{base} {stderr}" if stderr else base


def create_adapter(store: SessionStore) -> CodexAdapter:
    backend = os.getenv("CODEX_MCP_BACKEND", "app_server").strip().lower() or "app_server"
    if backend == "demo":
        return DemoCodexAdapter(store)
    return AppServerAdapter(store)


def _resolve_command(command: str | list[str] | None) -> CommandResolution:
    raw = ""
    explicit = False
    if isinstance(command, list):
        return CommandResolution([str(item) for item in command])
    if isinstance(command, str) and command.strip():
        raw = command.strip()
        explicit = True
    else:
        raw = os.getenv("CODEX_APP_SERVER_COMMAND", "").strip()
        explicit = bool(raw)
    if explicit:
        return CommandResolution(_parse_command(raw))

    user_cli = _user_npm_codex_cmd()
    if user_cli is not None:
        return CommandResolution([str(user_cli), "app-server"])

    resolved = shutil.which("codex") or shutil.which("codex.exe")
    if resolved and _path_looks_like_windowsapps_codex(resolved):
        return CommandResolution(
            ["codex", "app-server"],
            preflight_error=(
                f"当前 codex 命令解析到受 MSIX 权限限制的 WindowsApps 路径：{resolved}。"
                "Bridge 不能从普通 Python 进程直接启动这个入口。"
            ),
            suggested_fix=WINDOWSAPPS_FIX,
        )

    return CommandResolution(["codex", "app-server"])


def _parse_command(command: str | list[str] | None) -> list[str]:
    if isinstance(command, list):
        return [str(item) for item in command]
    if isinstance(command, str) and command.strip():
        raw = command.strip()
    else:
        raw = os.getenv("CODEX_APP_SERVER_COMMAND", "").strip()
    if not raw:
        return ["codex", "app-server"]
    if raw.startswith("["):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list) and data:
            return [str(item) for item in data]
    return shlex.split(raw, posix=os.name != "nt")


WINDOWSAPPS_FIX = (
    "请运行 scripts\\setup_codex_cli.ps1 安装用户级 Codex CLI，"
    "让 Bridge 使用 %APPDATA%\\npm\\codex.cmd；不要修改 C:\\Program Files\\WindowsApps 权限。"
)


def _user_npm_codex_cmd() -> Path | None:
    if os.name != "nt":
        return None
    appdata = os.getenv("APPDATA")
    if not appdata:
        return None
    candidate = Path(appdata) / "npm" / "codex.cmd"
    return candidate if candidate.exists() else None


async def _read_process_line(stream: Any) -> bytes:
    readline = getattr(stream, "readline")
    if asyncio.iscoroutinefunction(readline):
        return await readline()
    return await asyncio.to_thread(readline)


async def _wait_for_process(process: Any) -> int:
    wait = getattr(process, "wait")
    if asyncio.iscoroutinefunction(wait):
        return await wait()
    return await asyncio.to_thread(wait)


def _wrap_windows_script_command(command: list[str]) -> list[str]:
    if os.name != "nt" or not command:
        return command
    suffix = Path(command[0]).suffix.lower()
    if suffix not in {".cmd", ".bat"}:
        return command
    comspec = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    return [comspec, "/d", "/s", "/c", subprocess.list2cmdline(command)]


def _path_looks_like_windowsapps_codex(path: str) -> bool:
    normalized = path.replace("/", "\\").lower()
    return "\\windowsapps\\openai.codex_" in normalized or "\\windowsapps\\openai.codex" in normalized


def _suggested_fix_for_error(error: str | None) -> str | None:
    if not error:
        return None
    normalized = error.lower()
    if "windowsapps" in normalized or "winerror 5" in normalized or "access is denied" in normalized or "拒绝访问" in normalized:
        return WINDOWSAPPS_FIX
    return None


def _approval_policy() -> str:
    value = os.getenv("CODEX_MCP_APPROVAL_POLICY", "on-request").strip().lower()
    return value or "on-request"


def _sandbox_mode() -> str:
    value = os.getenv("CODEX_APP_SERVER_SANDBOX", "danger-full-access").strip().lower()
    if value in {"danger-full-access", "read-only", "workspace-write"}:
        return value
    return "danger-full-access"


def _sandbox_policy(workspace: str) -> dict[str, Any]:
    mode = _sandbox_mode()
    if mode == "read-only":
        return {"type": "readOnly"}
    if mode == "workspace-write":
        return {
            "type": "workspaceWrite",
            "writableRoots": [workspace],
            "readOnlyAccess": False,
            "excludeSlashTmp": False,
            "excludeTmpdirEnvVar": False,
            "networkAccess": False,
        }
    return {"type": "dangerFullAccess"}


def _tool_name(item: dict[str, Any]) -> str:
    for key in ("title", "name", "type"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "tool"


def _tool_summary(item: dict[str, Any]) -> str:
    for key in ("summary", "text", "title"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{_tool_name(item)} 已完成。"


def _session_summary(session: Any) -> str:
    if session is None:
        return "会话已完成。"
    assistant_messages = [item.content for item in session.messages if item.role == "assistant"]
    if assistant_messages:
        content = assistant_messages[-1].replace("\n", " ").strip()
        if content:
            return content[:60] + ("…" if len(content) > 60 else "")
    return "会话已完成。"


def _turn_status(turn: Any) -> str:
    if isinstance(turn, dict):
        status = turn.get("status")
        if isinstance(status, str):
            return status
        if isinstance(status, dict):
            type_value = status.get("type")
            if isinstance(type_value, str):
                return type_value
    return ""


def _normalize_workspace(path: str | None) -> str:
    if not path:
        return ""
    value = str(path)
    if value.startswith("\\\\?\\"):
        value = value[4:]
    return os.path.normcase(os.path.abspath(value))


def _path_within_root(path: str, root: str) -> bool:
    if not path or not root:
        return False
    try:
        common = os.path.commonpath([path, root])
    except ValueError:
        return False
    return common == root


def _thread_allowed(thread: dict[str, Any], workspace_roots: list[str]) -> bool:
    cwd = _normalize_workspace(thread.get("cwd"))
    if not cwd:
        return False
    if not workspace_roots:
        return True
    return any(_path_within_root(cwd, root) for root in workspace_roots)


def _thread_timestamp(thread: dict[str, Any], key: str) -> int:
    value = thread.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _thread_preview(thread: dict[str, Any]) -> str:
    preview = thread.get("preview")
    if isinstance(preview, str) and preview.strip():
        return preview.strip()
    name = thread.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return ""


def _thread_title(thread: dict[str, Any]) -> str:
    name = thread.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    preview = _thread_preview(thread)
    if preview:
        return preview.splitlines()[0][:48]
    return "未命名线程"


def _thread_source(thread: dict[str, Any]) -> str:
    value = thread.get("source")
    return value if isinstance(value, str) and value else "unknown"


def _thread_status(thread: dict[str, Any]) -> str:
    status = thread.get("status")
    if isinstance(status, str):
        return status
    if isinstance(status, dict):
        value = status.get("type")
        if isinstance(value, str):
            return value
    return "unknown"


def _epoch_to_iso(value: Any) -> str | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value).astimezone().isoformat()
    return None


def _convert_thread_summary(thread: dict[str, Any]) -> dict[str, Any]:
    return {
        "threadId": thread.get("id"),
        "title": _thread_title(thread),
        "preview": _thread_preview(thread),
        "workspace": _normalize_workspace(thread.get("cwd")),
        "source": _thread_source(thread),
        "status": _thread_status(thread),
        "updatedAt": _epoch_to_iso(thread.get("updatedAt")),
        "createdAt": _epoch_to_iso(thread.get("createdAt")),
        "path": thread.get("path"),
    }


def _convert_thread_detail(thread: dict[str, Any]) -> dict[str, Any]:
    return {
        **_convert_thread_summary(thread),
        "turns": [_convert_turn(turn) for turn in thread.get("turns", []) if isinstance(turn, dict)],
    }


def _convert_turn(turn: dict[str, Any]) -> dict[str, Any]:
    return {
        "turnId": turn.get("id"),
        "status": turn.get("status"),
        "error": turn.get("error"),
        "items": [_convert_item(item) for item in turn.get("items", []) if isinstance(item, dict)],
    }


def _convert_item(item: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {
        "type": item.get("type"),
        "id": item.get("id"),
    }
    for key in ("text", "phase", "summary", "content", "title", "command", "status", "paths"):
        if key in item:
            converted[key] = item.get(key)
    return converted


def _extract_output_delta(params: dict[str, Any]) -> str:
    for key in ("delta", "text", "output"):
        value = params.get(key)
        if isinstance(value, str) and value:
            return value
    item = params.get("item")
    if isinstance(item, dict):
        for key in ("delta", "text", "output"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _approval_title(method: str, params: dict[str, Any]) -> str:
    mapping = {
        "item/commandExecution/requestApproval": "命令执行审批",
        "item/fileChange/requestApproval": "文件改动审批",
        "item/permissions/requestApproval": "权限审批",
        "item/tool/requestUserInput": "需要补充输入",
        "mcpServer/elicitation/request": "MCP 交互请求",
        "execCommandApproval": "命令执行审批",
        "applyPatchApproval": "补丁应用审批",
    }
    title = mapping.get(method, method)
    command = params.get("command")
    if isinstance(command, str) and command:
        return f"{title}: {command}"
    return title


def _approval_summary(method: str, params: dict[str, Any]) -> str:
    for key in ("message", "reason", "prompt", "command"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    item = params.get("item")
    if isinstance(item, dict):
        for key in ("command", "summary", "title", "text"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return f"收到审批请求：{method}"


def _approval_payload(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": method,
        "params": params,
    }


def _approval_actions(method: str) -> list[str]:
    if method == "item/tool/requestUserInput":
        return ["submit", "cancel"]
    if method == "mcpServer/elicitation/request":
        return ["reject", "cancel"]
    return ["approve", "approve_session", "reject", "cancel"]


def _approval_wait_message(method: str) -> str:
    if method == "item/tool/requestUserInput":
        return "Codex 需要你补充输入。"
    if method == "mcpServer/elicitation/request":
        return "Codex 发起了 MCP 交互请求。"
    return "当前会话需要审批，请在手机端处理后继续。"


def _approval_resolution_payload(
    approval: ApprovalRecord,
    action: str,
    *,
    answers: list[dict[str, Any]] | None,
    content: str | None,
) -> dict[str, Any]:
    method = approval.kind
    params = approval.payload.get("params")
    params = params if isinstance(params, dict) else {}

    if method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
        return {
            "decision": {
                "approve": "accept",
                "approve_session": "acceptForSession",
                "reject": "decline",
                "cancel": "cancel",
            }.get(action, "decline")
        }

    if method == "item/permissions/requestApproval":
        permissions = params.get("permissions")
        if not isinstance(permissions, dict):
            permissions = {}
        if action == "approve":
            return {"permissions": permissions, "scope": "turn"}
        if action == "approve_session":
            return {"permissions": permissions, "scope": "session"}
        return {"permissions": {}, "scope": "turn"}


    if method == "item/tool/requestUserInput":
        return {"answers": _normalize_request_user_input_answers(answers, content)}

    if method == "mcpServer/elicitation/request":
        return {
            "action": "cancel" if action == "cancel" else "decline",
            "content": None,
            "_meta": None,
        }

    if method in {"execCommandApproval", "applyPatchApproval"}:
        return {
            "decision": {
                "approve": "approved",
                "approve_session": "approved_for_session",
                "reject": "denied",
                "cancel": "abort",
            }.get(action, "denied")
        }

    return {"decision": action}


def _normalize_request_user_input_answers(
    answers: list[dict[str, Any]] | None,
    content: str | None,
) -> dict[str, Any]:
    if answers:
        normalized: dict[str, Any] = {}
        for item in answers:
            if not isinstance(item, dict):
                continue
            question_id = str(item.get("id") or item.get("questionId") or "").strip()
            if not question_id:
                continue
            values = item.get("answers")
            if isinstance(values, list):
                normalized[question_id] = {"answers": values}
                continue
            single_value = item.get("answer")
            if single_value is not None:
                normalized[question_id] = {"answers": [single_value]}
        if normalized:
            return normalized
    if content:
        return {"freeform": {"answers": [content]}}
    return {}


def secrets_token() -> str:
    return uuid4().hex[:12]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()
