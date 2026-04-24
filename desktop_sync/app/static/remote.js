const params = new URLSearchParams(window.location.search);
const token = params.get("token");
const relaySessionId = params.get("relay_session") || resolveRelaySessionFromPath();
const relayMode = Boolean(relaySessionId);

const statusEl = document.getElementById("connection-status");
const windowStatusEl = document.getElementById("window-status");
const transportStatusEl = document.getElementById("transport-status");
const previewStatusEl = document.getElementById("preview-status");
const pinInput = document.getElementById("pin-input");
const rememberPinEl = document.getElementById("remember-pin");
const connectButton = document.getElementById("connect-button");
const textInput = document.getElementById("text-input");
const sendButton = document.getElementById("send-button");
const newlineWarningEl = document.getElementById("newline-warning");
const errorEl = document.getElementById("message-error");
const previewCanvas = document.getElementById("preview-canvas");
const previewPlaceholderEl = document.getElementById("preview-placeholder");
const touchpad = document.getElementById("touchpad");

const previewContext = previewCanvas.getContext("2d", { alpha: false });

let socket = null;
let authenticated = false;
let pendingSendId = null;
let rememberedPin = "";
let reconnectTimer = null;
let blockReconnect = false;
let currentWindowTitle = "";
let currentWindowLocked = false;
let previewEnabled = false;
let previewSubscribed = false;
let previewPointerId = null;
let previewGesture = null;
let activeScrollPointerId = null;
let activeScrollTouchId = null;
let lastScrollY = null;
let lastPreviewSeq = -1;
let lastInteractionRatio = { x: 0.5, y: 0.5 };

function resolveRelaySessionFromPath() {
  const match = window.location.pathname.match(/^\/r\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function setStatus(text, offline = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("offline", offline);
}

function setPreviewStatus(text, offline = false) {
  previewStatusEl.textContent = text;
  previewStatusEl.classList.toggle("offline", offline);
}

function setWindowState(windowLocked, title = "") {
  currentWindowLocked = windowLocked;
  currentWindowTitle = title || "";
  windowStatusEl.textContent = windowLocked ? (currentWindowTitle || "已锁定窗口") : "未锁定";
  if (!windowLocked) {
    showPreviewPlaceholder("请先在电脑上把目标应用切到前台，再按 Ctrl+Alt+L 锁定窗口。");
  }
}

function setTransportState(connected) {
  if (!connected) {
    transportStatusEl.textContent = "未连接";
    return;
  }
  transportStatusEl.textContent = relayMode ? "云中继" : "同一 Wi-Fi 直连";
}

function showError(message) {
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function showPreviewPlaceholder(message) {
  previewPlaceholderEl.hidden = false;
  previewPlaceholderEl.textContent = message;
}

function hidePreviewPlaceholder() {
  previewPlaceholderEl.hidden = true;
}

function nextMessageId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function safeSend(payload, failureMessage) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    showError("连接尚未建立，无法发送。");
    setStatus("连接未就绪", true);
    updateSendState();
    return false;
  }
  try {
    socket.send(JSON.stringify(payload));
    return true;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    showError(`${failureMessage}${message ? `：${message}` : ""}`);
    setStatus("发送失败", true);
    updateSendState();
    return false;
  }
}

function updateSendState() {
  const connected = authenticated && socket && socket.readyState === WebSocket.OPEN;
  const disabled = !connected || pendingSendId !== null;
  sendButton.disabled = disabled;
  textInput.disabled = disabled;
  connectButton.disabled = socket && socket.readyState === WebSocket.CONNECTING;
}

function scheduleReconnect() {
  if (!rememberPinEl.checked || !rememberedPin || blockReconnect) {
    return;
  }
  window.clearTimeout(reconnectTimer);
  reconnectTimer = window.setTimeout(() => connect(), 1500);
}

function buildSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (relayMode) {
    return `${protocol}//${window.location.host}/ws/mobile/${encodeURIComponent(relaySessionId)}`;
  }
  return `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`;
}

