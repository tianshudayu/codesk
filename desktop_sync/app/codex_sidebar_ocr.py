from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


MATCH_THRESHOLD = 0.72
MATCH_MARGIN = 0.12
MIN_OCR_CONFIDENCE = 0.25
SHORT_TITLE_MAX_CHARS = 6


class OcrUnavailableError(RuntimeError):
    pass


class SidebarTargetNotVisibleError(RuntimeError):
    pass


class SidebarTargetAmbiguousError(RuntimeError):
    pass


@dataclass(slots=True)
class TextBox:
    text: str
    confidence: float
    left: float
    top: float
    right: float
    bottom: float

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass(slots=True)
class SidebarRow:
    row_index: int
    text: str
    left: float
    top: float
    right: float
    bottom: float


@dataclass(slots=True)
class SidebarMatch:
    matched_text: str
    confidence: float
    row_index: int
    row_box: dict[str, float]


class CodexSidebarOcr:
    def __init__(self) -> None:
        self._engine: Any | None = None
        self._engine_load_error: str | None = None

    def match_thread(
        self,
        image: Any,
        *,
        title: str | None,
        preview: str | None,
        visible_rows: int,
    ) -> SidebarMatch:
        boxes = self._read_text_boxes(image)
        rows = self._group_rows(boxes, visible_rows=visible_rows, image_height=float(image.height))
        if not rows:
            raise SidebarTargetNotVisibleError("当前桌面左栏没有识别到可匹配的线程。")
        return self._match_rows(rows, title=title, preview=preview)

    def _read_text_boxes(self, image: Any) -> list[TextBox]:
        engine = self._load_engine()
        try:
            import numpy as np
            from PIL import ImageEnhance
        except ImportError as exc:
            raise OcrUnavailableError("OCR 依赖不可用，请重新安装远控服务依赖。") from exc

        scale = 2.0
        prepared = image.convert("RGB")
        prepared = ImageEnhance.Contrast(prepared).enhance(1.35)
        prepared = prepared.resize(
            (max(1, round(prepared.width * scale)), max(1, round(prepared.height * scale))),
        )
        raw = engine(np.array(prepared))
        items = self._raw_items(raw)
        boxes: list[TextBox] = []
        for item in items:
            parsed = self._parse_item(item, scale=scale)
            if parsed is not None:
                boxes.append(parsed)
        return boxes

    def _load_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        if self._engine_load_error is not None:
            raise OcrUnavailableError(self._engine_load_error)
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            self._engine_load_error = "OCR 依赖不可用，请安装 rapidocr-onnxruntime。"
            raise OcrUnavailableError(self._engine_load_error) from exc
        try:
            self._engine = RapidOCR()
        except Exception as exc:  # pragma: no cover - dependency-specific
            self._engine_load_error = f"OCR 初始化失败：{exc}"
            raise OcrUnavailableError(self._engine_load_error) from exc
        return self._engine

    def _raw_items(self, raw: Any) -> list[Any]:
        if raw is None:
            return []
        if isinstance(raw, tuple):
            raw = raw[0]
        if raw is None:
            return []
        return list(raw) if isinstance(raw, list) else []

    def _parse_item(self, item: Any, *, scale: float) -> TextBox | None:
        if isinstance(item, dict):
            box = item.get("box") or item.get("points")
            text = item.get("text")
            confidence = item.get("score") or item.get("confidence") or 0
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            box, text, confidence = item[0], item[1], item[2]
        else:
            return None
        if not isinstance(text, str) or not text.strip():
            return None
        try:
            score = float(confidence)
        except (TypeError, ValueError):
            score = 0.0
        if score < MIN_OCR_CONFIDENCE:
            return None
        points = _box_points(box)
        if not points:
            return None
        xs = [point[0] / scale for point in points]
        ys = [point[1] / scale for point in points]
        return TextBox(
            text=text.strip(),
            confidence=score,
            left=min(xs),
            top=min(ys),
            right=max(xs),
            bottom=max(ys),
        )

    def _group_rows(self, boxes: list[TextBox], *, visible_rows: int, image_height: float) -> list[SidebarRow]:
        if visible_rows <= 0 or image_height <= 0:
            return []
        buckets: dict[int, list[TextBox]] = {}
        for box in boxes:
            row_index = int(max(0, min(visible_rows - 1, box.center_y / image_height * visible_rows)))
            buckets.setdefault(row_index, []).append(box)

        rows: list[SidebarRow] = []
        for row_index, row_boxes in sorted(buckets.items()):
            row_boxes.sort(key=lambda item: (item.top, item.left))
            text = " ".join(item.text for item in row_boxes).strip()
            if not text:
                continue
            rows.append(
                SidebarRow(
                    row_index=row_index,
                    text=text,
                    left=min(item.left for item in row_boxes),
                    top=min(item.top for item in row_boxes),
                    right=max(item.right for item in row_boxes),
                    bottom=max(item.bottom for item in row_boxes),
                )
            )
        return rows

    def _match_rows(self, rows: list[SidebarRow], *, title: str | None, preview: str | None) -> SidebarMatch:
        title_norm = _normalize(title)
        preview_norm = _normalize(preview)
        if not title_norm and not preview_norm:
            raise SidebarTargetNotVisibleError("目标线程缺少可用于识别的标题或摘要。")

        if title_norm:
            exact_title_rows = [row for row in rows if _normalize(_leading_title_token(row.text)) == title_norm]
            if len(exact_title_rows) == 1:
                return _sidebar_match(exact_title_rows[0], 1.0)
            if len(exact_title_rows) > 1 and preview_norm:
                scored = sorted(
                    ((_score(_normalize(row.text), preview_norm), row) for row in exact_title_rows),
                    key=lambda item: item[0],
                    reverse=True,
                )
                best_score, best_row = scored[0]
                second_score = scored[1][0] if len(scored) > 1 else 0.0
                if best_score >= MATCH_THRESHOLD and best_score - second_score >= MATCH_MARGIN:
                    return _sidebar_match(best_row, min(0.99, best_score))

        if title_norm and len(title_norm) <= SHORT_TITLE_MAX_CHARS:
            return self._match_short_title(rows, title=title or "", title_norm=title_norm, preview_norm=preview_norm)

        scored: list[tuple[float, SidebarRow]] = []
        for row in rows:
            row_norm = _normalize(row.text)
            score = max(_score(row_norm, title_norm), _score(row_norm, preview_norm) * 0.94)
            if title_norm and preview_norm:
                score = max(score, _score(row_norm, title_norm + preview_norm) * 0.88)
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_row = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        if best_score < MATCH_THRESHOLD:
            raise SidebarTargetNotVisibleError("目标线程不在桌面左栏当前可见范围，或 OCR 未能识别到它。")
        if best_score - second_score < MATCH_MARGIN:
            raise SidebarTargetAmbiguousError("识别到多个相似线程，请让目标线程在左栏中更清晰可见后重试。")
        return SidebarMatch(
            matched_text=best_row.text,
            confidence=round(float(best_score), 4),
            row_index=getattr(best_row, "row_index", 0),
            row_box={
                "left": best_row.left,
                "top": best_row.top,
                "right": best_row.right,
                "bottom": best_row.bottom,
            },
        )

    def _match_short_title(
        self,
        rows: list[SidebarRow],
        *,
        title: str,
        title_norm: str,
        preview_norm: str,
    ) -> SidebarMatch:
        exact_rows = [row for row in rows if _contains_exact_short_title(row.text, title)]
        if not exact_rows:
            raise SidebarTargetNotVisibleError("target thread is not visible in the desktop sidebar.")

        if len(exact_rows) > 1 and preview_norm:
            scored = sorted(
                ((_score(_normalize(row.text), preview_norm), row) for row in exact_rows),
                key=lambda item: item[0],
                reverse=True,
            )
            best_score, best_row = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else 0.0
            if best_score >= MATCH_THRESHOLD and best_score - second_score >= MATCH_MARGIN:
                return _sidebar_match(best_row, min(0.99, best_score))

        if len(exact_rows) != 1:
            raise SidebarTargetAmbiguousError("multiple visible sidebar rows match the target title.")

        return _sidebar_match(exact_rows[0], 1.0)


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).lower()
    normalized = re.sub(r"# files mentioned by the user.*?## my request for codex:", "", normalized, flags=re.S)
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def _contains_exact_short_title(row_text: str, title: str) -> bool:
    target = _normalize(title)
    if not target:
        return False
    title_token = _leading_title_token(row_text)
    if title_token is not None:
        return _normalize(title_token) == target
    haystack = unicodedata.normalize("NFKC", row_text or "").lower()
    for match in re.finditer(re.escape(target), haystack):
        before = haystack[match.start() - 1] if match.start() > 0 else ""
        after = haystack[match.end()] if match.end() < len(haystack) else ""
        if _is_title_boundary(before) and _is_title_boundary(after):
            return True
    return False


