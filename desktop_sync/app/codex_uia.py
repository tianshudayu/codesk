from __future__ import annotations

import base64
import json
import ntpath
import os
import re
import subprocess
import time
import unicodedata
from dataclasses import dataclass


CREATE_NO_WINDOW = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


class UIAutomationUnavailableError(RuntimeError):
    pass


class UIAutomationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class UIARect:
    x: float
    y: float
    width: float
    height: float

    @property
    def center_x(self) -> int:
        return round(self.x + (self.width / 2.0))

    @property
    def center_y(self) -> int:
        return round(self.y + (self.height / 2.0))

    def to_public_dict(self) -> dict[str, float]:
        return {
            "left": round(self.x, 2),
            "top": round(self.y, 2),
            "right": round(self.x + self.width, 2),
            "bottom": round(self.y + self.height, 2),
        }


@dataclass(slots=True)
class UIASidebarItem:
    name: str
    control_type: str
    rect: UIARect
    offscreen: bool
    parent_name: str | None = None
    parent_control_type: str | None = None
    grandparent_name: str | None = None
    grandparent_control_type: str | None = None
    scrollable: bool = False
    invokable: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "UIASidebarItem":
        rect_payload = payload.get("rect") if isinstance(payload.get("rect"), dict) else {}
        return cls(
            name=str(payload.get("name") or ""),
            control_type=str(payload.get("controlType") or ""),
            rect=UIARect(
                x=float(rect_payload.get("x") or 0.0),
                y=float(rect_payload.get("y") or 0.0),
                width=float(rect_payload.get("width") or 0.0),
                height=float(rect_payload.get("height") or 0.0),
            ),
            offscreen=bool(payload.get("offscreen")),
            parent_name=_optional_str(payload.get("parentName")),
            parent_control_type=_optional_str(payload.get("parentControlType")),
            grandparent_name=_optional_str(payload.get("grandparentName")),
            grandparent_control_type=_optional_str(payload.get("grandparentControlType")),
            scrollable=bool(payload.get("scrollable")),
            invokable=bool(payload.get("invokable")),
        )

    @property
    def is_sidebar_item(self) -> bool:
        # Codex exposes right-pane transcript rows as ListItem too. Keep
        # thread switching scoped to the narrow left sidebar only.
        return self.control_type == "ControlType.ListItem" and 0 < self.rect.width <= 420

    @property
    def is_thread_item(self) -> bool:
        return (
            self.is_sidebar_item
            and self.parent_control_type == "ControlType.List"
            and self.grandparent_control_type == "ControlType.ListItem"
        )

    @property
    def is_project_item(self) -> bool:
        return (
            self.is_sidebar_item
            and not self.is_thread_item
            and self.parent_control_type == "ControlType.List"
            and self.grandparent_control_type == "ControlType.Group"
        )

    @property
    def project_name(self) -> str | None:
        if self.is_thread_item:
            return self.grandparent_name
        if self.is_project_item:
            return self.name
        return None

    @property
    def thread_title(self) -> str:
        return _strip_relative_time(self.name)


@dataclass(slots=True)
class ThreadFocusTarget:
    matched_project: str
    matched_title: str
    rect: UIARect
    raw_name: str
    verified_title: str | None = None

    @property
    def matched_text(self) -> str:
        return self.matched_title

    @property
    def confidence(self) -> float:
        return 1.0

    @property
    def row_box(self) -> dict[str, float]:
        return self.rect.to_public_dict()

    def to_public_dict(self) -> dict[str, object]:
        return {
            "matchSource": "uia",
            "matchedProject": self.matched_project,
            "matchedTitle": self.matched_title,
            "matchedText": self.matched_title,
            "confidence": 1.0,
            "rowBox": self.rect.to_public_dict(),
        }


@dataclass(slots=True)
class NewThreadTarget:
    button_name: str
    verified_title: str | None = None


