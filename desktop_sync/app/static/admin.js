const versionEl = document.getElementById("version");
const portEl = document.getElementById("port");
const tokenEl = document.getElementById("token");
const pinEl = document.getElementById("pin");
const pinRotatedEl = document.getElementById("pin-rotated");
const configPathEl = document.getElementById("config-path");
const logPathEl = document.getElementById("log-path");
const mobileStatusEl = document.getElementById("mobile-status");
const lockedWindowEl = document.getElementById("locked-window");
const urlListEl = document.getElementById("url-list");
const recentErrorsEl = document.getElementById("recent-errors");
const resetTokenButton = document.getElementById("reset-token");
const resetPinButton = document.getElementById("reset-pin");
const connectTitleEl = document.getElementById("connect-title");
const relayStatusEl = document.getElementById("relay-status");
const relayUrlEl = document.getElementById("relay-url");
const relayNoteEl = document.getElementById("relay-note");
const relayExpiresEl = document.getElementById("relay-expires");
const relayErrorEl = document.getElementById("relay-error");
const relayQrEl = document.getElementById("relay-qr");
const relayQrPlaceholderEl = document.getElementById("relay-qr-placeholder");

async function fetchState() {
  const response = await fetch("/api/admin/state", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`加载状态失败：${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderLockedWindow(lockedWindow) {
  if (!lockedWindow) {
    lockedWindowEl.textContent = "当前还没有锁定任何窗口。";
    return;
  }
  lockedWindowEl.innerHTML = `
    <div class="stat"><span>标题</span><strong>${escapeHtml(lockedWindow.title)}</strong></div>
    <div class="stat"><span>进程</span><strong>${escapeHtml(lockedWindow.process_name)}</strong></div>
    <div class="stat"><span>HWND</span><strong class="mono">${escapeHtml(lockedWindow.hwnd)}</strong></div>
    <div class="stat"><span>锁定时间</span><strong>${new Date(lockedWindow.locked_at).toLocaleString()}</strong></div>
  `;
}

function renderUrls(candidateAddresses) {
  if (!candidateAddresses.length) {
    urlListEl.innerHTML = `
      <div class="url-item">
        <div class="label">暂未检测到可用局域网地址</div>
        <div class="muted">如需局域网备用连接，请确认电脑已经接入本地网络。</div>
      </div>
    `;
    return;
  }
  urlListEl.innerHTML = candidateAddresses
    .map((item) => `
      <div class="url-item ${item.isRecommended ? "recommended" : ""}">
        <div class="label">${escapeHtml(item.label)}</div>
        <div class="mono">${escapeHtml(item.remoteUrl)}</div>
      </div>
    `)
    .join("");
}

function renderRecentErrors(recentErrors) {
  if (!recentErrors.length) {
    recentErrorsEl.textContent = "当前没有最近问题。";
    recentErrorsEl.classList.add("muted");
    return;
  }
  recentErrorsEl.classList.remove("muted");
  recentErrorsEl.innerHTML = recentErrors
    .map((item) => `
      <div class="issue-item">
        <div><strong>${escapeHtml(item.code)}</strong> <span class="muted">(${escapeHtml(item.stage)})</span></div>
        <div>${escapeHtml(item.message)}</div>
        <div class="muted">${new Date(item.timestamp).toLocaleString()}</div>
      </div>
    `)
    .join("");
}

function relayStatusText(relay) {
  switch (relay.status) {
    case "connected":
      return "中继已连接";
    case "disconnected":
      return "中继已断开";
    default:
      return "中继连接中";
  }
}

function connectionStatusText(connection, relay) {
  if (connection?.mode === "lan-direct") {
    return "推荐使用局域网直连";
  }
  if (connection?.mode === "relay") {
    return relayStatusText(relay);
  }
  if (connection?.mode === "relay-fallback") {
    return "当前仅有本地 relay 调试地址";
  }
  return relayStatusText(relay);
}

function parseHost(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function isPrivateIpv4(host) {
  return /^10\./.test(host)
    || /^192\.168\./.test(host)
    || /^172\.(1[6-9]|2\d|3[0-1])\./.test(host);
}

function relayNoteText(relay) {
  const configuredHost = parseHost(relay.configuredUrl || "");
  const mobileHost = parseHost(relay.mobileUrl || "");
  if (!relay.mobileUrl) {
    return "等待云中继生成地址...";
  }
  if (["127.0.0.1", "localhost", "::1"].includes(mobileHost)) {
    return "当前二维码指向电脑本机地址，手机无法直接访问。若为同一 Wi‑Fi 测试，请重启本地 relay；若需跨网络使用，请配置公网 REMOTE_ASSIST_RELAY_PUBLIC_URL。";
  }
  if (["127.0.0.1", "localhost", "::1"].includes(configuredHost) && isPrivateIpv4(mobileHost)) {
    return "当前二维码已自动切换为局域网地址，仅在手机与电脑连接同一 Wi‑Fi 时可用。";
  }
  return "当前二维码可直接发给手机使用。";
}

function renderRelay(relay, connection) {
  const mobileUrl = connection?.mobileUrl || relay.mobileUrl || "";
  const mobileHost = parseHost(mobileUrl);
  connectTitleEl.textContent = connection?.label || "手机扫码连接";
  relayStatusEl.textContent = connectionStatusText(connection, relay);
  relayStatusEl.classList.toggle("offline", !mobileUrl);
  relayUrlEl.textContent = mobileUrl || "等待手机连接地址...";
  relayNoteEl.textContent = connection?.note || relayNoteText(relay);
  relayNoteEl.classList.toggle("muted", !["127.0.0.1", "localhost", "::1"].includes(mobileHost));
  relayExpiresEl.textContent = relay.expiresAt ? new Date(relay.expiresAt).toLocaleString() : "-";
  relayErrorEl.textContent = relay.lastError || "当前没有错误。";
  relayErrorEl.classList.toggle("muted", !relay.lastError);

  const qrSvgUrl = connection?.qrSvgUrl || relay.qrSvgUrl;
  if (qrSvgUrl) {
    relayQrEl.src = `${qrSvgUrl}${qrSvgUrl.includes("?") ? "&" : "?"}t=${Date.now()}`;
    relayQrEl.hidden = false;
    relayQrPlaceholderEl.hidden = true;
  } else {
    relayQrEl.removeAttribute("src");
    relayQrEl.hidden = true;
    relayQrPlaceholderEl.hidden = false;
  }
}

function renderState(state) {
  versionEl.textContent = state.version;
  portEl.textContent = state.port;
  tokenEl.textContent = state.sessionToken;
  pinEl.textContent = state.currentPin;
  pinRotatedEl.textContent = state.pinLastRotatedAt ? new Date(state.pinLastRotatedAt).toLocaleString() : "-";
  configPathEl.textContent = state.configPath;
  logPathEl.textContent = state.logPath;
  mobileStatusEl.textContent = state.mobileConnected
    ? `手机已连接（${state.mobileTransport === "relay" ? "云中继" : "局域网"}）`
    : "手机未连接";
  mobileStatusEl.classList.toggle("offline", !state.mobileConnected);
  renderRelay(state.relay || {}, state.preferredConnection || null);
  renderLockedWindow(state.lockedWindow);
  renderUrls(state.candidateAddresses || []);
  renderRecentErrors(state.recentErrors || []);
}

async function refresh() {
  try {
    renderState(await fetchState());
  } catch (error) {
    mobileStatusEl.textContent = "管理页刷新失败";
    mobileStatusEl.classList.add("offline");
    relayStatusEl.textContent = "中继状态未知";
    relayStatusEl.classList.add("offline");
    console.error(error);
  }
}

async function postAndRefresh(url) {
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  await refresh();
}

resetTokenButton.addEventListener("click", async () => {
  resetTokenButton.disabled = true;
  try {
    await postAndRefresh("/api/admin/token/reset");
  } catch (error) {
    window.alert(`操作失败：${error.message}`);
  } finally {
    resetTokenButton.disabled = false;
  }
});

resetPinButton.addEventListener("click", async () => {
  resetPinButton.disabled = true;
  try {
    await postAndRefresh("/api/admin/pin/reset");
  } catch (error) {
    window.alert(`操作失败：${error.message}`);
  } finally {
    resetPinButton.disabled = false;
  }
});

await refresh();
window.setInterval(refresh, 1500);