function updateReadyState(windowLocked, title, previewIsEnabled) {
  authenticated = true;
  previewEnabled = Boolean(previewIsEnabled);
  previewSubscribed = false;
  setTransportState(true);
  setWindowState(Boolean(windowLocked), title || "");
  showError("");

  if (windowLocked) {
    setStatus(`已连接：${title || "已锁定窗口"}`, false);
    setPreviewStatus(previewEnabled ? "等待画面..." : "当前环境不支持", !previewEnabled);
    if (previewEnabled) {
      requestPreviewSubscription();
    } else {
      showPreviewPlaceholder("电脑端当前缺少预览依赖，暂时只能发送文本和滚动。");
    }
  } else {
    setStatus("已连接，但当前未锁定窗口", true);
    setPreviewStatus("等待锁定窗口", true);
  }
  updateSendState();
}

function connect() {
  window.clearTimeout(reconnectTimer);
  if (!relayMode && !token) {
    setStatus("缺少 Token", true);
    setTransportState(false);
    showError("请从电脑管理页打开手机访问地址，确保链接中包含会话 Token。");
    updateSendState();
    return;
  }
  if (relayMode && !relaySessionId) {
    setStatus("缺少会话", true);
    setTransportState(false);
    showError("当前云中继会话地址不完整，请重新扫码打开。");
    updateSendState();
    return;
  }
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const pin = pinInput.value.trim() || rememberedPin;
  if (!pin) {
    setStatus("需要 PIN", true);
    setTransportState(false);
    showError("请输入电脑管理页显示的 6 位会话 PIN。");
    updateSendState();
    return;
  }

  authenticated = false;
  previewSubscribed = false;
  previewEnabled = false;
  blockReconnect = false;
  setTransportState(false);
  setPreviewStatus("未开始", true);
  showError("");
  setStatus(relayMode ? "正在连接云中继..." : "连接中...", false);

  socket = new WebSocket(buildSocketUrl());

  socket.addEventListener("open", () => {
    rememberedPin = rememberPinEl.checked ? pin : "";
    setStatus("PIN 校验中...", false);
    safeSend({ type: "hello", client: "mobile-web", version: 1, pin }, "发送认证消息失败");
    updateSendState();
  });

  socket.addEventListener("message", async (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "ready") {
      updateReadyState(payload.windowLocked, payload.title, payload.previewEnabled);
      return;
    }
    if (payload.type === "state") {
      setWindowState(Boolean(payload.windowLocked), payload.title || "");
      previewEnabled = Boolean(payload.previewEnabled);
      if (payload.windowLocked) {
        setStatus(`已连接：${payload.title || "已锁定窗口"}`, false);
        if (previewEnabled && !previewSubscribed) {
          requestPreviewSubscription();
        }
      } else {
        setStatus("已连接，但当前未锁定窗口", true);
        setPreviewStatus("等待锁定窗口", true);
      }
      return;
    }
    if (payload.type === "preview.frame") {
      await renderPreviewFrame(payload);
      return;
    }
    if (payload.type === "preview.unavailable") {
      setPreviewStatus("预览暂不可用", true);
      showPreviewPlaceholder(payload.message || "当前无法获得锁定窗口画面。");
      return;
    }
    if (payload.type === "ack" && payload.id === pendingSendId) {
      pendingSendId = null;
      textInput.value = "";
      newlineWarningEl.hidden = true;
      showError("");
      setStatus(
        currentWindowLocked ? `已发送到：${currentWindowTitle || "已锁定窗口"}` : "已连接，但当前未锁定窗口",
        !currentWindowLocked,
      );
      updateSendState();
      return;
    }
    if (payload.type === "error") {
      if (payload.id === pendingSendId) {
        pendingSendId = null;
      }
      if (["invalid_pin", "pin_throttled", "invalid_token", "session_busy"].includes(payload.code)) {
        blockReconnect = true;
        authenticated = false;
        setTransportState(false);
      }
      if (payload.code === "window_not_locked" || payload.code === "window_missing") {
        setWindowState(false, "");
        setPreviewStatus("等待锁定窗口", true);
      }
      if (payload.code === "focus_failed") {
        setStatus("电脑无法切回目标窗口", true);
      }
      showError(payload.message || payload.code || "发生了未知错误。");
      updateSendState();
    }
  });

  socket.addEventListener("error", () => {
    setStatus("网络连接异常", true);
    setPreviewStatus("连接异常", true);
  });

  socket.addEventListener("close", () => {
    authenticated = false;
    pendingSendId = null;
    previewSubscribed = false;
    setTransportState(false);
    setPreviewStatus(blockReconnect ? "已断开" : "等待重连", true);
    setStatus(blockReconnect ? "已断开连接" : "连接已断开，正在重试...", true);
    updateSendState();
    if (!blockReconnect) {
      scheduleReconnect();
    }
  });
}