def _leading_title_token(row_text: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", row_text or "").strip().lower()
    if not normalized:
        return None
    tokens = [token for token in re.split(r"\s+", normalized) if token]
    if not tokens:
        return None
    meaningful = [token for token in tokens if not _is_row_meta_token(token)]
    if meaningful:
        return meaningful[0]
    return None


def _is_row_meta_token(token: str) -> bool:
    token = unicodedata.normalize("NFKC", token or "").strip().lower()
    if not token:
        return True
    if re.fullmatch(r"\d+\s*(秒|分|分钟|小时|天|周|月|年)", token):
        return True
    if token in {
        "re",
        "resume",
        "running",
        "completed",
        "waiting",
        "blocked",
        "done",
        "idle",
        "pending",
        "synced",
        "active",
        "空闲",
        "进行中",
        "运行中",
        "已完成",
        "等待",
        "阻塞",
        "恢复",
        "当前",
        "同步",
        "降级",
        "桌面实时",
    }:
        return True
    return False


def _is_title_boundary(char: str) -> bool:
    return not char or not re.match(r"[\w\u4e00-\u9fff]", char, flags=re.UNICODE)


def _sidebar_match(row: SidebarRow, confidence: float) -> SidebarMatch:
    return SidebarMatch(
        matched_text=row.text,
        confidence=round(float(confidence), 4),
        row_index=getattr(row, "row_index", 0),
        row_box={
            "left": row.left,
            "top": row.top,
            "right": row.right,
            "bottom": row.bottom,
        },
    )


def _score(row_text: str, target: str) -> float:
    if not row_text or not target:
        return 0.0
    if target in row_text:
        return 1.0
    if len(row_text) >= 4 and row_text in target:
        return 0.9
    return SequenceMatcher(None, row_text, target).ratio()


def _box_points(box: Any) -> list[tuple[float, float]]:
    if not isinstance(box, (list, tuple)):
        return []
    if len(box) == 4 and all(isinstance(item, (int, float)) for item in box):
        left, top, right, bottom = [float(item) for item in box]
        return [(left, top), (right, top), (right, bottom), (left, bottom)]
    points: list[tuple[float, float]] = []
    for point in box:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        try:
            points.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            return []
    return points
