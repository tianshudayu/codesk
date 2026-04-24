from __future__ import annotations

import json
import sys
from copy import deepcopy
from uuid import uuid4


pending_turns: dict[str, dict[str, str]] = {}
pending_requests: dict[str, dict[str, str]] = {}


def send(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def extract_prompt(params: dict[str, object]) -> str:
    input_items = params.get("input")
    if not isinstance(input_items, list) or not input_items:
        return ""
    first = input_items[0]
    if not isinstance(first, dict):
        return ""
    return str(first.get("text") or "")


def turn_item_user(text: str) -> dict[str, object]:
    return {
        "type": "userMessage",
        "id": f"item-{uuid4().hex[:8]}",
        "content": [{"type": "text", "text": text, "text_elements": []}],
    }


def turn_item_assistant(text: str) -> dict[str, object]:
    return {
        "type": "agentMessage",
        "id": f"item-{uuid4().hex[:8]}",
        "text": text,
        "phase": "final_answer",
        "memoryCitation": None,
    }


THREADS: dict[str, dict[str, object]] = {
    "thread-existing": {
        "id": "thread-existing",
        "preview": "历史线程示例",
        "ephemeral": False,
        "modelProvider": "openai",
        "createdAt": 1775535294,
        "updatedAt": 1775535311,
        "status": {"type": "idle"},
        "path": None,
        "cwd": r"E:\workspace",
        "cliVersion": "0.118.0",
        "source": "vscode",
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": "历史线程示例",
        "turns": [
            {
                "id": "turn-existing",
                "items": [
                    turn_item_user("先总结项目结构"),
                    turn_item_assistant("项目结构摘要：bridge、tests、static。"),
                ],
                "status": "completed",
                "error": None,
            }
        ],
    },
    "thread-large": {
        "id": "thread-large",
        "preview": "大响应线程",
        "ephemeral": False,
        "modelProvider": "openai",
        "createdAt": 1775536200,
        "updatedAt": 1775537200,
        "status": {"type": "idle"},
        "path": None,
        "cwd": r"E:\workspace",
        "cliVersion": "0.118.0",
        "source": "cli",
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": "大响应线程",
        "turns": [
            {
                "id": "turn-large",
                "items": [
                    turn_item_user("输出很长的日志"),
                    turn_item_assistant("X" * 120000),
                ],
                "status": "completed",
                "error": None,
            }
        ],
    },
    "thread-other": {
        "id": "thread-other",
        "preview": "不在白名单",
        "ephemeral": False,
        "modelProvider": "openai",
        "createdAt": 1775538200,
        "updatedAt": 1775538300,
        "status": {"type": "idle"},
        "path": None,
        "cwd": r"D:\other",
        "cliVersion": "0.118.0",
        "source": "vscode",
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": "别的工作区",
        "turns": [],
    },
    "thread-running": {
        "id": "thread-running",
        "preview": "运行中的任务",
        "ephemeral": False,
        "modelProvider": "openai",
        "createdAt": 1775539000,
        "updatedAt": 1775539400,
        "status": {"type": "running"},
        "path": None,
        "cwd": r"D:\other",
        "cliVersion": "0.118.0",
        "source": "cli",
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": "运行中的任务",
        "turns": [],
    },
}


def emit_completed_turn(thread_id: str, turn_id: str, prompt: str, response: str) -> None:
    send(
        {
            "method": "item/started",
            "params": {
                "threadId": thread_id,
                "turnId": turn_id,
                "item": {"type": "commandExecution", "title": "workspace_scan"},
            },
        }
    )
    send(
        {
            "method": "item/commandExecution/outputDelta",
            "params": {"threadId": thread_id, "turnId": turn_id, "delta": "scan output\n"},
        }
    )
    send(
        {
            "method": "item/completed",
            "params": {
                "threadId": thread_id,
                "turnId": turn_id,
                "item": {
                    "type": "commandExecution",
                    "title": "workspace_scan",
                    "summary": "已完成工作区扫描。",
                },
            },
        }
    )
    send({"method": "turn/plan/updated", "params": {"threadId": thread_id, "turnId": turn_id, "plan": [{"step": "scan", "status": "completed"}]}})
    send({"method": "turn/diff/updated", "params": {"threadId": thread_id, "turnId": turn_id, "diff": {"files": ["bridge/main.py"]}}})
    midpoint = max(1, len(response) // 2)
    send({"method": "item/agentMessage/delta", "params": {"threadId": thread_id, "turnId": turn_id, "delta": response[:midpoint]}})
    send({"method": "item/agentMessage/delta", "params": {"threadId": thread_id, "turnId": turn_id, "delta": response[midpoint:]}})
    send(
        {
            "method": "item/completed",
            "params": {
                "threadId": thread_id,
                "turnId": turn_id,
                "item": turn_item_assistant(response),
            },
        }
    )
    send({"method": "turn/completed", "params": {"threadId": thread_id, "turn": {"id": turn_id, "status": "completed"}}})
    THREADS[thread_id]["updatedAt"] = THREADS[thread_id].get("updatedAt", 0) + 1
    THREADS[thread_id]["status"] = {"type": "idle"}
    THREADS[thread_id].setdefault("turns", []).append(
        {
            "id": turn_id,
            "items": [turn_item_user(prompt), turn_item_assistant(response)],
            "status": "completed",
            "error": None,
        }
    )


for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    request = json.loads(line)

    if "id" in request and "method" not in request:
        request_id = str(request["id"])
        pending = pending_requests.pop(request_id, None)
        if pending is not None:
            send({"method": "serverRequest/resolved", "params": {"requestId": request_id}})
            thread_id = pending["threadId"]
            turn_id = pending["turnId"]
            action = json.dumps(request.get("result"), ensure_ascii=False)
            response = f"审批已处理：{action}"
            emit_completed_turn(thread_id, turn_id, pending["prompt"], response)
        continue

    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}

    if method == "initialize":
        send({"id": request_id, "result": {"ok": True}})
        continue

    if method == "configRequirements/read":
        send({"id": request_id, "result": {"requirements": {"allowedApprovalPolicies": ["never", "on-request"]}}})
        continue

    if method == "thread/list":
        send({"id": request_id, "result": {"data": [deepcopy(item) for item in THREADS.values()], "nextCursor": None}})
        continue

    if method == "thread/read":
        thread_id = str(params.get("threadId"))
        send({"id": request_id, "result": {"thread": deepcopy(THREADS[thread_id])}})
        continue

    if method == "thread/resume":
        thread_id = str(params.get("threadId"))
        thread = deepcopy(THREADS[thread_id])
        thread["status"] = {"type": "idle"}
        send(
            {
                "id": request_id,
                "result": {
                    "thread": thread,
                    "model": "gpt-5.4",
                    "modelProvider": "openai",
                    "serviceTier": None,
                    "cwd": thread["cwd"],
                    "approvalPolicy": "on-request",
                    "approvalsReviewer": "user",
                    "sandbox": {"type": "readOnly", "access": {"type": "fullAccess"}, "networkAccess": False},
                    "reasoningEffort": "high",
                },
            }
        )
        continue

    if method == "thread/start":
        thread_id = f"thread-{uuid4().hex[:8]}"
        THREADS[thread_id] = {
            "id": thread_id,
            "preview": "",
            "ephemeral": False,
            "modelProvider": "openai",
            "createdAt": 1775540000,
            "updatedAt": 1775540000,
            "status": {"type": "idle"},
            "path": None,
            "cwd": params.get("cwd"),
            "cliVersion": "0.118.0",
            "source": "bridge",
            "agentNickname": None,
            "agentRole": None,
            "gitInfo": None,
            "name": None,
            "turns": [],
        }
        send({"id": request_id, "result": {"thread": {"id": thread_id, "cwd": params.get("cwd")}}})
        continue

    if method in {"turn/start", "turn/steer"}:
        thread_id = str(params.get("threadId"))
        turn_id = f"turn-{uuid4().hex[:8]}"
        prompt = extract_prompt(params)
        send({"id": request_id, "result": {"turn": {"id": turn_id}}})
        send({"method": "turn/started", "params": {"threadId": thread_id, "turn": {"id": turn_id}}})

        lowered = prompt.lower()
        if "approval" in lowered:
            request_token = f"request-{uuid4().hex[:8]}"
            pending_requests[request_token] = {"threadId": thread_id, "turnId": turn_id, "prompt": prompt}
            send(
                {
                    "id": request_token,
                    "method": "item/commandExecution/requestApproval",
                    "params": {"threadId": thread_id, "turnId": turn_id, "command": "dir"},
                }
            )
            continue

        if "permissions" in lowered:
            request_token = f"request-{uuid4().hex[:8]}"
            pending_requests[request_token] = {"threadId": thread_id, "turnId": turn_id, "prompt": prompt}
            send(
                {
                    "id": request_token,
                    "method": "item/permissions/requestApproval",
                    "params": {"threadId": thread_id, "turnId": turn_id, "permissions": {"shell": True}},
                }
            )
            continue

        if "user input" in lowered:
            request_token = f"request-{uuid4().hex[:8]}"
            pending_requests[request_token] = {"threadId": thread_id, "turnId": turn_id, "prompt": prompt}
            send(
                {
                    "id": request_token,
                    "method": "item/tool/requestUserInput",
                    "params": {
                        "threadId": thread_id,
                        "turnId": turn_id,
                        "questions": [{"id": "color", "question": "choose color"}],
                    },
                }
            )
            continue

        if "legacy exec" in lowered:
            request_token = f"request-{uuid4().hex[:8]}"
            pending_requests[request_token] = {"threadId": thread_id, "turnId": turn_id, "prompt": prompt}
            send({"id": request_token, "method": "execCommandApproval", "params": {"threadId": thread_id, "turnId": turn_id, "command": "dir"}})
            continue

        if "legacy patch" in lowered:
            request_token = f"request-{uuid4().hex[:8]}"
            pending_requests[request_token] = {"threadId": thread_id, "turnId": turn_id, "prompt": prompt}
            send({"id": request_token, "method": "applyPatchApproval", "params": {"threadId": thread_id, "turnId": turn_id}})
            continue

        if "hold" in lowered:
            pending_turns[thread_id] = {"turnId": turn_id, "prompt": prompt}
            continue

        response = f"Codex echo: {prompt}"
        emit_completed_turn(thread_id, turn_id, prompt, response)
        continue

    if method == "turn/interrupt":
        thread_id = str(params.get("threadId"))
        turn = pending_turns.pop(thread_id, None)
        send({"id": request_id, "result": {"ok": True}})
        if turn is not None:
            send({"method": "turn/completed", "params": {"threadId": thread_id, "turn": {"id": turn['turnId'], "status": "cancelled"}}})
        continue

    send({"id": request_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}})
