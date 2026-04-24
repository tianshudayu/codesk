from __future__ import annotations

import asyncio
import contextlib
import ctypes
import hashlib
import logging
import os
import signal
import sys
from pathlib import Path

from .main import build_runtime

ERROR_ALREADY_EXISTS = 183
_SINGLE_INSTANCE_HANDLE = None


def _identity_mutex_name() -> str:
    identity_path = os.getenv("CODEX_CLOUD_AGENT_IDENTITY_FILE", "").strip()
    if not identity_path:
        identity_path = str((Path(__file__).resolve().parent.parent / ".logs" / "cloud-agent.json").resolve())
    digest = hashlib.sha1(identity_path.encode("utf-8", "replace")).hexdigest()
    return f"Global\\CodeskAgent-{digest}"


def acquire_single_instance() -> bool:
    global _SINGLE_INSTANCE_HANDLE
    if os.name != "nt":
        return True
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, _identity_mutex_name())
    if not handle:
        return True
    _SINGLE_INSTANCE_HANDLE = handle
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


async def run_agent() -> None:
    runtime = build_runtime(enable_relay=False, enable_cloud_agent=True)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for signum in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if signum is None:
            continue
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop_event.set)

    try:
        await runtime.service.start_background_tasks()
        if runtime.cloud_agent is not None:
            await runtime.cloud_agent.start()
        await stop_event.wait()
    finally:
        if runtime.cloud_agent is not None:
            await runtime.cloud_agent.close()
        await runtime.service.stop_background_tasks()
        await runtime.adapter.close()


def main() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    runtime_root = os.getenv("CODEX_RUNTIME_ROOT", "").strip()
    log_root = Path(runtime_root).expanduser() if runtime_root else Path(__file__).resolve().parent.parent / ".logs"
    log_dir = log_root / ".logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / "agent.log", encoding="utf-8"))
    except Exception:
        pass
    logging.basicConfig(
        level=logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("websockets.client").setLevel(logging.INFO)
    if not acquire_single_instance():
        logging.info("Codesk agent already running for this identity; exiting duplicate instance.")
        return
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
