from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from .models import AttachmentRecord


ALLOWED_IMAGE_MIME_TYPES: Final[dict[str, str]] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_ATTACHMENT_BYTES: Final[int] = 5 * 1024 * 1024
MAX_MESSAGE_ATTACHMENTS: Final[int] = 4


@dataclass(slots=True)
class AttachmentValidationError(Exception):
    message: str


def normalize_mime_type(value: str | None) -> str:
    mime_type = str(value or "").split(";", 1)[0].strip().lower()
    return mime_type


def validate_image_upload(file_name: str, mime_type: str, data: bytes) -> str:
    normalized = normalize_mime_type(mime_type)
    if normalized not in ALLOWED_IMAGE_MIME_TYPES:
        raise AttachmentValidationError("仅支持 JPEG、PNG、WebP 图片。")
    if not data:
        raise AttachmentValidationError("图片内容为空。")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise AttachmentValidationError("图片不能超过 5MB。")
    detected = sniff_image_mime_type(data)
    if detected != normalized:
        raise AttachmentValidationError("图片格式与 MIME 类型不匹配。")
    return normalized


def sniff_image_mime_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def image_dimensions(data: bytes) -> tuple[int, int]:
    try:
        from PIL import Image
        from io import BytesIO

        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            return int(width), int(height)
    except Exception:
        return 0, 0


def safe_display_file_name(value: str | None, fallback: str = "image") -> str:
    raw = Path(str(value or fallback)).name.strip()
    if not raw or raw in {".", ".."}:
        return fallback
    return raw[:120]


def store_image_attachment(
    *,
    root: Path,
    file_name: str,
    mime_type: str,
    data: bytes,
) -> AttachmentRecord:
    normalized = validate_image_upload(file_name, mime_type, data)
    attachment_id = secrets.token_urlsafe(16)
    extension = ALLOWED_IMAGE_MIME_TYPES[normalized]
    directory = root / attachment_id
    directory.mkdir(parents=True, exist_ok=False)
    local_path = directory / f"original{extension}"
    local_path.write_bytes(data)
    width, height = image_dimensions(data)
    return AttachmentRecord(
        attachment_id=attachment_id,
        file_name=safe_display_file_name(file_name, f"image{extension}"),
        mime_type=normalized,
        size_bytes=len(data),
        width=width,
        height=height,
        created_at=datetime.now().astimezone(),
        local_path=str(local_path.resolve()),
    )