class CodexDesktopUIAutomation:
    def list_sidebar_items(self, hwnd: int) -> list[UIASidebarItem]:
        payload = self._run({"action": "sidebar_items", "hwnd": hwnd})
        items = payload.get("items")
        if not isinstance(items, list):
            raise UIAutomationError("uia_invalid_response", "桌面无障碍接口返回了无效的线程列表。")
        return [UIASidebarItem.from_payload(item) for item in items if isinstance(item, dict)]

    def find_thread_target(self, hwnd: int, *, workspace: str, title: str) -> ThreadFocusTarget:
        project_name = _workspace_basename(workspace)
        title_norm = _normalize(title)
        if not project_name:
            raise UIAutomationError("invalid_message", "当前会话缺少有效工作区，无法对齐桌面线程。")
        if not title_norm:
            raise UIAutomationError("invalid_message", "当前会话缺少有效标题，无法对齐桌面线程。")

        items = self.list_sidebar_items(hwnd)
        project_items = [item for item in items if item.is_project_item and _normalize(item.name) == _normalize(project_name)]
        if not project_items:
            raise UIAutomationError("project_not_found", "未找到目标项目，请保持 Codex 左侧项目列表展开后重试。")
        if len(project_items) > 1:
            raise UIAutomationError("ambiguous_project", "检测到多个同名项目，已阻断以避免切错线程。")

        candidates = self._thread_candidates(items, project_name=project_name, title=title)
        if not candidates:
            raise UIAutomationError("target_not_visible", "目标线程未出现在对应项目的桌面边栏中。")
        if len(candidates) > 1:
            raise UIAutomationError("ambiguous_target", "对应项目下存在多个同名线程，已阻断以避免切错线程。")

        target = candidates[0]
        if target.offscreen:
            if not target.scrollable:
                raise UIAutomationError("target_not_visible", "目标线程当前不在桌面边栏可见范围内。")
            self.scroll_item_into_view(
                hwnd,
                item_name=target.name,
                project_name=target.project_name or project_name,
            )
            items = self.list_sidebar_items(hwnd)
            refreshed = self._thread_candidates(items, project_name=project_name, title=title)
            if not refreshed:
                raise UIAutomationError("target_not_visible", "目标线程滚动后仍未出现在桌面边栏中。")
            if len(refreshed) > 1:
                raise UIAutomationError("ambiguous_target", "滚动后检测到多个同名线程，已阻断以避免切错线程。")
            target = refreshed[0]
            if target.offscreen:
                raise UIAutomationError("target_not_visible", "目标线程仍未滚动到可点击位置。")

        return ThreadFocusTarget(
            matched_project=project_name,
            matched_title=target.thread_title,
            rect=target.rect,
            raw_name=target.name,
        )

    def scroll_item_into_view(self, hwnd: int, *, item_name: str, project_name: str) -> None:
        self._run(
            {
                "action": "scroll_item",
                "hwnd": hwnd,
                "itemName": item_name,
                "projectName": project_name,
            }
        )

    def get_active_title(self, hwnd: int) -> str | None:
        payload = self._run({"action": "active_title", "hwnd": hwnd})
        value = payload.get("title")
        return value if isinstance(value, str) and value.strip() else None

    def wait_for_active_title(
        self,
        hwnd: int,
        *,
        expected_title: str,
        timeout: float = 1.6,
        interval: float = 0.16,
    ) -> str:
        expected_norm = _normalize(expected_title)
        deadline = time.monotonic() + max(0.2, timeout)
        last_seen: str | None = None
        while time.monotonic() < deadline:
            current = self.get_active_title(hwnd)
            last_seen = current or last_seen
            if current and _normalize(current) == expected_norm:
                return current
            time.sleep(max(0.05, interval))
        if last_seen:
            raise UIAutomationError("verify_failed", f"切换后验证失败，当前标题是“{last_seen}”。")
        raise UIAutomationError("verify_failed", "切换后验证失败，未能读取当前线程标题。")

    def activate_new_thread(self, hwnd: int, *, workspace: str | None = None) -> NewThreadTarget:
        project_name = _workspace_basename(workspace) if workspace else None
        previous_title = self.get_active_title(hwnd)
        payload = self._run(
            {
                "action": "activate_new_thread",
                "hwnd": hwnd,
                "projectName": project_name,
            }
        )
        verified_title = self._wait_for_new_thread_state(hwnd, previous_title=previous_title)
        return NewThreadTarget(
            button_name=str(payload.get("buttonName") or "新线程"),
            verified_title=verified_title,
        )

    def _wait_for_new_thread_state(
        self,
        hwnd: int,
        *,
        previous_title: str | None,
        timeout: float = 1.2,
        interval: float = 0.16,
    ) -> str | None:
        previous_norm = _normalize(previous_title)
        deadline = time.monotonic() + max(0.2, timeout)
        while time.monotonic() < deadline:
            current = self.get_active_title(hwnd)
            if current and _normalize(current) != previous_norm:
                return current
            time.sleep(max(0.05, interval))
        return None

    def _thread_candidates(self, items: list[UIASidebarItem], *, project_name: str, title: str) -> list[UIASidebarItem]:
        project_norm = _normalize(project_name)
        title_norm = _normalize(title)
        return [
            item
            for item in items
            if item.is_thread_item
            and _normalize(item.project_name) == project_norm
            and _normalize(item.thread_title) == title_norm
        ]

    def _run(self, payload: dict[str, object]) -> dict[str, object]:
        command = _powershell_command()
        if not command:
            raise UIAutomationUnavailableError("当前系统未找到 PowerShell，无法使用 Windows UIAutomation。")
        env = os.environ.copy()
        env["CODEX_UIA_PAYLOAD_B64"] = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
        script_bytes = _POWERSHELL_SCRIPT.encode("utf-16-le")
        encoded_command = base64.b64encode(script_bytes).decode("ascii")
        try:
            completed = subprocess.run(
                [command, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12.0,
                env=env,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        except OSError as exc:
            raise UIAutomationUnavailableError(f"调用 Windows UIAutomation 失败：{exc}") from exc
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            message = stderr or stdout or "Windows UIAutomation 脚本执行失败。"
            raise UIAutomationUnavailableError(message)
        if not stdout:
            raise UIAutomationUnavailableError("Windows UIAutomation 未返回任何结果。")
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise UIAutomationUnavailableError(f"Windows UIAutomation 返回了无效 JSON：{stdout}") from exc
        if not isinstance(result, dict):
            raise UIAutomationUnavailableError("Windows UIAutomation 返回了未知结构。")
        if not result.get("ok", False):
            code = str(result.get("code") or "uia_failed")
            message = str(result.get("message") or "Windows UIAutomation 操作失败。")
            raise UIAutomationError(code, message)
        return result


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _strip_relative_time(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip()
    if not text:
        return ""
    return re.sub(
        r"\s*\d+\s*(秒|分|分钟|小时|天|周|个月|月|年|s|m|h|d|w|mo|y)\s*(ago)?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _workspace_basename(workspace: str | None) -> str:
    if not workspace:
        return ""
    normalized = workspace.rstrip("\\/")
    if not normalized:
        return ""
    return ntpath.basename(normalized)


def _powershell_command() -> str | None:
    if os.name != "nt":
        return None
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        os.path.join(system_root, "SysWOW64", "WindowsPowerShell", "v1.0", "powershell.exe"),
        "powershell.exe",
    ]
    for candidate in candidates:
        if os.path.isabs(candidate):
            if os.path.exists(candidate):
                return candidate
            continue
        return candidate
    return None


_POWERSHELL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Web.Extensions

$JsonSerializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$JsonSerializer.MaxJsonLength = 67108864
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function New-Result($ok, $extra) {
  $payload = @{ ok = [bool]$ok }
  foreach ($entry in $extra.GetEnumerator()) {
    $payload[$entry.Key] = $entry.Value
  }
  return $payload
}

function Write-Result($payload) {
  [Console]::WriteLine($JsonSerializer.Serialize($payload))
}

function Normalize-Name([string]$value) {
  if ([string]::IsNullOrWhiteSpace($value)) { return '' }
  return ($value.Normalize([Text.NormalizationForm]::FormKC)).Trim()
}

function Get-RectPayload($element) {
  $rect = $element.Current.BoundingRectangle
  return @{
    x = [double]$rect.X
    y = [double]$rect.Y
    width = [double]$rect.Width
    height = [double]$rect.Height
  }
}

function Get-ElementPayload($element, $walker) {
  $parent = $walker.GetParent($element)
  $grandparent = $null
  if ($parent) {
    $grandparent = $walker.GetParent($parent)
  }
  $scrollPattern = $null
  $invokePattern = $null
  $hasScroll = $element.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$scrollPattern)
  $hasInvoke = $element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$invokePattern)
  return @{
    name = $element.Current.Name
    controlType = $element.Current.ControlType.ProgrammaticName
    offscreen = [bool]$element.Current.IsOffscreen
    rect = Get-RectPayload $element
    parentName = if ($parent) { $parent.Current.Name } else { $null }
    parentControlType = if ($parent) { $parent.Current.ControlType.ProgrammaticName } else { $null }
    grandparentName = if ($grandparent) { $grandparent.Current.Name } else { $null }
    grandparentControlType = if ($grandparent) { $grandparent.Current.ControlType.ProgrammaticName } else { $null }
    scrollable = [bool]$hasScroll
    invokable = [bool]$hasInvoke
  }
}

function Find-ElementsByControlType($root, $controlType) {
  $condition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    $controlType
  )
  return $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
}