function requestPreviewSubscription() {
  if (!authenticated || !previewEnabled || previewSubscribed) {
    return;
  }
  previewSubscribed = true;
  setPreviewStatus("等待画面...", false);
  if (!safeSend({ type: "preview.subscribe", id: nextMessageId() }, "开启预览失败")) {
    previewSubscribed = false;
  }
}

async function renderPreviewFrame(payload) {
  if (typeof payload.seq === "number" && payload.seq <= lastPreviewSeq) {
    return;
  }
  if (typeof payload.seq === "number") {
    lastPreviewSeq = payload.seq;
  }
  const bytes = base64ToUint8Array(payload.data || "");
  if (!bytes.length) {
    return;
  }
  const blob = new Blob([bytes], { type: "image/jpeg" });
  if ("createImageBitmap" in window) {
    const bitmap = await createImageBitmap(blob);
    drawPreviewBitmap(bitmap, payload.width, payload.height);
    bitmap.close();
  } else {
    await drawPreviewImage(blob, payload.width, payload.height);
  }
  hidePreviewPlaceholder();
  setPreviewStatus(`实时预览 ${payload.width}×${payload.height}`, false);
}

function drawPreviewBitmap(bitmap, width, height) {
  if (previewCanvas.width !== width || previewCanvas.height !== height) {
    previewCanvas.width = width;
    previewCanvas.height = height;
  }
  previewContext.drawImage(bitmap, 0, 0, width, height);
}

function drawPreviewImage(blob, width, height) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(blob);
    image.onload = () => {
      if (previewCanvas.width !== width || previewCanvas.height !== height) {
        previewCanvas.width = width;
        previewCanvas.height = height;
      }
      previewContext.drawImage(image, 0, 0, width, height);
      URL.revokeObjectURL(url);
      resolve();
    };
    image.onerror = (error) => {
      URL.revokeObjectURL(url);
      reject(error);
    };
    image.src = url;
  });
}

