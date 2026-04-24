from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def log_event(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    payload = {
        "event": event,
        "timestamp": datetime.now().astimezone().isoformat(),
        **fields,
    }
    logger.log(level, json.dumps(payload, ensure_ascii=True, default=str))