function Get-Root($hwndValue) {
  $hwnd = [intptr][int]$hwndValue
  $root = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
  if (-not $root) {
    throw '无法从窗口句柄读取 Codex 的无障碍树。'
  }
  return $root
}

function Read-Payload() {
  $raw = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:CODEX_UIA_PAYLOAD_B64))
  return $raw | ConvertFrom-Json
}

try {
  $payload = Read-Payload
  $root = Get-Root $payload.hwnd
  $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
  $action = [string]$payload.action

  if ($action -eq 'sidebar_items') {
    $items = @()
    $elements = Find-ElementsByControlType $root ([System.Windows.Automation.ControlType]::ListItem)
    for ($i = 0; $i -lt $elements.Count; $i++) {
      $items += Get-ElementPayload $elements.Item($i) $walker
    }
    Write-Result (New-Result $true @{ items = $items })
    exit 0
  }

  if ($action -eq 'scroll_item') {
    $elements = Find-ElementsByControlType $root ([System.Windows.Automation.ControlType]::ListItem)
    $matches = @()
    for ($i = 0; $i -lt $elements.Count; $i++) {
      $element = $elements.Item($i)
      $item = Get-ElementPayload $element $walker
      if ((Normalize-Name $item.name) -eq (Normalize-Name ([string]$payload.itemName)) -and (Normalize-Name $item.grandparentName) -eq (Normalize-Name ([string]$payload.projectName))) {
        $matches += [pscustomobject]@{
          Element = $element
          Item = $item
        }
      }
    }
    if ($matches.Count -eq 0) {
      Write-Result (New-Result $false @{ code = 'target_not_visible'; message = '目标线程未出现在当前桌面边栏中。' })
      exit 0
    }
    if ($matches.Count -gt 1) {
      Write-Result (New-Result $false @{ code = 'ambiguous_target'; message = '桌面边栏中存在多个同名线程，已阻断以避免切错。' })
      exit 0
    }
    $match = $matches[0]
    if (-not $match.Item.scrollable) {
      Write-Result (New-Result $true @{})
      exit 0
    }
    $pattern = $null
    if (-not $match.Element.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$pattern)) {
      Write-Result (New-Result $false @{ code = 'target_not_visible'; message = '目标线程当前不可滚入可见范围。' })
      exit 0
    }
    $pattern.ScrollIntoView()
    Start-Sleep -Milliseconds 180
    Write-Result (New-Result $true @{})
    exit 0
  }

  if ($action -eq 'active_title') {
    $texts = Find-ElementsByControlType $root ([System.Windows.Automation.ControlType]::Text)
    $rootRect = $root.Current.BoundingRectangle
    $candidates = @()
    for ($i = 0; $i -lt $texts.Count; $i++) {
      $element = $texts.Item($i)
      $rect = $element.Current.BoundingRectangle
      $name = $element.Current.Name
      if ([string]::IsNullOrWhiteSpace($name)) { continue }
      if ($element.Current.IsOffscreen) { continue }
      if ($rect.X -lt ($rootRect.X + ($rootRect.Width * 0.22))) { continue }
      if ($rect.Y -gt ($rootRect.Y + ($rootRect.Height * 0.22))) { continue }
      if ($rect.Width -lt 24 -or $rect.Height -lt 10) { continue }
      $candidates += [pscustomobject]@{
        name = $name
        y = [double]$rect.Y
        x = [double]$rect.X
      }
    }
    $sorted = $candidates | Sort-Object y, x
    $title = $null
    if ($sorted.Count -gt 0) {
      $title = $sorted[0].name
    }
    Write-Result (New-Result $true @{ title = $title })
    exit 0
  }

  if ($action -eq 'activate_new_thread') {
    $buttons = Find-ElementsByControlType $root ([System.Windows.Automation.ControlType]::Button)
    $preferred = if ([string]::IsNullOrWhiteSpace([string]$payload.projectName)) { $null } else { "在 $($payload.projectName) 中开始新线程" }
    $matches = @()
    for ($i = 0; $i -lt $buttons.Count; $i++) {
      $element = $buttons.Item($i)
      if ($element.Current.IsOffscreen) { continue }
      $name = $element.Current.Name
      if ([string]::IsNullOrWhiteSpace($name)) { continue }
      if ($preferred -and $name -eq $preferred) {
        $matches += $element
      }
    }
    if ($matches.Count -eq 0) {
      for ($i = 0; $i -lt $buttons.Count; $i++) {
        $element = $buttons.Item($i)
        if ($element.Current.IsOffscreen) { continue }
        if ($element.Current.Name -eq '新线程') {
          $matches += $element
        }
      }
    }
    if ($matches.Count -eq 0) {
      Write-Result (New-Result $false @{ code = 'new_thread_button_not_found'; message = '未找到可用的新线程按钮。' })
      exit 0
    }
    $button = $matches[0]
    $pattern = $null
    if (-not $button.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
      Write-Result (New-Result $false @{ code = 'new_thread_button_not_found'; message = '新线程按钮当前不可点击。' })
      exit 0
    }
    $pattern.Invoke()
    Start-Sleep -Milliseconds 180
    Write-Result (New-Result $true @{ buttonName = $button.Current.Name })
    exit 0
  }

  Write-Result (New-Result $false @{ code = 'invalid_action'; message = "不支持的 UIAutomation 动作：$action" })
  exit 0
}
catch {
  Write-Result (New-Result $false @{ code = 'uia_unavailable'; message = $_.Exception.Message })
  exit 0
}
"""