function base64ToUint8Array(value) {
  const binary = window.atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function ensureInteractivePreview() {
  if (!authenticated) {
    showError("连接尚未建立，暂时不能操作预览。");
    return false;
  }
  if (!currentWindowLocked) {
    showError("电脑端还没有锁定目标窗口。请先把目标应用切到前台，再按 Ctrl+Alt+L。");
    setStatus("等待电脑锁定窗口", true);
    return false;
  }
  return true;
}

function previewRatioFromEvent(event) {
  const rect = previewCanvas.getBoundingClientRect();
  const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
  const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
  return { x, y };
}

function beginPreviewGesture(event) {
  if (!ensureInteractivePreview()) {
    return;
  }
  previewPointerId = event.pointerId;
  previewCanvas.setPointerCapture(event.pointerId);
  const ratio = previewRatioFromEvent(event);
  lastInteractionRatio = ratio;
  previewGesture = {
    startClientX: event.clientX,
    startClientY: event.clientY,
    startRatio: ratio,
    lastRatio: ratio,
    dragging: false,
  };
  showError("");
}

function movePreviewGesture(event) {
  if (event.pointerId !== previewPointerId || !previewGesture) {
    return;
  }
  const ratio = previewRatioFromEvent(event);
  lastInteractionRatio = ratio;
  previewGesture.lastRatio = ratio;
  const dx = event.clientX - previewGesture.startClientX;
  const dy = event.clientY - previewGesture.startClientY;
  const distance = Math.hypot(dx, dy);
  if (!previewGesture.dragging && distance >= 10) {
    previewGesture.dragging = safeSend(
      {
        type: "pointer.down",
        id: nextMessageId(),
        xRatio: previewGesture.startRatio.x,
        yRatio: previewGesture.startRatio.y,
      },
      "开始拖动失败",
    );
  }
  if (previewGesture.dragging) {
    safeSend({ type: "pointer.move", id: nextMessageId(), xRatio: ratio.x, yRatio: ratio.y }, "发送拖动失败");
  }
}

function endPreviewGesture(event) {
  if (event.pointerId !== previewPointerId || !previewGesture) {
    return;
  }
  const ratio = previewRatioFromEvent(event);
  lastInteractionRatio = ratio;
  if (previewGesture.dragging) {
    safeSend({ type: "pointer.up", id: nextMessageId(), xRatio: ratio.x, yRatio: ratio.y }, "结束拖动失败");
  } else {
    const clickDown = safeSend(
      {
        type: "pointer.down",
        id: nextMessageId(),
        xRatio: ratio.x,
        yRatio: ratio.y,
      },
      "点击失败",
    );
    if (clickDown) {
      safeSend({ type: "pointer.up", id: nextMessageId(), xRatio: ratio.x, yRatio: ratio.y }, "点击失败");
    }
  }
  previewPointerId = null;
  previewGesture = null;
}

function cancelPreviewGesture() {
  if (previewGesture?.dragging) {
    const ratio = previewGesture.lastRatio;
    safeSend({ type: "pointer.up", id: nextMessageId(), xRatio: ratio.x, yRatio: ratio.y }, "取消拖动失败");
  }
  previewPointerId = null;
  previewGesture = null;
}

function touchEventRatio(touch) {
  const rect = previewCanvas.getBoundingClientRect();
  return {
    x: Math.min(1, Math.max(0, (touch.clientX - rect.left) / rect.width)),
    y: Math.min(1, Math.max(0, (touch.clientY - rect.top) / rect.height)),
  };
}

function beginScroll(clientY) {
  if (!ensureInteractivePreview()) {
    return false;
  }
  lastScrollY = clientY;
  touchpad.classList.add("active");
  showError("");
  return true;
}

function moveScroll(clientY) {
  if (lastScrollY === null || !authenticated) {
    return;
  }
  const dy = clientY - lastScrollY;
  if (Math.abs(dy) < 2) {
    return;
  }
  lastScrollY = clientY;
  safeSend(
    {
      type: "gesture.scroll",
      id: nextMessageId(),
      xRatio: lastInteractionRatio.x,
      yRatio: lastInteractionRatio.y,
      dy,
    },
    "发送滚动消息失败",
  );
}

function endScroll() {
  activeScrollPointerId = null;
  activeScrollTouchId = null;
  lastScrollY = null;
  touchpad.classList.remove("active");
}

connectButton.addEventListener("click", () => {
  connect();
});

sendButton.addEventListener("click", () => {
  const text = textInput.value;
  if (!text || !authenticated || pendingSendId !== null) {
    return;
  }
  if (!currentWindowLocked) {
    showError("电脑端还没有锁定目标窗口。请先把目标应用切到前台，再按 Ctrl+Alt+L。");
    setStatus("等待电脑锁定窗口", true);
    return;
  }
  pendingSendId = nextMessageId();
  newlineWarningEl.hidden = !text.endsWith("\n");
  showError("");
  if (!safeSend({ type: "text.send", id: pendingSendId, text }, "发送文本失败")) {
    pendingSendId = null;
  }
  updateSendState();
});

if ("PointerEvent" in window) {
  previewCanvas.addEventListener("pointerdown", (event) => {
    beginPreviewGesture(event);
  });
  previewCanvas.addEventListener("pointermove", (event) => {
    movePreviewGesture(event);
  });
  previewCanvas.addEventListener("pointerup", (event) => {
    endPreviewGesture(event);
  });
  previewCanvas.addEventListener("pointercancel", () => {
    cancelPreviewGesture();
  });

  touchpad.addEventListener("pointerdown", (event) => {
    if (!beginScroll(event.clientY)) {
      return;
    }
    activeScrollPointerId = event.pointerId;
    touchpad.setPointerCapture(event.pointerId);
  });
  touchpad.addEventListener("pointermove", (event) => {
    if (event.pointerId !== activeScrollPointerId) {
      return;
    }
    moveScroll(event.clientY);
  });
  touchpad.addEventListener("pointerup", (event) => {
    if (event.pointerId !== activeScrollPointerId) {
      return;
    }
    endScroll();
  });
  touchpad.addEventListener("pointercancel", (event) => {
    if (event.pointerId !== activeScrollPointerId) {
      return;
    }
    endScroll();
  });
} else {
  let activePreviewTouchId = null;

  previewCanvas.addEventListener(
    "touchstart",
    (event) => {
      const touch = event.changedTouches[0];
      if (!touch || !ensureInteractivePreview()) {
        return;
      }
      activePreviewTouchId = touch.identifier;
      const ratio = touchEventRatio(touch);
      lastInteractionRatio = ratio;
      previewGesture = {
        startClientX: touch.clientX,
        startClientY: touch.clientY,
        startRatio: ratio,
        lastRatio: ratio,
        dragging: false,
      };
      showError("");
    },
    { passive: true },
  );

  previewCanvas.addEventListener(
    "touchmove",
    (event) => {
      const touch = Array.from(event.changedTouches).find((item) => item.identifier === activePreviewTouchId);
      if (!touch || !previewGesture) {
        return;
      }
      event.preventDefault();
      const ratio = touchEventRatio(touch);
      lastInteractionRatio = ratio;
      previewGesture.lastRatio = ratio;
      const dx = touch.clientX - previewGesture.startClientX;
      const dy = touch.clientY - previewGesture.startClientY;
      if (!previewGesture.dragging && Math.hypot(dx, dy) >= 10) {
        previewGesture.dragging = safeSend(
          {
            type: "pointer.down",
            id: nextMessageId(),
            xRatio: previewGesture.startRatio.x,
            yRatio: previewGesture.startRatio.y,
          },
          "开始拖动失败",
        );
      }
      if (previewGesture.dragging) {
        safeSend({ type: "pointer.move", id: nextMessageId(), xRatio: ratio.x, yRatio: ratio.y }, "发送拖动失败");
      }
    },
    { passive: false },
  );

  const finishTouchPreview = (touch) => {
    if (!touch || !previewGesture) {
      activePreviewTouchId = null;
      previewGesture = null;
      return;
    }
    const ratio = touchEventRatio(touch);
    lastInteractionRatio = ratio;
    if (previewGesture.dragging) {
      safeSend({ type: "pointer.up", id: nextMessageId(), xRatio: ratio.x, yRatio: ratio.y }, "结束拖动失败");
    } else {
      const clickDown = safeSend(
        {
          type: "pointer.down",
          id: nextMessageId(),
          xRatio: ratio.x,
          yRatio: ratio.y,
        },
        "点击失败",
      );
      if (clickDown) {
        safeSend({ type: "pointer.up", id: nextMessageId(), xRatio: ratio.x, yRatio: ratio.y }, "点击失败");
      }
    }
    activePreviewTouchId = null;
    previewGesture = null;
  };

  previewCanvas.addEventListener(
    "touchend",
    (event) => {
      const touch = Array.from(event.changedTouches).find((item) => item.identifier === activePreviewTouchId);
      finishTouchPreview(touch || event.changedTouches[0]);
    },
    { passive: true },
  );

  previewCanvas.addEventListener(
    "touchcancel",
    (event) => {
      const touch = Array.from(event.changedTouches).find((item) => item.identifier === activePreviewTouchId);
      finishTouchPreview(touch || event.changedTouches[0]);
    },
    { passive: true },
  );

  touchpad.addEventListener(
    "touchstart",
    (event) => {
      const touch = event.changedTouches[0];
      if (!touch || !beginScroll(touch.clientY)) {
        return;
      }
      activeScrollTouchId = touch.identifier;
    },
    { passive: true },
  );

  touchpad.addEventListener(
    "touchmove",
    (event) => {
      const touch = Array.from(event.changedTouches).find((item) => item.identifier === activeScrollTouchId);
      if (!touch) {
        return;
      }
      event.preventDefault();
      moveScroll(touch.clientY);
    },
    { passive: false },
  );

  touchpad.addEventListener("touchend", () => {
    endScroll();
  });

  touchpad.addEventListener("touchcancel", () => {
    endScroll();
  });
}

if (rememberPinEl.checked) {
  rememberedPin = pinInput.value.trim();
}

previewCanvas.width = 960;
previewCanvas.height = 640;
previewContext.fillStyle = "#0d1720";
previewContext.fillRect(0, 0, previewCanvas.width, previewCanvas.height);
showPreviewPlaceholder("连接成功后将开始接收锁定窗口画面。");
setPreviewStatus("未开始", true);
setWindowState(false, "");
setTransportState(false);
updateSendState();
