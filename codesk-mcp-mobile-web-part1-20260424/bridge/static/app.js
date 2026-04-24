const $ = (id) => document.getElementById(id);

const dom = {
  authShell: $("auth-shell"),
  backendStatus: $("backend-status"),
  relayStatus: $("relay-status"),
  pairCode: $("pair-code"),
  pairButton: $("pair-button"),
  pairStatus: $("pair-status"),
  topbarStatus: $("topbar-status"),
  openLibrary: $("open-library"),
  openCompose: $("open-compose"),
  openWall: $("open-wall"),
  libraryCompose: $("library-compose"),
  followActive: $("follow-active"),
  langToggle: $("lang-toggle"),
  themeToggle: $("theme-toggle"),
  openSettings: $("open-settings"),
  overlay: $("overlay"),
  libraryPanel: $("library-panel"),
  libraryMark: $("library-mark"),
  liveMark: $("live-mark"),
  recentMark: $("recent-mark"),
  liveList: $("live-list"),
  recentList: $("recent-list"),
  historyFold: $("history-fold"),
  historySummary: $("history-summary"),
  historyList: $("history-list"),
  emptyView: $("empty-view"),
  emptyCopy: $("empty-copy"),
  wallView: $("wall-view"),
  sessionView: $("session-view"),
  sessionContext: $("session-context"),
  cancelSession: $("cancel-session"),
  approvalStrip: $("approval-strip"),
  desktopApprovalStrip: $("desktop-approval-strip"),
  activityStrip: $("activity-strip"),
  conversationLog: $("conversation-log"),
  sessionDebug: $("session-debug"),
  sessionDebugSummary: $("session-debug-summary"),
  debugLog: $("debug-log"),
  composerDock: $("composer-dock"),
  composer: $("composer"),
  attachmentStrip: $("attachment-strip"),
  attachImage: $("attach-image"),
  imageInput: $("image-input"),
  followupInput: $("followup-input"),
  sendFollowup: $("send-followup"),
  threadView: $("thread-view"),
  threadContext: $("thread-context"),
  resumeThread: $("resume-thread"),
  threadSummary: $("thread-summary"),
  threadLog: $("thread-log"),
  threadDebugFold: $("thread-debug-fold"),
  threadDebugSummary: $("thread-debug-summary"),
  threadDebug: $("thread-debug"),
  threadDock: $("thread-dock"),
  resumeThreadInline: $("resume-thread-inline"),
  jumpLatest: $("jump-latest"),
  composePanel: $("compose-panel"),
  composeMark: $("compose-mark"),
  closeCompose: $("close-compose"),
  workspaceSelect: $("workspace-select"),
  titleInput: $("title-input"),
  promptInput: $("prompt-input"),
  createSession: $("create-session"),
  settingsPanel: $("settings-panel"),
  settingsMark: $("settings-mark"),
  closeSettings: $("close-settings"),
  settingsBackend: $("settings-backend"),
  settingsRoute: $("settings-route"),
  settingsSync: $("settings-sync"),
  refreshAll: $("refresh-all"),
  viewActionsPanel: $("view-actions-panel"),
  viewActionsMark: $("view-actions-mark"),
  closeViewActions: $("close-view-actions"),
  viewActionsTitle: $("view-actions-title"),
  viewActionsDetails: $("view-actions-details"),
  viewActionsPrimary: $("view-actions-primary"),
  readerPanel: $("reader-panel"),
  readerMark: $("reader-mark"),
  closeReader: $("close-reader"),
  readerMeta: $("reader-meta"),
  readerContent: $("reader-content"),
  desktopApprovalPanel: $("desktop-approval-panel"),
  desktopApprovalMark: $("desktop-approval-mark"),
  closeDesktopApproval: $("close-desktop-approval"),
  desktopApprovalStatus: $("desktop-approval-status"),
  desktopPreviewStage: $("desktop-preview-stage"),
  desktopPreviewImage: $("desktop-preview-image"),
  desktopPreviewEmpty: $("desktop-preview-empty"),
};

const ACTIVE_THREAD_STATUSES = new Set([
  "running",
  "waiting",
  "blocked",
  "needs-approval",
  "approval-required",
]);

const I18N = {
  "zh-CN": {
    authChecking: "检查后端中...",
    routeDetecting: "检测连接方式...",
    pairPlaceholder: "配对码",
    notPaired: "未配对",
    pairing: "配对中...",
    paired: "已配对",
    sessionExpired: "会话已失效",
    connect: "连接",
    openLibrary: "线程库",
    newSession: "新建",
    settings: "设置",
    more: "更多",
    actions: "操作",
    close: "关闭",
    details: "详情",
    language: "语言",
    theme: "主题",
    live: "运行中",
    recent: "最近",
    history: "历史",
    today: "今天",
    thisWeek: "本周",
    older: "更早",
    emptyView: "选择一个当前会话或线程。",
    continuePlaceholder: "继续输入...",
    startPlaceholder: "开始一个任务...",
    titlePlaceholder: "标题（可选）",
    cancelSession: "取消",
    adoptThread: "接管",
    openSession: "打开",
    continueThread: "继续此线程",
    desktopAligning: "正在切换桌面线程...",
    desktopAlignRequired: "请先点击继续此线程完成桌面对齐",
    desktopAlignFailed: "目标线程不在桌面左栏可见范围，请在 Codex 中滚到可见后重试",
    jumpLatest: "回到最新",
    debug: "原始",
    statusTitle: "状态",
    refresh: "刷新",
    backend: "后端",
    route: "连接",
    sync: "同步",
    workspace: "工作区",
    path: "路径",
    preview: "摘要",
    sourceLabel: "来源",
    updatedLabel: "更新时间",
    reasoning: "推理",
    user: "用户",
    assistant: "助手",
    draft: "生成中",
    tools: "工具",
    approval: "审批",
    plan: "计划",
    diff: "变更",
    done: "已完成",
    failed: "失败",
    queued: "已发送",
    sentWaiting: "已发送，等待响应",
    sendFailed: "发送失败",
    synced: "已同步",
    running: "进行中",
    waiting: "待审批",
    completed: "已完成",
    cancelled: "已取消",
    imported: "已接入",
    idle: "空闲",
    linked: "已接入",
    newKind: "新建",
    resumeKind: "恢复",
    adoptedKind: "已接管",
    desktopLive: "桌面实时",
    desktopReady: "桌面就绪",
    degraded: "降级",
    keyboardSend: "键盘发送",
    keyboardSendHint: "需保持桌面输入框聚焦",
    autoFollow: "自动跟随",
    manualFollow: "手动浏览",
    lanDirect: "局域网直连",
    relay: "中继",
    direct: "直连",
    routeConnected: "已连接",
    routeDisconnected: "已断开",
    routeError: "异常",
    bridgeOffline: "桥接离线",
    syncIdle: "空闲",
    syncLive: "实时",
    syncPartial: "部分失败",
    syncSyncing: "同步中",
    syncCreating: "创建中",
    latestProgress: "最新进度",
    noDebugEvents: "暂无原始事件",
    noTurnData: "暂无线程原始数据",
    noLiveSessions: "暂无运行中会话",
    noRecentThreads: "暂无最近线程",
    approvalRequired: "需要审批",
    sessionCompleted: "会话已完成",
    sessionFailed: "会话失败",
    planUpdated: "计划已更新",
    diffUpdated: "变更已更新",
    toolRunning: "运行中",
    toolCompleted: "已完成",
    loading: "加载中...",
    loadFailed: "\u52a0\u8f7d\u5931\u8d25",
    tapRefresh: "\u53ef\u5237\u65b0\u91cd\u8bd5",
    codexRemote: "Codex Remote",
    start: "开始",
    send: "发送",
    black: "黑",
    white: "白",
    zh: "中",
    en: "EN",
    inputPrompt: "输入",
    active: "当前",
    adopted: "已接管",
    untitled: "未命名",
    ready: "就绪",
    unavailable: "不可用",
    liveCount: "运行中 {count}",
    threadTurn: "线程 {count}",
    updatedAt: "更新 {time}",
    syncAt: "同步 {time}",
    tool: "工具",
    event: "事件",
    desktopApprovalTitle: "桌面待审批",
    desktopApprovalHint: "桌面端出现了待审批事项，可在手机预览里直接处理。",
    openDesktopApproval: "打开预览处理",
    desktopApprovalUnavailable: "桌面预览暂不可用",
    desktopApprovalPanel: "桌面审批",
    desktopPreviewWaiting: "正在连接桌面预览...",
    desktopPreviewUnavailable: "桌面预览当前不可用",
  },
  en: {
    authChecking: "Checking backend...",
    routeDetecting: "Detecting route...",
    pairPlaceholder: "Pair code",
    notPaired: "Not paired",
    pairing: "Pairing...",
    paired: "Paired",
    sessionExpired: "Session expired",
    connect: "Connect",
    openLibrary: "Threads",
    newSession: "New",
    settings: "Settings",
    more: "More",
    actions: "Actions",
    close: "Close",
    details: "Details",
    language: "Language",
    theme: "Theme",
    live: "Live",
    recent: "Recent",
    history: "History",
    today: "Today",
    thisWeek: "This Week",
    older: "Older",
    emptyView: "Select a live session or thread.",
    continuePlaceholder: "Continue...",
    startPlaceholder: "Start a task...",
    titlePlaceholder: "Title (optional)",
    cancelSession: "Cancel",
    adoptThread: "Adopt",
    openSession: "Open",
    continueThread: "Continue this thread",
    desktopAligning: "Switching desktop thread...",
    desktopAlignRequired: "Continue this thread first to align the desktop",
    desktopAlignFailed: "Target thread is not visible in the desktop sidebar. Scroll it into view in Codex and retry.",
    jumpLatest: "Latest",
    debug: "Raw",
    statusTitle: "Status",
    refresh: "Refresh",
    backend: "Backend",
    route: "Route",
    sync: "Sync",
    workspace: "Workspace",
    path: "Path",
    preview: "Preview",
    sourceLabel: "Source",
    updatedLabel: "Updated",
    reasoning: "Reasoning",
    user: "User",
    assistant: "Assistant",
    draft: "Draft",
    tools: "Tools",
    approval: "Approval",
    plan: "Plan",
    diff: "Diff",
    done: "Done",
    failed: "Failed",
    queued: "Queued",
    sentWaiting: "Sent, waiting for reply",
    sendFailed: "Send failed",
    synced: "Synced",
    running: "Running",
    waiting: "Approval",
    completed: "Done",
    cancelled: "Cancelled",
    imported: "Linked",
    idle: "Idle",
    linked: "Linked",
    newKind: "New",
    resumeKind: "Resume",
    adoptedKind: "Adopted",
    desktopLive: "Desktop Live",
    desktopReady: "Desktop Ready",
    degraded: "Degraded",
    keyboardSend: "Keyboard Send",
    keyboardSendHint: "Keep the desktop composer focused",
    autoFollow: "Auto Follow",
    manualFollow: "Manual Browse",
    lanDirect: "LAN Direct",
    relay: "Relay",
    direct: "Direct",
    routeConnected: "Connected",
    routeDisconnected: "Disconnected",
    routeError: "Error",
    bridgeOffline: "Bridge Offline",
    syncIdle: "Idle",
    syncLive: "Live",
    syncPartial: "Partial",
    syncSyncing: "Syncing",
    syncCreating: "Creating",
    latestProgress: "Latest Progress",
    noDebugEvents: "No debug events",
    noTurnData: "No raw turn data",
    noLiveSessions: "No live sessions",
    noRecentThreads: "No recent threads",
    approvalRequired: "Approval required",
    sessionCompleted: "Session completed",
    sessionFailed: "Session failed",
    planUpdated: "Plan updated",
    diffUpdated: "Diff updated",
    toolRunning: "Running",
    toolCompleted: "Completed",
    loading: "Loading...",
    loadFailed: "Load failed",
    tapRefresh: "Refresh to retry",
    codexRemote: "Codex Remote",
    start: "Start",
    send: "Send",
    black: "Dark",
    white: "Light",
    zh: "中",
    en: "EN",
    inputPrompt: "Input",
    active: "Active",
    adopted: "Adopted",
    untitled: "Untitled",
    ready: "Ready",
    unavailable: "Unavailable",
    liveCount: "{count} live",
    threadTurn: "Turn {count}",
    updatedAt: "Updated {time}",
    syncAt: "Synced {time}",
    tool: "Tool",
    event: "Event",
    desktopApprovalTitle: "Desktop approval",
    desktopApprovalHint: "The desktop client is waiting for approval. Open the preview to handle it on mobile.",
    openDesktopApproval: "Open preview",
    desktopApprovalUnavailable: "Desktop preview unavailable",
    desktopApprovalPanel: "Desktop approval",
    desktopPreviewWaiting: "Connecting desktop preview...",
    desktopPreviewUnavailable: "Desktop preview is unavailable right now",
  },
};

const relaySessionId = location.pathname.startsWith("/r/")
  ? decodeURIComponent(location.pathname.split("/").filter(Boolean).at(-1))
  : null;

const state = {
  mode: relaySessionId ? "relay" : "direct",
  relaySessionId,
  accessToken: "",
  currentView: "remote",
  ui: {
    lang: "zh-CN",
    theme: "dark",
  },
  backendAvailable: false,
  backendName: "",
  backendError: "",
  routeStatus: relaySessionId ? "relay" : "direct",
  syncStatus: "idle",
  workspaces: [],
  threads: [],
  sessions: [],
  activeSession: {
    activeSessionId: null,
    source: null,
    updatedAt: null,
  },
  currentSessionId: null,
  currentSession: null,
  currentThreadId: null,
  currentThread: null,
  approvals: [],
  pendingAttachments: [],
  sessionEvents: [],
  assistantDraft: "",
  autoFollow: window.matchMedia("(min-width: 1100px)").matches,
  uiUnsubscribe: null,
  sessionUnsubscribe: null,
  refreshTimer: null,
  sessionTicket: 0,
  threadTicket: 0,
  sending: false,
  aligningThread: false,
  pairing: false,
  threadsLoaded: false,
  threadsLoading: false,
  threadsError: "",
  sessionsLoaded: false,
  sessionsLoading: false,
  sessionsError: "",
  isNearLatest: true,
  hasUnreadBelow: false,
  pendingScrollToLatest: false,
  historyOpen: false,
  mobileExpanded: Object.create(null),
  mobileReaderItems: Object.create(null),
  readerItem: null,
  desktopPreview: {
    socket: null,
    connected: false,
    status: "idle",
    frameSrc: "",
    unavailable: "",
    pointerActive: false,
  },
  wall: {
    items: [],
    query: "",
    tag: "all",
    favoritesOnly: false,
    editingId: null,
  },
};

const MAX_IMAGE_ATTACHMENTS = 4;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_IMAGE_EDGE = 1600;

const PLAN_LONG_PRESS_MS = 420;
const longPressState = {
  createTimer: null,
  createTriggered: false,
  sendTimer: null,
  sendTriggered: false,
};

function storageKey() {
  if (state.mode === "relay") {
    return `codex.remote.token:relay:${state.relaySessionId}`;
  }
  return `codex.remote.token:direct:${location.origin}`;
}

function saveToken(token) {
  state.accessToken = token;
  localStorage.setItem(storageKey(), token);
}

function clearToken() {
  state.accessToken = "";
  localStorage.removeItem(storageKey());
}

function preferenceKey(name) {
  return `codex.remote.ui:${name}`;
}

function loadPreference(name, fallback) {
  return localStorage.getItem(preferenceKey(name)) || fallback;
}

function savePreference(name, value) {
  localStorage.setItem(preferenceKey(name), value);
}

function wallStorageKey() {
  if (state.mode === "relay") {
    return `codex.remote.wall:relay:${state.relaySessionId}`;
  }
  return `codex.remote.wall:direct:${location.origin}`;
}

function normalizeWallTags(value) {
  return [...new Set(
    String(value ?? "")
      .split(/[\n,#]+/)
      .map((item) => item.trim())
      .filter(Boolean),
  )].slice(0, 8);
}

function loadWallItems() {
  try {
    const raw = localStorage.getItem(wallStorageKey());
    const parsed = raw ? JSON.parse(raw) : [];
    state.wall.items = Array.isArray(parsed) ? parsed.filter((item) => item && item.id) : [];
  } catch (error) {
    state.wall.items = [];
  }
}

function saveWallItems() {
  localStorage.setItem(wallStorageKey(), JSON.stringify(state.wall.items));
}

function wallDraftItem() {
  return state.wall.items.find((item) => item.id === state.wall.editingId) || null;
}

function sortedWallItems(items = state.wall.items) {
  return [...items].sort((left, right) => {
    if (Boolean(left.favorite) !== Boolean(right.favorite)) {
      return left.favorite ? -1 : 1;
    }
    return new Date(right.updatedAt || right.createdAt || 0).getTime() - new Date(left.updatedAt || left.createdAt || 0).getTime();
  });
}

function wallTagOptions() {
  return [...new Set(state.wall.items.flatMap((item) => Array.isArray(item.tags) ? item.tags : []))].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

function filteredWallItems() {
  const query = state.wall.query.trim().toLowerCase();
  return sortedWallItems().filter((item) => {
    if (state.wall.favoritesOnly && !item.favorite) {
      return false;
    }
    if (state.wall.tag !== "all" && !(item.tags || []).includes(state.wall.tag)) {
      return false;
    }
    if (!query) {
      return true;
    }
    const haystack = [item.title, item.content, ...(item.tags || [])]
      .join("\n")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function resetWallComposer() {
  state.wall.editingId = null;
}

function openWallView() {
  state.currentView = "wall";
  setPanel(dom.libraryPanel, false);
  setPanel(dom.composePanel, false);
  setPanel(dom.settingsPanel, false);
  setPanel(dom.viewActionsPanel, false);
  setPanel(dom.readerPanel, false);
  renderMainView();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function shortText(value, max = 120) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function t(key) {
  const bundle = I18N[state.ui.lang] || I18N["zh-CN"];
  return bundle[key] || key;
}

function statusLabel(status) {
  const key = String(status ?? "").trim().toLowerCase();
  const labels = {
    running: t("running"),
    waiting: t("waiting"),
    completed: t("completed"),
    failed: t("failed"),
    cancelled: t("cancelled"),
    imported: t("linked"),
    idle: t("idle"),
    notloaded: t("idle"),
    "not-loaded": t("idle"),
    "approval-required": t("waiting"),
    "needs-approval": t("waiting"),
  };
  return labels[key] || key || t("idle");
}

function sessionKindLabel(kind) {
  const key = String(kind ?? "").trim();
  const labels = {
    new: t("newKind"),
    manual_resume: t("resumeKind"),
    auto_adopted: t("adoptedKind"),
  };
  return labels[key] || key || t("newKind");
}

function sessionSyncLabel(session) {
  if (!session) {
    return "";
  }
  const hasThread = Boolean(sessionThreadId(session));
  if (session.deliveryRoute === "desktop_gui" && session.desktopAutomationReady) {
    return t("desktopLive");
  }
  if (session.desktopAutomationReady) {
    return t("desktopReady");
  }
  if (hasThread) {
    return t("degraded");
  }
  return "";
}

function sessionSyncHint(session) {
  if (!session) {
    return "";
  }
  if (session.desktopAutomationReady && sessionThreadId(session)) {
    return `${t("keyboardSend")} · ${t("keyboardSendHint")}`;
  }
  return "";
}

function actionLabel(action) {
  const key = String(action || "").trim().toLowerCase();
  const labels = {
    approve: state.ui.lang === "zh-CN" ? "批准" : "Approve",
    approve_session: state.ui.lang === "zh-CN" ? "本会话批准" : "Approve Session",
    reject: state.ui.lang === "zh-CN" ? "拒绝" : "Reject",
    cancel: state.ui.lang === "zh-CN" ? "取消" : "Cancel",
    submit: state.ui.lang === "zh-CN" ? "提交" : "Submit",
    open: t("openSession"),
  };
  return labels[key] || action;
}

function formatTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(state.ui.lang, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function dayBucket(value) {
  const date = new Date(value ?? 0);
  const now = new Date();
  if (Number.isNaN(date.getTime())) {
    return "older";
  }
  const diffDays = Math.floor((now.setHours(0, 0, 0, 0) - date.setHours(0, 0, 0, 0)) / 86400000);
  if (diffDays <= 0) {
    return "today";
  }
  if (diffDays <= 6) {
    return "thisWeek";
  }
  return "older";
}

function bucketLabel(bucket) {
  if (bucket === "today") {
    return t("today");
  }
  if (bucket === "thisWeek") {
    return t("thisWeek");
  }
  return t("older");
}

function isDesktop() {
  return window.matchMedia("(min-width: 1100px)").matches;
}

function isMobilePlainMode() {
  return !isDesktop();
}

function collapseButtonLabel(expanded) {
  return expanded ? t("close") : t("more");
}

function mobileExpandKey(...parts) {
  return parts
    .map((item) => String(item ?? "").trim())
    .filter(Boolean)
    .join(":");
}

function isMobileExpanded(key) {
  return Boolean(state.mobileExpanded[key]);
}

function toggleMobileExpanded(key) {
  if (!key) {
    return;
  }
  if (state.mobileExpanded[key]) {
    delete state.mobileExpanded[key];
  } else {
    state.mobileExpanded[key] = true;
  }
  renderMainView();
}

function shouldCollapseMobileText(value) {
  if (!isMobilePlainMode()) {
    return false;
  }
  const text = normalizeDisplayText(value);
  if (!text) {
    return false;
  }
  return text.length > 160 || text.split("\n").length > 6;
}

function mobileExcerptText(value, maxLines = 6, maxChars = 160) {
  const text = normalizeDisplayText(value);
  if (!text) {
    return "";
  }
  const lines = text.split("\n");
  const kept = [];
  let usedChars = 0;
  for (const line of lines) {
    if (kept.length >= maxLines || usedChars >= maxChars) {
      break;
    }
    const remaining = maxChars - usedChars;
    const slice = line.slice(0, remaining);
    kept.push(slice);
    usedChars += slice.length;
    if (slice.length < line.length) {
      break;
    }
  }
  const excerpt = kept.join("\n").trimEnd();
  return excerpt.length < text.length ? `${excerpt}…` : excerpt;
}

function mobilePreviewSnippet(value, maxChars = 72) {
  const text = normalizeDisplayText(value).replace(/\s+/g, " ").trim();
  if (!text) {
    return "";
  }
  return shortText(text, maxChars);
}

function attachmentImageUrl(attachment) {
  const raw = attachment?.previewUrl || "";
  if (!raw) {
    return "";
  }
  const url = new URL(raw, location.origin);
  if (state.mode === "cloud" && state.cloud.selectedDeviceId) {
    url.searchParams.set("deviceId", state.cloud.selectedDeviceId);
  }
  if (state.accessToken) {
    url.searchParams.set("access_token", state.accessToken);
  }
  return url.toString();
}

function renderMessageAttachments(attachments = []) {
  const items = (attachments || []).filter(Boolean);
  if (!items.length) {
    return "";
  }
  return `
    <div class="message-attachments">
      ${items
        .map((attachment) => {
          const src = attachment.localPreviewUrl || attachmentImageUrl(attachment);
          const label = attachment.fileName || "image";
          return `
            <span class="message-attachment" role="button" tabindex="0" data-attachment-preview="${escapeHtml(src)}" aria-label="${escapeHtml(label)}">
              ${src ? `<img src="${escapeHtml(src)}" alt="${escapeHtml(label)}">` : ""}
              <span>${escapeHtml(label)}</span>
            </span>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderAttachmentStrip() {
  if (!dom.attachmentStrip) {
    return;
  }
  const items = state.pendingAttachments || [];
  dom.attachmentStrip.classList.toggle("has-items", items.length > 0);
  dom.attachmentStrip.innerHTML = items
    .map((item) => `
      <div class="attachment-chip" data-local-id="${escapeHtml(item.localId)}">
        <img src="${escapeHtml(item.previewUrl)}" alt="${escapeHtml(item.file?.name || "image")}">
        <button type="button" data-remove-attachment="${escapeHtml(item.localId)}" aria-label="remove">x</button>
        <span class="attachment-status">${escapeHtml(item.status === "uploading" ? "uploading" : item.error || item.file?.name || "image")}</span>
      </div>
    `)
    .join("");
}

function clearPendingAttachments() {
  for (const item of state.pendingAttachments || []) {
    if (item.previewUrl) {
      URL.revokeObjectURL(item.previewUrl);
    }
  }
  state.pendingAttachments = [];
  renderAttachmentStrip();
  window.requestAnimationFrame(updateFloatingLayout);
}

async function loadImageFromFile(file) {
  const url = URL.createObjectURL(file);
  try {
    const image = await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = url;
    });
    return image;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function canvasToBlob(canvas, type = "image/jpeg", quality = 0.86) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error("image encode failed"));
      }
    }, type, quality);
  });
}

async function prepareImageFile(file) {
  const supported = ["image/jpeg", "image/png", "image/webp"];
  if (!supported.includes(file.type)) {
    throw new Error("仅支持 JPEG、PNG、WebP 图片。");
  }
  const image = await loadImageFromFile(file);
  const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(image.naturalWidth || image.width, image.naturalHeight || image.height));
  if (scale >= 1 && file.size <= MAX_IMAGE_BYTES) {
    return file;
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round((image.naturalWidth || image.width) * scale));
  canvas.height = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
  const context = canvas.getContext("2d");
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const blob = await canvasToBlob(canvas);
  const name = `${(file.name || "image").replace(/\.[^.]+$/, "") || "image"}.jpg`;
  const resized = new File([blob], name, { type: "image/jpeg" });
  if (resized.size > MAX_IMAGE_BYTES) {
    throw new Error("图片压缩后仍超过 5MB。");
  }
  return resized;
}

async function addImageFiles(files) {
  const selected = Array.from(files || []);
  if (!selected.length) {
    return;
  }
  for (const file of selected) {
    if (state.pendingAttachments.length >= MAX_IMAGE_ATTACHMENTS) {
      optimisticFailEvent("单条消息最多支持 4 张图片。");
      break;
    }
    try {
      const prepared = await prepareImageFile(file);
      state.pendingAttachments.push({
        localId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        file: prepared,
        previewUrl: URL.createObjectURL(prepared),
        status: "ready",
        error: "",
      });
    } catch (error) {
      optimisticFailEvent(error.message || "图片处理失败");
    }
  }
  renderAttachmentStrip();
  renderMainView();
}

function removePendingAttachment(localId) {
  const item = state.pendingAttachments.find((entry) => entry.localId === localId);
  if (item?.previewUrl) {
    URL.revokeObjectURL(item.previewUrl);
  }
  state.pendingAttachments = state.pendingAttachments.filter((entry) => entry.localId !== localId);
  renderAttachmentStrip();
  updateFloatingLayout();
}

async function uploadPendingAttachments() {
  const ids = [];
  for (const item of state.pendingAttachments) {
    if (item.attachmentId) {
      ids.push(item.attachmentId);
      continue;
    }
    item.status = "uploading";
    item.error = "";
    renderAttachmentStrip();
    const uploaded = await client.uploadAttachment(item.file);
    item.attachmentId = uploaded.attachmentId;
    item.status = "uploaded";
    ids.push(uploaded.attachmentId);
  }
  return ids;
}

function setBodyState() {
  document.body.classList.toggle("paired", Boolean(state.accessToken));
  document.body.classList.toggle("library-open", Boolean(state.accessToken) && (!isDesktop() && dom.libraryPanel.dataset.open === "true"));
  document.body.classList.toggle("compose-open", dom.composePanel.dataset.open === "true");
  document.body.classList.toggle("settings-open", dom.settingsPanel.dataset.open === "true");
  document.body.classList.toggle("actions-open", dom.viewActionsPanel.dataset.open === "true");
  document.body.classList.toggle("reader-open", dom.readerPanel?.dataset.open === "true");
  document.body.classList.toggle("desktop-approval-open", dom.desktopApprovalPanel?.dataset.open === "true");
}

async function readJson(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  return JSON.parse(text);
}

class DirectClient {
  async request(path, { method = "GET", body, auth = true } = {}) {
    const headers = {};
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (auth && state.accessToken) {
      headers.Authorization = `Bearer ${state.accessToken}`;
    }
    const response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const payload = await readJson(response).catch(() => ({}));
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    return readJson(response);
  }

  health() {
    return this.request("/api/health", { auth: false });
  }

  pair(code) {
    return this.request("/api/auth/pair", {
      method: "POST",
      body: { code },
      auth: false,
    });
  }

  listWorkspaces() {
    return this.request("/api/workspaces");
  }

  listSessions() {
    return this.request("/api/sessions");
  }

  getSession(sessionId) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}`);
  }

  getActiveSession() {
    return this.request("/api/ui/active-session");
  }

  setActiveSession(sessionId, source = "ui") {
    return this.request("/api/ui/active-session", {
      method: "POST",
      body: { sessionId: sessionId || null, source },
    });
  }

  async uploadAttachment(file) {
    const headers = {};
    if (state.accessToken) {
      headers.Authorization = `Bearer ${state.accessToken}`;
    }
    const form = new FormData();
    form.append("file", file, file.name || "image.jpg");
    const response = await fetch("/api/attachments", {
      method: "POST",
      headers,
      body: form,
    });
    if (!response.ok) {
      const payload = await readJson(response).catch(() => ({}));
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    return readJson(response);
  }

  createSession(workspace, prompt, title, interactionMode = "default", attachmentIds = []) {
    return this.request("/api/sessions", {
      method: "POST",
      body: { workspace, prompt, title: title || null, interactionMode, attachmentIds },
    });
  }

  continueSession(sessionId, content, interactionMode = "default", attachmentIds = []) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: { content, interactionMode, attachmentIds },
    });
  }

  alignSession(sessionId) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}/desktop-align`, {
      method: "POST",
    });
  }

  cancelSession(sessionId) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}/cancel`, {
      method: "POST",
    });
  }

  listThreads() {
    return this.request("/api/threads");
  }

  getThread(threadId) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}`);
  }

  resumeThread(threadId, prompt, interactionMode = "default", attachmentIds = []) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/resume`, {
      method: "POST",
      body: { prompt: prompt || null, interactionMode, attachmentIds },
    });
  }

  listApprovals(sessionId) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}/approvals`);
  }

  resolveApproval(sessionId, approvalId, payload) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}/approvals/${encodeURIComponent(approvalId)}/resolve`, {
      method: "POST",
      body: payload,
    });
  }

  subscribeSession(sessionId, onEvent) {
    const url = new URL(`/api/sessions/${encodeURIComponent(sessionId)}/events`, location.origin);
    url.searchParams.set("access_token", state.accessToken);
    const source = new EventSource(url);
    source.onmessage = (event) => {
      if (!event.data) {
        return;
      }
      onEvent(JSON.parse(event.data));
    };
    source.onerror = () => {};
    return () => source.close();
  }

  subscribeUi(onEvent) {
    const url = new URL("/api/ui/events", location.origin);
    url.searchParams.set("access_token", state.accessToken);
    const source = new EventSource(url);
    source.onmessage = (event) => {
      if (!event.data) {
        return;
      }
      onEvent(JSON.parse(event.data));
    };
    source.onerror = () => {};
    return () => source.close();
  }

  createDesktopSocket() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const url = new URL(`${protocol}://${location.host}/api/desktop/ws`);
    url.searchParams.set("access_token", state.accessToken);
    return new WebSocket(url.toString());
  }
}

class RelayClient {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.socket = null;
    this.closed = false;
    this.pending = new Map();
    this.connectPromise = null;
    this.sessionSubscription = null;
    this.uiSubscription = null;
    this.reconnectTimer = null;
  }

  async connect() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      return;
    }
    if (this.connectPromise) {
      return this.connectPromise;
    }
    this.connectPromise = new Promise((resolve, reject) => {
      let opened = false;
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${protocol}://${location.host}/ws/mobile/${encodeURIComponent(this.sessionId)}`);
      this.socket = socket;

      socket.addEventListener("open", () => {
        opened = true;
        state.routeStatus = "relay.connected";
        renderStatus();
        resolve();
      });
      socket.addEventListener("message", (event) => {
        this.handleMessage(JSON.parse(event.data));
      });
      socket.addEventListener("close", () => {
        this.socket = null;
        this.connectPromise = null;
        this.failPending("relay disconnected");
        state.routeStatus = "relay.disconnected";
        renderStatus();
        if (!opened) {
          reject(new Error("relay unavailable"));
          return;
        }
        if (!this.closed) {
          this.reconnectTimer = window.setTimeout(() => {
            this.connect().then(() => this.resubscribe()).catch(() => {});
          }, 1200);
        }
      });
      socket.addEventListener("error", () => {
        state.routeStatus = "relay.error";
        renderStatus();
        if (!opened) {
          reject(new Error("relay connection failed"));
        }
      });
    });
    return this.connectPromise;
  }

  failPending(message) {
    for (const { reject, timer } of this.pending.values()) {
      window.clearTimeout(timer);
      reject(new Error(message));
    }
    this.pending.clear();
  }

  async close() {
    this.closed = true;
    window.clearTimeout(this.reconnectTimer);
    if (this.socket) {
      this.socket.close();
    }
  }

  async sendWithAck(payload) {
    await this.connect();
    if (state.routeStatus === "bridge_offline") {
      throw new Error("bridge offline");
    }
    const id = payload.id || crypto.randomUUID();
    const message = { ...payload, id };
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("relay timeout"));
      }, 12000);
      this.pending.set(id, { resolve, reject, timer });
      this.socket.send(JSON.stringify(message));
    });
  }

  async request(action, payload = {}, { auth = true } = {}) {
    const response = await this.sendWithAck({
      type: "rpc.request",
      action,
      payload,
      accessToken: auth ? state.accessToken : undefined,
    });
    return response.result;
  }

  async resubscribe() {
    if (!state.accessToken) {
      return;
    }
    if (this.uiSubscription) {
      const { onEvent } = this.uiSubscription;
      this.uiSubscription = null;
      await this.subscribeUi(onEvent);
    }
    if (this.sessionSubscription) {
      const { sessionId, onEvent } = this.sessionSubscription;
      this.sessionSubscription = null;
      await this.subscribeSession(sessionId, onEvent);
    }
  }

  handleMessage(message) {
    const type = String(message.type || "");
    if (type === "rpc.response") {
      const pending = this.pending.get(message.id);
      if (!pending) {
        return;
      }
      this.pending.delete(message.id);
      window.clearTimeout(pending.timer);
      if (message.ok) {
        pending.resolve(message);
        return;
      }
      pending.reject(new Error(message.error?.message || "relay request failed"));
      return;
    }
    if (type === "session.event") {
      if (this.sessionSubscription && message.sessionId === this.sessionSubscription.sessionId) {
        this.sessionSubscription.onEvent(message.event);
      }
      return;
    }
    if (type === "ui.event") {
      this.uiSubscription?.onEvent(message.event);
      return;
    }
    if (type === "relay.status") {
      state.routeStatus = String(message.status || "relay");
      renderStatus();
      return;
    }
    if (type === "relay.error") {
      state.routeStatus = String(message.message || "relay.error");
      renderStatus();
    }
  }

  health() {
    return this.request("health", {}, { auth: false });
  }

  pair(code) {
    return this.request("pair_device", { code }, { auth: false });
  }

  listWorkspaces() {
    return this.request("list_workspaces");
  }

  listSessions() {
    return this.request("list_sessions");
  }

  getSession(sessionId) {
    return this.request("get_session", { sessionId });
  }

  getActiveSession() {
    return this.request("get_active_session");
  }

  setActiveSession(sessionId, source = "relay_ui") {
    return this.request("set_active_session", { sessionId: sessionId || null, source });
  }

  uploadAttachment() {
    throw new Error("当前 relay 模式暂不支持图片上传。");
  }

  createSession(workspace, prompt, title, interactionMode = "default", attachmentIds = []) {
    return this.request("create_session", { workspace, prompt, title: title || null, interactionMode, attachmentIds });
  }

  continueSession(sessionId, content, interactionMode = "default", attachmentIds = []) {
    return this.request("continue_session", { sessionId, content, interactionMode, attachmentIds });
  }

  alignSession(sessionId) {
    return this.request("align_desktop_session", { sessionId });
  }

  cancelSession(sessionId) {
    return this.request("cancel_session", { sessionId });
  }

  listThreads() {
    return this.request("list_threads");
  }

  getThread(threadId) {
    return this.request("get_thread", { threadId });
  }

  resumeThread(threadId, prompt, interactionMode = "default", attachmentIds = []) {
    return this.request("resume_thread", { threadId, prompt: prompt || null, interactionMode, attachmentIds });
  }

  listApprovals(sessionId) {
    return this.request("list_approvals", { sessionId });
  }

  resolveApproval(sessionId, approvalId, payload) {
    return this.request("resolve_approval", {
      sessionId,
      approvalId,
      action: payload.action,
      actionValue: payload.action,
      answers: payload.answers,
      content: payload.content,
    });
  }

  async subscribeSession(sessionId, onEvent) {
    if (this.sessionSubscription?.sessionId === sessionId) {
      this.sessionSubscription.onEvent = onEvent;
      return async () => this.unsubscribeSession(sessionId);
    }
    await this.unsubscribeSession();
    await this.sendWithAck({
      type: "rpc.subscribe",
      sessionId,
      accessToken: state.accessToken,
    });
    this.sessionSubscription = { sessionId, onEvent };
    return async () => this.unsubscribeSession(sessionId);
  }

  async unsubscribeSession(sessionId = null) {
    if (!this.sessionSubscription) {
      return;
    }
    const current = this.sessionSubscription.sessionId;
    if (sessionId && current !== sessionId) {
      return;
    }
    this.sessionSubscription = null;
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: "rpc.unsubscribe", sessionId: current }));
    }
  }

  async subscribeUi(onEvent) {
    if (this.uiSubscription) {
      this.uiSubscription.onEvent = onEvent;
      return async () => this.unsubscribeUi();
    }
    await this.sendWithAck({
      type: "rpc.subscribe_ui",
      accessToken: state.accessToken,
    });
    this.uiSubscription = { onEvent };
    return async () => this.unsubscribeUi();
  }

  async unsubscribeUi() {
    if (!this.uiSubscription) {
      return;
    }
    this.uiSubscription = null;
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: "rpc.unsubscribe_ui" }));
    }
  }

  createDesktopSocket() {
    return null;
  }
}

const client = state.mode === "relay" ? new RelayClient(state.relaySessionId) : new DirectClient();

function sortByUpdated(items, key = "updatedAt") {
  return [...items].sort((left, right) => {
    const a = new Date(left[key] || left.createdAt || 0).getTime();
    const b = new Date(right[key] || right.createdAt || 0).getTime();
    return b - a;
  });
}

function threadStatus(thread) {
  return String(thread?.status || "").trim().toLowerCase();
}

function sessionThreadId(session) {
  return session?.sourceThreadId || session?.backendSessionId || null;
}

function findSession(sessionId) {
  return state.sessions.find((item) => item.sessionId === sessionId) || null;
}

function findSessionForThread(threadId) {
  return state.sessions.find((item) => sessionThreadId(item) === threadId) || null;
}

function sessionNeedsDesktopAlignment(session, interactionMode = "default") {
  if (!session || interactionMode === "plan") {
    return false;
  }
  if (state.mode === "cloud") {
    return true;
  }
  return session.deliveryRoute === "desktop_gui" || Boolean(session.desktopAutomationReady);
}

function sessionIsDesktopAligned(session, interactionMode = "default") {
  if (!sessionNeedsDesktopAlignment(session, interactionMode)) {
    return true;
  }
  if (!sessionThreadId(session)) {
    return true;
  }
  return session.desktopTargetState === "aligned";
}

function setPanel(panel, open) {
  if (!panel) {
    return;
  }
  panel.dataset.open = open ? "true" : "false";
  setBodyState();
}

function actionDetailRow(label, value, { multiline = false } = {}) {
  if (!value) {
    return "";
  }
  const classes = multiline ? "action-detail-row multiline" : "action-detail-row";
  const content = multiline ? renderRichText(value) : escapeHtml(value);
  return `
    <div class="${classes}">
      <div class="action-detail-label">${escapeHtml(label)}</div>
      <div class="action-detail-value">${content}</div>
    </div>
  `;
}

function currentViewActionsModel() {
  if (state.currentSession) {
    const session = state.currentSession;
    const canCancel = session.status === "running" || session.status === "waiting";
    const syncValue = [
      sessionSyncLabel(session),
      session.lastThreadSyncAt ? formatTime(session.lastThreadSyncAt) : "",
    ]
      .filter(Boolean)
      .join(" · ");
    return {
      title: shortText(session.title || t("untitled"), 72),
      details: [
        actionDetailRow(t("workspace"), session.workspace),
        actionDetailRow(
          t("statusTitle"),
          [statusLabel(session.status), session.isActive ? t("active") : ""].filter(Boolean).join(" · "),
        ),
        actionDetailRow(t("sourceLabel"), sessionKindLabel(session.sessionKind)),
        actionDetailRow(t("sync"), syncValue),
        actionDetailRow(t("failed"), session.lastError),
      ]
        .filter(Boolean)
        .join(""),
      primaryAction: "cancel-session",
      primaryLabel: t("cancelSession"),
      primaryKind: "danger",
      primaryDisabled: !canCancel,
    };
  }
  if (state.currentThread) {
    const thread = state.currentThread;
    const linked = findSessionForThread(thread.threadId);
    return {
      title: shortText(thread.title || thread.preview || t("untitled"), 72),
      details: [
        actionDetailRow(t("workspace"), thread.workspace),
        actionDetailRow(
          t("statusTitle"),
          [
            statusLabel(thread.status),
            linked ? (linked.isActive ? t("active") : t("adopted")) : "",
          ]
            .filter(Boolean)
            .join(" · "),
        ),
        actionDetailRow(t("updatedLabel"), thread.updatedAt ? formatTime(thread.updatedAt) : ""),
        actionDetailRow(t("preview"), shortText(thread.preview || "", 220), { multiline: true }),
        actionDetailRow(t("path"), shortText(thread.path || "", 220), { multiline: true }),
      ]
        .filter(Boolean)
        .join(""),
      primaryAction: "resume-thread",
      primaryLabel: state.aligningThread ? t("desktopAligning") : t("continueThread"),
      primaryKind: "",
      primaryDisabled: state.aligningThread,
    };
  }
  return null;
}

function renderViewActionsPanel() {
  const model = currentViewActionsModel();
  dom.viewActionsMark.textContent = t("actions");
  dom.closeViewActions.title = t("close");
  dom.closeViewActions.setAttribute("aria-label", t("close"));
  if (!model) {
    dom.viewActionsTitle.textContent = t("emptyView");
    dom.viewActionsDetails.innerHTML = "";
    dom.viewActionsPrimary.classList.add("hidden");
    return;
  }
  dom.viewActionsTitle.textContent = model.title;
  dom.viewActionsDetails.innerHTML = model.details || `<div class="nav-meta">${escapeHtml(t("details"))}</div>`;
  dom.viewActionsPrimary.classList.toggle("hidden", !model.primaryAction);
  dom.viewActionsPrimary.dataset.action = model.primaryAction || "";
  dom.viewActionsPrimary.dataset.kind = model.primaryKind || "";
  dom.viewActionsPrimary.disabled = Boolean(model.primaryDisabled);
  dom.viewActionsPrimary.textContent = model.primaryLabel || "";
}

function openCurrentViewActions() {
  if (!state.currentSession && !state.currentThread) {
    return;
  }
  setPanel(dom.readerPanel, false);
  renderViewActionsPanel();
  setPanel(dom.libraryPanel, false);
  setPanel(dom.composePanel, false);
  setPanel(dom.settingsPanel, false);
  setPanel(dom.viewActionsPanel, true);
}

function renderStatus() {
  const backendLine = state.backendAvailable
    ? `${state.backendName || "backend"} ready`
    : `${state.backendName || "backend"} unavailable`;
  const focusSession = state.currentSession || findSession(state.activeSession.activeSessionId);
  const desktopLine = sessionSyncLabel(focusSession);
  dom.backendStatus.textContent = backendLine;
  dom.relayStatus.textContent = state.mode === "relay" ? `relay ${state.routeStatus}` : "lan direct";
  dom.pairStatus.textContent = state.accessToken ? "paired" : "not paired";

  const liveCount = state.sessions.filter((item) => ACTIVE_THREAD_STATUSES.has(String(item.status || "").toLowerCase()) || item.isActive).length;
  const title = state.currentSession?.title || findSession(state.activeSession.activeSessionId)?.title || "codex remote";
  dom.topbarStatus.textContent = `${title} · ${liveCount}`;
  dom.followActive.textContent = state.autoFollow ? "A" : "M";
  dom.followActive.title = state.autoFollow ? "Auto follow current session" : "Manual browse";
  dom.settingsBackend.textContent = `backend ${backendLine}`;
  dom.settingsRoute.textContent = `route ${state.mode === "relay" ? state.routeStatus : "lan direct"}${desktopLine ? ` · ${desktopLine}` : ""}`;
  dom.settingsSync.textContent = `sync ${state.syncStatus}${focusSession?.lastThreadSyncAt ? ` · ${formatTime(focusSession.lastThreadSyncAt)}` : ""}`;
}

function sessionMeta(session) {
  const parts = [
    statusLabel(session.status),
    sessionKindLabel(session.sessionKind),
  ];
  if (session.isActive) {
    parts.unshift("active");
  }
  if (session.resultSummary) {
    parts.push(shortText(session.resultSummary, 42));
  }
  if (sessionSyncLabel(session)) {
    parts.push(sessionSyncLabel(session));
  }
  return parts.filter(Boolean).join(" · ");
}

function threadMeta(thread, linkedSession) {
  const parts = [statusLabel(thread.status)];
  if (linkedSession) {
    parts.push(linkedSession.isActive ? "active" : "adopted");
  }
  if (thread.workspace) {
    parts.push(thread.workspace);
  }
  return parts.filter(Boolean).join(" · ");
}

function bucketThreads() {
  const liveSessions = sortByUpdated(
    state.sessions.filter((item) => item.isActive || ACTIVE_THREAD_STATUSES.has(String(item.status || "").toLowerCase()) || item.sessionKind === "auto_adopted"),
  );
  const pinnedThreadIds = new Set(liveSessions.map((item) => sessionThreadId(item)).filter(Boolean));
  const remaining = sortByUpdated(state.threads).filter((item) => !pinnedThreadIds.has(item.threadId));
  const recent = remaining.slice(0, 8);
  const historyItems = remaining.slice(8);
  const history = { Today: [], "This Week": [], Older: [] };
  for (const item of historyItems) {
    history[dayBucket(item.updatedAt || item.createdAt)].push(item);
  }
  return { liveSessions, recent, history };
}

function renderLibrary() {
  const { liveSessions, recent, history } = bucketThreads();

  dom.liveList.innerHTML = liveSessions.length
    ? liveSessions
        .map(
          (item) => `
            <button class="nav-item ${item.sessionId === state.currentSessionId ? "active" : ""}" type="button" data-kind="session" data-session-id="${escapeHtml(item.sessionId)}">
              <div class="nav-title">${escapeHtml(shortText(item.title || "Untitled", 42))}</div>
              <div class="nav-meta">${escapeHtml(sessionMeta(item))}</div>
            </button>
          `,
        )
        .join("")
    : `<div class="nav-meta">No live sessions</div>`;

  dom.recentList.innerHTML = recent.length
    ? recent
        .map((item) => {
          const linked = findSessionForThread(item.threadId);
          return `
            <button class="nav-item ${item.threadId === state.currentThreadId ? "active" : ""}" type="button" data-kind="thread" data-thread-id="${escapeHtml(item.threadId)}">
              <div class="nav-title">${escapeHtml(shortText(item.title || item.preview || "Untitled", 42))}</div>
              <div class="nav-meta">${escapeHtml(threadMeta(item, linked))}</div>
            </button>
          `;
        })
        .join("")
    : `<div class="nav-meta">No recent threads</div>`;

  dom.historyList.innerHTML = Object.entries(history)
    .filter(([, items]) => items.length)
    .map(
      ([label, items]) => `
        <div class="history-group">
          <div class="history-label">${escapeHtml(label)}</div>
          <div class="nav-list">
            ${items
              .map((item) => {
                const linked = findSessionForThread(item.threadId);
                return `
                  <button class="nav-item ${item.threadId === state.currentThreadId ? "active" : ""}" type="button" data-kind="thread" data-thread-id="${escapeHtml(item.threadId)}">
                    <div class="nav-title">${escapeHtml(shortText(item.title || item.preview || "Untitled", 42))}</div>
                    <div class="nav-meta">${escapeHtml(threadMeta(item, linked))}</div>
                  </button>
                `;
              })
              .join("")}
          </div>
        </div>
      `,
    )
    .join("");
  dom.historyFold.open = false;
}

function makeBubble(role, label, content, extraClass = "") {
  return `
    <article class="bubble ${escapeHtml(role)} ${escapeHtml(extraClass)}">
      <div class="bubble-label">${escapeHtml(label)}</div>
      <div>${escapeHtml(content || "")}</div>
    </article>
  `;
}

function summarizeEvent(event) {
  const type = String(event?.type || "");
  if (type === "tool.completed") {
    return { title: event.name || "tool", body: shortText(event.summary || "completed", 96) };
  }
  if (type === "tool.started") {
    return { title: event.name || "tool", body: "running" };
  }
  if (type === "turn.plan.updated") {
    const steps = Array.isArray(event.plan) ? event.plan.map((item) => item.step).filter(Boolean).join(" · ") : "plan updated";
    return { title: "plan", body: shortText(steps || "plan updated", 96) };
  }
  if (type === "turn.diff.updated") {
    const files = Array.isArray(event.diff?.files) ? event.diff.files.join(" · ") : "diff updated";
    return { title: "diff", body: shortText(files, 96) };
  }
  if (type === "session.completed") {
    return { title: "done", body: shortText(event.summary || "session completed", 96) };
  }
  if (type === "session.failed") {
    return { title: "failed", body: shortText(event.message || "session failed", 96) };
  }
  if (type === "session.waiting" || type === "approval.required") {
    return { title: "approval", body: shortText(event.message || event.approval?.summary || "requires approval", 96) };
  }
  if (type === "ui.followup.sent") {
    return { title: "queued", body: shortText(event.content || "message sent", 96) };
  }
  if (type === "ui.followup.failed") {
    return { title: "send failed", body: shortText(event.message || "failed", 96) };
  }
  if (type === "thread.mirrored") {
    return { title: "synced", body: shortText(statusLabel(event.status || "completed"), 96) };
  }
  return null;
}

function renderActivityStrip() {
  const cards = state.sessionEvents
    .map(summarizeEvent)
    .filter(Boolean)
    .slice(-5)
    .reverse();
  dom.activityStrip.innerHTML = cards
    .map(
      (item) => `
        <div class="activity-card">
          <div>${escapeHtml(item.title)}</div>
          <div class="nav-meta">${escapeHtml(item.body)}</div>
        </div>
      `,
    )
    .join("");
}

function renderApprovals() {
  if (!state.currentSessionId) {
    dom.approvalStrip.innerHTML = "";
    return;
  }
  const active = state.approvals.filter((item) => item.status === "pending");
  dom.approvalStrip.innerHTML = active
    .map((item) => {
      const buttons = (item.availableActions || [])
        .map((action) => {
          const danger = action === "reject" || action === "cancel" ? ` data-kind="danger"` : "";
          return `<button type="button"${danger} data-approval-id="${escapeHtml(item.approvalId)}" data-action="${escapeHtml(action)}">${escapeHtml(action)}</button>`;
        })
        .join("");
      return `
        <div class="approval-item">
          <div>${escapeHtml(item.title || "approval")}</div>
          <div class="approval-copy">${escapeHtml(shortText(item.summary || "", 160))}</div>
          <div class="approval-actions">${buttons}</div>
        </div>
      `;
    })
    .join("");
}

function renderSessionConversation() {
  const session = state.currentSession;
  if (!session) {
    dom.conversationLog.innerHTML = "";
    return;
  }
  const bubbles = [];
  for (const message of session.messages || []) {
    const role = message.role === "user" ? "user" : "assistant";
    bubbles.push(makeBubble(role, role, message.content, message.pending ? "draft" : ""));
  }
  if (state.assistantDraft) {
    bubbles.push(makeBubble("assistant", "draft", state.assistantDraft, "draft"));
  }
  dom.conversationLog.innerHTML = bubbles.join("");
}

function renderSessionContext() {
  const session = state.currentSession;
  if (!session) {
    dom.sessionContext.innerHTML = "";
    dom.cancelSession.disabled = true;
    return;
  }
  const chips = [
    session.workspace,
    statusLabel(session.status),
    sessionKindLabel(session.sessionKind),
    sessionSyncLabel(session),
    session.isActive ? "active" : "",
    session.lastThreadSyncAt ? `sync ${formatTime(session.lastThreadSyncAt)}` : "",
    session.updatedAt ? formatTime(session.updatedAt) : "",
  ]
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");
  dom.sessionContext.innerHTML = `
    <div class="context-title">${escapeHtml(shortText(session.title || "Untitled", 72))}</div>
    <div class="context-subline">${chips}</div>
  `;
  dom.cancelSession.disabled = !(session.status === "running" || session.status === "waiting");
}

function renderSessionDebug() {
  dom.debugLog.innerHTML = state.sessionEvents.length
    ? state.sessionEvents
        .slice(-24)
        .reverse()
        .map(
          (item) => `
            <div class="debug-item">
              <div>${escapeHtml(item.type || "event")}</div>
              <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
            </div>
          `,
        )
        .join("")
    : `<div class="nav-meta">No debug events</div>`;
}

function normalizeThreadTurns(thread) {
  const turns = [];
  for (const turn of thread.turns || []) {
    const blocks = [];
    const tools = [];
    for (const item of turn.items || []) {
      if (item.type === "userMessage") {
        const text = Array.isArray(item.content)
          ? item.content
              .map((part) => (typeof part?.text === "string" ? part.text : ""))
              .filter(Boolean)
              .join("\n")
          : "";
        if (text) {
          blocks.push({ role: "user", label: "user", content: text });
        }
        continue;
      }
      if (item.type === "agentMessage") {
        const role = item.phase === "commentary" ? "commentary" : "assistant";
        const label = item.phase === "commentary" ? "commentary" : "assistant";
        if (item.text) {
          blocks.push({ role, label, content: item.text });
        }
        continue;
      }
      const summary = shortText(item.summary || item.title || item.command || item.type || "item", 80);
      if (summary) {
        tools.push(summary);
      }
    }
    turns.push({
      turnId: turn.turnId,
      status: turn.status,
      error: turn.error,
      blocks,
      tools,
    });
  }
  return turns;
}

function renderThreadContext() {
  const thread = state.currentThread;
  if (!thread) {
    dom.threadContext.innerHTML = "";
    return;
  }
  const linked = findSessionForThread(thread.threadId);
  const chips = [
    thread.workspace,
    statusLabel(thread.status),
    linked ? "adopted" : "",
    thread.updatedAt ? formatTime(thread.updatedAt) : "",
  ]
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");
  dom.threadContext.innerHTML = `
    <div class="context-title">${escapeHtml(shortText(thread.title || thread.preview || "Untitled", 72))}</div>
    <div class="context-subline">${chips}</div>
  `;
  dom.resumeThread.textContent = linked ? "open" : "adopt";
}

function renderThreadSummary() {
  const thread = state.currentThread;
  if (!thread) {
    dom.threadSummary.innerHTML = "";
    return;
  }
  const cards = [
    thread.preview ? { title: "preview", body: thread.preview } : null,
    thread.path ? { title: "path", body: thread.path } : null,
  ]
    .filter(Boolean)
    .map(
      (item) => `
        <div class="activity-card">
          <div>${escapeHtml(item.title)}</div>
          <div class="nav-meta">${escapeHtml(shortText(item.body, 160))}</div>
        </div>
      `,
    )
    .join("");
  dom.threadSummary.innerHTML = cards;
}

function renderThreadConversation() {
  const thread = state.currentThread;
  if (!thread) {
    dom.threadLog.innerHTML = "";
    return;
  }
  const turns = normalizeThreadTurns(thread);
  dom.threadLog.innerHTML = turns
    .map((turn) => {
      const blocks = turn.blocks.map((item) => makeBubble(item.role, item.label, item.content)).join("");
      const tools = turn.tools.length
        ? `<div class="tool-row">${turn.tools.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>`
        : "";
      const status = turn.status ? `<div class="bubble-label">${escapeHtml(statusLabel(turn.status))}</div>` : "";
      const error = turn.error ? `<div class="nav-meta">${escapeHtml(turn.error)}</div>` : "";
      return `<section class="turn">${status}${blocks}${tools}${error}</section>`;
    })
    .join("");
}

function renderThreadDebug() {
  const turns = state.currentThread?.turns || [];
  dom.threadDebug.innerHTML = turns.length
    ? turns
        .slice()
        .reverse()
        .map(
          (item) => `
            <div class="debug-item">
              <div>${escapeHtml(item.turnId || "turn")}</div>
              <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
            </div>
          `,
        )
        .join("")
    : `<div class="nav-meta">No turn data</div>`;
}

function renderMainView() {
  const hasSession = Boolean(state.currentSession);
  const hasThread = Boolean(state.currentThread);
  dom.emptyView.classList.toggle("hidden", hasSession || hasThread);
  dom.sessionView.classList.toggle("hidden", !hasSession);
  dom.threadView.classList.toggle("hidden", !hasThread);
  if (hasSession) {
    renderSessionContext();
    renderApprovals();
    renderAttachmentStrip();
    renderActivityStrip();
    renderSessionConversation();
    renderSessionDebug();
    renderDesktopApprovalPanel();
  }
  if (hasThread) {
    renderThreadContext();
    renderThreadSummary();
    renderThreadConversation();
    renderThreadDebug();
    if (dom.desktopApprovalPanel.dataset.open === "true") {
      setPanel(dom.desktopApprovalPanel, false);
    }
  }
  if (!hasSession && !hasThread && dom.desktopApprovalPanel.dataset.open === "true") {
    setPanel(dom.desktopApprovalPanel, false);
  }
  renderStatus();
  renderLibrary();
}

function routeLabel() {
  if (state.mode !== "relay") {
    return t("lanDirect");
  }
  const route = String(state.routeStatus || "");
  if (route.includes("connected")) {
    return `${t("relay")} · ${t("routeConnected")}`;
  }
  if (route.includes("disconnected")) {
    return `${t("relay")} · ${t("routeDisconnected")}`;
  }
  if (route.includes("error")) {
    return `${t("relay")} · ${t("routeError")}`;
  }
  if (route === "bridge_offline") {
    return t("bridgeOffline");
  }
  return t("relay");
}

function syncStatusLabel() {
  const labels = {
    idle: t("syncIdle"),
    live: t("syncLive"),
    partial: t("syncPartial"),
    syncing: t("syncSyncing"),
    creating: t("syncCreating"),
  };
  return labels[state.syncStatus] || state.syncStatus;
}

function applyUiChrome() {
  document.documentElement.lang = state.ui.lang;
  document.body.dataset.theme = state.ui.theme;
  document.title = t("codexRemote");

  dom.pairCode.placeholder = t("pairPlaceholder");
  dom.pairCode.setAttribute("aria-label", t("pairPlaceholder"));
  dom.pairButton.setAttribute("aria-label", t("connect"));
  dom.openLibrary.setAttribute("aria-label", t("openLibrary"));
  dom.openCompose.setAttribute("aria-label", t("newSession"));
  dom.openSettings.setAttribute("aria-label", t("settings"));
  dom.sendFollowup.setAttribute("aria-label", t("send"));
  dom.sendFollowup.title = t("send");
  dom.cancelSession.textContent = "⋯";
  dom.cancelSession.title = t("more");
  dom.cancelSession.setAttribute("aria-label", t("more"));
  dom.resumeThread.textContent = "⋯";
  dom.resumeThread.title = t("more");
  dom.resumeThread.setAttribute("aria-label", t("more"));
  dom.followupInput.placeholder = t("continuePlaceholder");
  dom.followupInput.setAttribute("aria-label", t("continuePlaceholder"));
  dom.titleInput.placeholder = t("titlePlaceholder");
  dom.titleInput.setAttribute("aria-label", t("titlePlaceholder"));
  dom.promptInput.placeholder = t("startPlaceholder");
  dom.promptInput.setAttribute("aria-label", t("startPlaceholder"));
  dom.workspaceSelect.setAttribute("aria-label", t("workspace"));
  dom.jumpLatest.textContent = "\u2193";
  dom.jumpLatest.setAttribute("aria-label", t("jumpLatest"));
  dom.jumpLatest.title = t("jumpLatest");
  dom.resumeThreadInline.textContent = t("continueThread");
  dom.langToggle.title = t("language");
  dom.themeToggle.title = t("theme");
  dom.langToggle.textContent = state.ui.lang === "zh-CN" ? t("en") : t("zh");
  dom.themeToggle.textContent = state.ui.theme === "dark" ? t("white") : t("black");
  dom.libraryMark.textContent = t("openLibrary");
  dom.liveMark.textContent = t("live");
  dom.recentMark.textContent = t("recent");
  dom.historySummary.textContent = t("history");
  dom.emptyCopy.textContent = t("emptyView");
  dom.sessionDebugSummary.textContent = t("debug");
  dom.threadDebugSummary.textContent = t("debug");
  dom.composeMark.textContent = t("newSession");
  dom.settingsMark.textContent = t("statusTitle");
  dom.desktopApprovalMark.textContent = t("desktopApprovalPanel");
  dom.desktopApprovalStatus.textContent = t("desktopPreviewWaiting");
  dom.desktopPreviewEmpty.textContent = t("desktopPreviewUnavailable");
  dom.closeDesktopApproval.setAttribute("aria-label", t("close"));
  dom.closeDesktopApproval.title = t("close");
  dom.createSession.textContent = t("start");
  dom.refreshAll.textContent = t("refresh");
  dom.libraryCompose.textContent = t("newSession");
  renderViewActionsPanel();
}

function renderStatus() {
  applyUiChrome();
  const backendName = state.backendName || t("backend");
  const backendState = state.backendAvailable ? t("ready") : t("unavailable");
  const backendLine = `${backendName} · ${backendState}`;
  const focusSession = state.currentSession || findSession(state.activeSession.activeSessionId);
  const wallTitle = `灵感墙 · ${state.wall.items.length}`;
  const title = state.currentView === "wall"
    ? wallTitle
    : shortText(
      state.currentSession?.title
        || state.currentThread?.title
        || state.currentThread?.preview
        || findSession(state.activeSession.activeSessionId)?.title
        || t("codexRemote"),
      48,
    );
  const liveCount = state.sessions.filter(
    (item) => ACTIVE_THREAD_STATUSES.has(String(item.status || "").toLowerCase()) || item.isActive,
  ).length;
  const syncLine = [
    syncStatusLabel(),
    focusSession?.lastThreadSyncAt ? t("syncAt").replace("{time}", formatTime(focusSession.lastThreadSyncAt)) : "",
    sessionSyncHint(focusSession),
  ]
    .filter(Boolean)
    .join(" · ");
  const routeLine = [routeLabel(), sessionSyncLabel(focusSession)].filter(Boolean).join(" · ");

  dom.backendStatus.textContent = backendLine;
  dom.relayStatus.textContent = routeLabel();
  dom.pairStatus.textContent = state.pairing ? t("pairing") : state.accessToken ? t("paired") : t("notPaired");
  dom.topbarStatus.textContent = state.currentView === "wall"
    ? title
    : (liveCount ? `${title} · ${t("liveCount").replace("{count}", liveCount)}` : title);
  dom.settingsBackend.textContent = `${t("backend")} · ${backendLine}`;
  dom.settingsRoute.textContent = `${t("route")} · ${routeLine}`;
  dom.settingsSync.textContent = `${t("sync")} · ${syncLine}`;
  dom.openWall.classList.toggle("active", state.currentView === "wall");
  dom.openWall.title = "打开灵感墙";
  if (dom.followActive) {
    dom.followActive.textContent = state.autoFollow ? "A" : "M";
    dom.followActive.title = state.autoFollow ? t("autoFollow") : t("manualFollow");
  }
}

function renderWallView() {
  const draft = wallDraftItem();
  const items = filteredWallItems();
  const favorites = state.wall.items.filter((item) => item.favorite).length;
  const tags = wallTagOptions();
  const palette = [
    ["amber", "#f4b183"],
    ["sky", "#7dc4ff"],
    ["mint", "#86d6b4"],
    ["rose", "#f29eb0"],
    ["ink", "#b4b8c7"],
  ];

  dom.wallView.innerHTML = `
    <div class="wall-shell">
      <section class="wall-hero">
        <div class="wall-kicker">Inspiration Wall</div>
        <h1 class="wall-title">把零散灵感钉成一面墙</h1>
        <div class="wall-copy">第一版使用浏览器本地存储，适合快速记录想法、标签、色彩和收藏项，先把流程跑通再考虑跨设备同步。</div>
        <div class="wall-stats">
          <div class="wall-stat"><span class="wall-stat-value">${state.wall.items.length}</span><span class="wall-stat-label">总卡片</span></div>
          <div class="wall-stat"><span class="wall-stat-value">${favorites}</span><span class="wall-stat-label">收藏</span></div>
          <div class="wall-stat"><span class="wall-stat-value">${tags.length}</span><span class="wall-stat-label">标签</span></div>
        </div>
      </section>

      <div class="wall-stage">
        <form class="wall-composer" data-wall-form="composer">
          <div class="wall-composer-head">
            <div>
              <div class="wall-kicker">${draft ? "Editing" : "Quick Capture"}</div>
              <div class="wall-toolbar-title">${draft ? "编辑卡片" : "新建一张卡片"}</div>
            </div>
            <button class="mini-button" type="button" data-wall-action="reset-composer">${draft ? "取消" : "清空"}</button>
          </div>

          <label class="wall-field">
            <span class="wall-label">标题</span>
            <input name="title" type="text" maxlength="80" placeholder="例如：沉浸式终端、移动控制台、桌面镜像交互" value="${escapeHtml(draft?.title || "")}">
          </label>

          <label class="wall-field">
            <span class="wall-label">灵感内容</span>
            <textarea name="content" placeholder="把脑海里的句子、界面想法、交互细节直接丢进来。">${escapeHtml(draft?.content || "")}</textarea>
          </label>

          <div class="wall-inline-fields">
            <label class="wall-field">
              <span class="wall-label">标签</span>
              <input name="tags" type="text" placeholder="产品, 视觉, 动效" value="${escapeHtml((draft?.tags || []).join(", "))}">
            </label>
            <label class="wall-field">
              <span class="wall-label">色彩</span>
              <select name="color">
                ${palette.map(([name, value]) => `<option value="${value}" ${(draft?.color || "#f4b183") === value ? "selected" : ""}>${name}</option>`).join("")}
              </select>
            </label>
          </div>

          <div class="wall-actions">
            <button class="sheet-action" type="submit">${draft ? "保存更新" : "保存卡片"}</button>
            <button class="sheet-action subtle" type="button" data-wall-action="seed-sample">生成示例</button>
          </div>
        </form>

        <div class="wall-board">
          <div class="wall-toolbar">
            <div class="wall-toolbar-copy">
              <div class="wall-toolbar-title">筛选与检索</div>
              <div class="wall-toolbar-note">按关键词、标签或收藏状态收束灵感。</div>
            </div>
          </div>

          <div class="wall-filters">
            <input name="wall-query" type="search" placeholder="搜索标题、内容、标签" value="${escapeHtml(state.wall.query)}">
            <select name="wall-filter-tag">
              <option value="all">全部标签</option>
              ${tags.map((tag) => `<option value="${escapeHtml(tag)}" ${state.wall.tag === tag ? "selected" : ""}>${escapeHtml(tag)}</option>`).join("")}
            </select>
            <label class="wall-toggle">
              <input name="wall-favorites" type="checkbox" ${state.wall.favoritesOnly ? "checked" : ""}>
              <span>只看收藏</span>
            </label>
          </div>

          <div class="wall-grid">
            ${items.length ? items.map((item) => `
              <article class="wall-card" style="--wall-accent:${escapeHtml(item.color || "#f4b183")}">
                <div class="wall-card-head">
                  <div class="wall-card-title">${escapeHtml(item.title || "未命名灵感")}</div>
                  <button class="mini-button" type="button" data-wall-action="toggle-favorite" data-wall-id="${escapeHtml(item.id)}">${item.favorite ? "starred" : "star"}</button>
                </div>
                <div class="wall-card-body">${escapeHtml(item.content || "")}</div>
                <div class="wall-tag-row">
                  ${(item.tags || []).map((tag) => `<button class="wall-tag ${state.wall.tag === tag ? "active" : ""}" type="button" data-wall-action="filter-tag" data-wall-tag="${escapeHtml(tag)}"># ${escapeHtml(tag)}</button>`).join("")}
                </div>
                <div class="wall-card-meta">
                  <span>${formatTime(item.updatedAt || item.createdAt)}</span>
                  <span>${(item.tags || []).length} tags</span>
                </div>
                <div class="wall-card-actions">
                  <button class="mini-button" type="button" data-wall-action="edit" data-wall-id="${escapeHtml(item.id)}">edit</button>
                  <button class="mini-button" type="button" data-wall-action="duplicate" data-wall-id="${escapeHtml(item.id)}">copy</button>
                  <button class="mini-button" type="button" data-wall-action="delete" data-wall-id="${escapeHtml(item.id)}">del</button>
                </div>
              </article>
            `).join("") : `
              <div class="wall-empty">
                <div class="wall-empty-copy">当前筛选下没有卡片。先记录一个想法，或者清掉筛选条件。</div>
              </div>
            `}
          </div>
        </div>
      </div>
    </div>
  `;
}

function sessionMeta(session) {
  const parts = [statusLabel(session.status), sessionKindLabel(session.sessionKind)];
  if (session.isActive) {
    parts.unshift(t("active"));
  }
  if (sessionSyncLabel(session)) {
    parts.push(sessionSyncLabel(session));
  }
  if (session.resultSummary) {
    parts.push(shortText(session.resultSummary, 42));
  }
  return parts.filter(Boolean).join(" · ");
}

function threadMeta(thread, linkedSession) {
  const parts = [statusLabel(thread.status)];
  if (linkedSession) {
    parts.push(linkedSession.isActive ? t("active") : t("adopted"));
  }
  if (thread.workspace) {
    parts.push(shortText(thread.workspace, 28));
  }
  return parts.filter(Boolean).join(" · ");
}

function bucketThreads() {
  const liveSessions = sortByUpdated(
    state.sessions.filter(
      (item) => item.isActive || ACTIVE_THREAD_STATUSES.has(String(item.status || "").toLowerCase()) || item.sessionKind === "auto_adopted",
    ),
  );
  const pinnedThreadIds = new Set(liveSessions.map((item) => sessionThreadId(item)).filter(Boolean));
  const sortedThreads = sortByUpdated(Array.isArray(state.threads) ? state.threads : []).filter((item) => item?.threadId);
  const filtered = sortedThreads.filter((item) => !pinnedThreadIds.has(item.threadId));
  const remaining = filtered.length || !sortedThreads.length ? filtered : sortedThreads;
  const recent = remaining.slice(0, 8);
  const historyItems = remaining.slice(8);
  const history = { today: [], thisWeek: [], older: [] };
  for (const item of historyItems) {
    history[dayBucket(item.updatedAt || item.createdAt)].push(item);
  }
  return { liveSessions, recent, history };
}

function renderLibraryPlaceholder(kind, message) {
  return `<div class="nav-meta" data-state="${escapeHtml(kind)}">${escapeHtml(message)}</div>`;
}

function renderSessionNavItem(session) {
  return `
    <button class="nav-item ${session.sessionId === state.currentSessionId ? "active" : ""}" type="button" data-session-id="${escapeHtml(session.sessionId)}">
      <div class="nav-title">${escapeHtml(shortText(session.title || t("untitled"), 42))}</div>
      <div class="nav-meta">${escapeHtml(sessionMeta(session))}</div>
    </button>
  `;
}

function renderThreadNavItem(thread) {
  const linked = findSessionForThread(thread.threadId);
  return `
    <button class="nav-item ${thread.threadId === state.currentThreadId ? "active" : ""}" type="button" data-thread-id="${escapeHtml(thread.threadId)}">
      <div class="nav-title">${escapeHtml(shortText(thread.title || thread.preview || t("untitled"), 42))}</div>
      <div class="nav-meta">${escapeHtml(threadMeta(thread, linked))}</div>
    </button>
  `;
}

function renderLibrary() {
  const { liveSessions, recent, history } = bucketThreads();

  if (state.sessionsLoading && !state.sessionsLoaded) {
    dom.liveList.innerHTML = renderLibraryPlaceholder("loading", t("loading"));
  } else if (liveSessions.length) {
    dom.liveList.innerHTML = liveSessions.map(renderSessionNavItem).join("");
  } else if (state.sessionsError) {
    dom.liveList.innerHTML = renderLibraryPlaceholder("error", `${t("loadFailed")} · ${shortText(state.sessionsError, 48)}`);
  } else {
    dom.liveList.innerHTML = renderLibraryPlaceholder("empty", t("noLiveSessions"));
  }

  if (state.threadsLoading && !state.threadsLoaded) {
    dom.recentList.innerHTML = renderLibraryPlaceholder("loading", t("loading"));
  } else if (recent.length) {
    dom.recentList.innerHTML = recent.map(renderThreadNavItem).join("");
  } else if (state.threadsError) {
    dom.recentList.innerHTML = renderLibraryPlaceholder("error", `${t("loadFailed")} · ${shortText(state.threadsError, 48)}`);
  } else {
    dom.recentList.innerHTML = renderLibraryPlaceholder("empty", t("noRecentThreads"));
  }

  dom.historyList.innerHTML = Object.entries(history)
    .filter(([, items]) => items.length)
    .map(
      ([bucket, items]) => `
        <div class="history-group">
          <div class="history-label">${escapeHtml(bucketLabel(bucket))}</div>
          <div class="nav-list">${items.map(renderThreadNavItem).join("")}</div>
        </div>
      `,
    )
    .join("");

  dom.historyFold.open = state.historyOpen;
}

function textFromParts(content) {
  if (typeof content === "string") {
    return normalizeDisplayText(content);
  }
  if (!Array.isArray(content)) {
    return "";
  }
  return normalizeDisplayText(content
    .map((part) => {
      if (typeof part === "string") {
        return part;
      }
      if (typeof part?.text === "string") {
        return part.text;
      }
      if (typeof part?.content === "string") {
        return part.content;
      }
      return "";
    })
    .filter(Boolean)
    .join("\n"));
}

function renderRichText(value) {
  return escapeHtml(trimVisibleText(value)).replaceAll("\n", "<br>");
}

function stripAttachmentBoilerplate(value) {
  const raw = String(value ?? "").replace(/\r\n?/g, "\n");
  return raw.replace(/^# Files mentioned by the user:\n[\s\S]*?## My request for Codex:\n*/m, "");
}

function stripPlanModeBoilerplate(value) {
  const raw = String(value ?? "").replace(/\r\n?/g, "\n");
  return raw.replace(/\n*<codex-mobile-plan-mode>[\s\S]*?<\/codex-mobile-plan-mode>\n*/g, "\n");
}

function normalizeDisplayText(value) {
  return trimVisibleText(stripPlanModeBoilerplate(stripAttachmentBoilerplate(value)));
}

function trimVisibleText(value) {
  const raw = String(value ?? "").replace(/\r\n?/g, "\n");
  if (!raw.trim()) {
    return "";
  }
  const lines = raw.split("\n");
  while (lines.length && !lines[0].trim()) {
    lines.shift();
  }
  while (lines.length && !lines[lines.length - 1].trim()) {
    lines.pop();
  }
  return lines.join("\n");
}

function normalizeChips(chips) {
  return (chips || [])
    .map((item) => trimVisibleText(item))
    .filter(Boolean);
}

function shouldCollapseLongText(value) {
  if (isDesktop()) {
    return false;
  }
  const text = normalizeDisplayText(value);
  if (!text) {
    return false;
  }
  const lines = text.split("\n").length;
  return text.length > 420 || lines > 12;
}

function previewText(value, max = 120) {
  const normalized = normalizeDisplayText(value).replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "";
  }
  return shortText(normalized, max);
}

function renderCollapsibleBody(value, previewLength = 200) {
  const text = normalizeDisplayText(value);
  if (!text) {
    return "";
  }
  if (!shouldCollapseLongText(text)) {
    return `<div class="card-body">${renderRichText(text)}</div>`;
  }
  const preview = previewText(text, isDesktop() ? previewLength : Math.min(previewLength, 88));
  return `
    <details class="card-details">
      <summary class="card-summary">
        <span class="card-summary-text">${escapeHtml(preview)}</span>
      </summary>
      <div class="card-body">${renderRichText(text)}</div>
    </details>
  `;
}

function renderMobilePlainText(value, expandKey) {
  const text = normalizeDisplayText(value);
  if (!text) {
    return "";
  }
  const collapsed = shouldCollapseMobileText(text) && !isMobileExpanded(expandKey);
  const visibleText = collapsed ? mobileExcerptText(text) : text;
  const toggle = shouldCollapseMobileText(text)
    ? `<button class="plain-toggle" type="button" data-expand-key="${escapeHtml(expandKey)}">${escapeHtml(collapseButtonLabel(!collapsed))}</button>`
    : "";
  return `
    <div class="plain-bubble-body">${renderRichText(visibleText)}</div>
    ${toggle}
  `;
}

function renderMobilePlainBubble(entry, expandKey) {
  const text = normalizeDisplayText(entry.content);
  if (!text) {
    return "";
  }
  return `
    <article class="plain-bubble ${escapeHtml(entry.role || "assistant")} ${entry.draft ? "draft" : ""}">
      <div class="plain-bubble-label">${escapeHtml(entry.label)}</div>
      ${renderMobilePlainText(text, expandKey)}
    </article>
  `;
}

function renderMobilePlainStatus(entry, expandKey) {
  const text = normalizeDisplayText(entry.body);
  if (!text) {
    return "";
  }
  return `
    <div class="plain-status-line ${escapeHtml(entry.tone || "")}">
      <div class="plain-status-label">${escapeHtml(entry.label)}</div>
      ${renderMobilePlainText(text, expandKey)}
    </div>
  `;
}

function setMobileReaderItems(items) {
  state.mobileReaderItems = Object.create(null);
  for (const item of items) {
    if (!item?.readerKey) {
      continue;
    }
    state.mobileReaderItems[item.readerKey] = item;
  }
  if (state.readerItem?.readerKey) {
    state.readerItem = state.mobileReaderItems[state.readerItem.readerKey] || null;
    if (!state.readerItem) {
      setPanel(dom.readerPanel, false);
    }
  }
}

function renderMobilePreviewItem(entry) {
  const attachments = entry.attachments || [];
  const preview = mobilePreviewSnippet(entry.content || entry.body || "") || (attachments.length ? "图片" : "");
  if (!preview && !attachments.length) {
    return "";
  }
  const meta = [
    entry.timestamp ? formatTime(entry.timestamp) : "",
    entry.tone ? statusLabel(entry.tone) : "",
  ]
    .filter(Boolean)
    .join(" · ");
  return `
    <button class="preview-item ${escapeHtml(entry.role || entry.kind || "message")} ${escapeHtml(entry.tone || "")}" type="button" data-reader-key="${escapeHtml(entry.readerKey)}">
      <span class="preview-item-label">${escapeHtml(entry.label)}</span>
      ${renderMessageAttachments(attachments)}
      <span class="preview-item-text">${escapeHtml(preview)}</span>
      ${meta ? `<span class="preview-item-meta">${escapeHtml(meta)}</span>` : ""}
    </button>
  `;
}

function isRenderableTimelineEntry(entry) {
  if (!entry) {
    return false;
  }
  if (entry.kind === "message" || entry.kind === "reasoning") {
    return Boolean(trimVisibleText(entry.content) || (entry.attachments || []).length);
  }
  if (entry.kind === "status") {
    return Boolean(trimVisibleText(entry.body));
  }
  if (entry.kind === "activity") {
    return Boolean(trimVisibleText(entry.body) || normalizeChips(entry.chips).length);
  }
  return false;
}

function formatRelativeTimeLabel(value) {
  const text = formatTime(value);
  return text ? t("updatedAt").replace("{time}", text) : "";
}

function renderMessageCard(entry) {
  const content = normalizeDisplayText(entry.content);
  const attachments = entry.attachments || [];
  if (!content && !attachments.length) {
    return "";
  }
  return `
    <article class="message-card ${escapeHtml(entry.role)} ${entry.draft ? "draft" : ""}">
      <div class="message-label">${escapeHtml(entry.label)}</div>
      ${renderMessageAttachments(attachments)}
      ${renderCollapsibleBody(content, 220)}
    </article>
  `;
}

function renderReasoningCard(entry) {
  const content = trimVisibleText(entry.content);
  if (!content) {
    return "";
  }
  const preview = shortText(content, 140);
  return `
    <article class="reasoning-card">
      <details>
        <summary>${escapeHtml(entry.label || t("reasoning"))}</summary>
        <div class="reasoning-preview">${escapeHtml(preview)}</div>
        <div class="reasoning-body">${renderCollapsibleBody(content, 200)}</div>
      </details>
    </article>
  `;
}

function renderActivityCard(entry) {
  const body = trimVisibleText(entry.body);
  const chips = normalizeChips(entry.chips)
    .map((item) => `<span class="activity-chip">${escapeHtml(item)}</span>`)
    .join("");
  if (!body && !chips) {
    return "";
  }
  return `
    <article class="activity-card">
      <div class="activity-label">${escapeHtml(entry.label)}</div>
      ${body ? `<div class="activity-body">${renderCollapsibleBody(body, 180)}</div>` : ""}
      ${chips ? `<div class="activity-chip-row">${chips}</div>` : ""}
    </article>
  `;
}

function renderStatusCard(entry) {
  const body = trimVisibleText(entry.body);
  if (!body) {
    return "";
  }
  return `
    <article class="status-card ${escapeHtml(entry.tone || "")}">
      <div class="status-label">${escapeHtml(entry.label)}</div>
      <div class="status-body">${renderCollapsibleBody(body, 180)}</div>
    </article>
  `;
}

function renderTimelineEntry(entry) {
  if (entry.kind === "message") {
    return renderMessageCard(entry);
  }
  if (entry.kind === "reasoning") {
    return renderReasoningCard(entry);
  }
  if (entry.kind === "status") {
    return renderStatusCard(entry);
  }
  return renderActivityCard(entry);
}

function eventTimeMs(event) {
  const value = Date.parse(String(event?.timestamp || ""));
  return Number.isFinite(value) ? value : 0;
}

function isTransientFailureEvent(event) {
  const type = String(event?.type || "");
  return type === "ui.followup.failed" || type === "session.failed";
}

function currentSessionRecoveredAtMs() {
  const session = state.currentSession;
  if (!session || session.status === "failed" || session.lastError) {
    return 0;
  }
  const updatedAt = Date.parse(String(session.updatedAt || ""));
  const syncedAt = Date.parse(String(session.lastThreadSyncAt || ""));
  return Math.max(
    Number.isFinite(updatedAt) ? updatedAt : 0,
    Number.isFinite(syncedAt) ? syncedAt : 0,
  );
}

function shouldDisplaySessionEvent(event) {
  if (!event) {
    return false;
  }
  if (!isTransientFailureEvent(event)) {
    return true;
  }
  const recoveredAt = currentSessionRecoveredAtMs();
  const failedAt = eventTimeMs(event);
  if (!recoveredAt || !failedAt) {
    return true;
  }
  return recoveredAt < failedAt;
}

function pruneSessionEventHistory() {
  state.sessionEvents = state.sessionEvents.filter((event) => shouldDisplaySessionEvent(event));
}

function clearLocalFollowupFailures() {
  state.sessionEvents = state.sessionEvents.filter((event) => String(event?.type || "") !== "ui.followup.failed");
}

function summarizeToolState(event) {
  return event.type === "tool.completed" ? t("toolCompleted") : t("toolRunning");
}

function normalizeSessionEventEntry(event) {
  const type = String(event?.type || "");
  if (
    !type
    || type === "message.delta"
    || type === "message.completed"
    || type === "session.created"
    || type === "commandExecution"
    || type === "fileChange"
    || type === "webSearch"
    || type === "contextCompaction"
  ) {
    return null;
  }
  if (type === "tool.started" || type === "tool.completed") {
    return {
      kind: "activity",
      label: t("tools"),
      body: shortText(event.summary || event.message || event.command || "", 180),
      chips: [event.name || t("tool"), summarizeToolState(event)].filter(Boolean),
      timestamp: event.timestamp,
    };
  }
  if (type === "turn.plan.updated") {
    return {
      kind: "activity",
      label: t("plan"),
      body: "",
      chips: Array.isArray(event.plan) ? event.plan.map((item) => shortText(item.step, 48)).filter(Boolean) : [t("planUpdated")],
      timestamp: event.timestamp,
    };
  }
  if (type === "turn.diff.updated") {
    return {
      kind: "activity",
      label: t("diff"),
      body: "",
      chips: Array.isArray(event.diff?.files) ? event.diff.files.map((item) => shortText(item, 36)) : [t("diffUpdated")],
      timestamp: event.timestamp,
    };
  }
  if (type === "approval.required") {
    return {
      kind: "status",
      tone: "waiting",
      label: t("approval"),
      body: shortText(event.message || event.approval?.summary || t("approvalRequired"), 220),
      timestamp: event.timestamp,
    };
  }
  if (type === "approval.resolved") {
    return {
      kind: "activity",
      label: t("approval"),
      body: shortText(event.message || event.action || "", 180),
      timestamp: event.timestamp,
    };
  }
  if (type === "session.waiting") {
    return {
      kind: "status",
      tone: "waiting",
      label: t("waiting"),
      body: shortText(event.message || t("approvalRequired"), 220),
      timestamp: event.timestamp,
    };
  }
  if (type === "session.completed") {
    return {
      kind: "status",
      tone: "completed",
      label: t("done"),
      body: shortText(event.summary || t("sessionCompleted"), 220),
      timestamp: event.timestamp,
    };
  }
  if (type === "session.failed") {
    return {
      kind: "status",
      tone: "failed",
      label: t("failed"),
      body: shortText(event.message || t("sessionFailed"), 220),
      timestamp: event.timestamp,
    };
  }
  if (type === "ui.followup.sent") {
    return {
      kind: "activity",
      label: t("queued"),
      body: shortText(event.content || t("sentWaiting"), 220),
      timestamp: event.timestamp,
    };
  }
  if (type === "ui.followup.failed") {
    return {
      kind: "status",
      tone: "failed",
      label: t("sendFailed"),
      body: shortText(event.message || t("sendFailed"), 220),
      timestamp: event.timestamp,
    };
  }
  if (type === "thread.mirrored") {
    return {
      kind: "activity",
      label: t("synced"),
      body: shortText(statusLabel(event.status || "completed"), 120),
      timestamp: event.timestamp,
    };
  }
  return {
    kind: "activity",
    label: t("event"),
    body: shortText(event.message || event.summary || type, 180),
    timestamp: event.timestamp,
  };
}

function normalizeSessionTimeline() {
  const session = state.currentSession;
  const entries = [];
  let order = 0;
  for (const message of session?.messages || []) {
    entries.push({
      kind: "message",
      role: message.role === "user" ? "user" : "assistant",
      label: message.role === "user" ? t("user") : t("assistant"),
      content: message.content || "",
      attachments: message.attachments || [],
      draft: Boolean(message.pending),
      timestamp: message.createdAt || message.timestamp,
      sortKey: 1,
      order: ++order,
    });
  }
  for (const event of state.sessionEvents) {
    if (!shouldDisplaySessionEvent(event)) {
      continue;
    }
    const entry = normalizeSessionEventEntry(event);
    if (entry) {
      entries.push({ ...entry, sortKey: 2, order: ++order });
    }
  }
  if (state.assistantDraft) {
    entries.push({
      kind: "reasoning",
      label: t("reasoning"),
      content: state.assistantDraft,
      timestamp: new Date().toISOString(),
      sortKey: 3,
      order: ++order,
    });
  }
  return entries.filter(isRenderableTimelineEntry).sort((left, right) => {
    const leftHasTimestamp = Boolean(left.timestamp);
    const rightHasTimestamp = Boolean(right.timestamp);
    const a = new Date(left.timestamp || 0).getTime();
    const b = new Date(right.timestamp || 0).getTime();
    if (leftHasTimestamp && rightHasTimestamp && a !== b) {
      return a - b;
    }
    if (leftHasTimestamp !== rightHasTimestamp) {
      return leftHasTimestamp ? -1 : 1;
    }
    if ((left.order || 0) !== (right.order || 0)) {
      return (left.order || 0) - (right.order || 0);
    }
    return (left.sortKey || 0) - (right.sortKey || 0);
  });
}

function normalizeMobileSessionStatusEvent(event) {
  const type = String(event?.type || "");
  if (type === "approval.required" || type === "session.waiting") {
    return {
      kind: "status",
      tone: "waiting",
      label: t("waiting"),
      body: event.message || event.approval?.summary || t("approvalRequired"),
      timestamp: event.timestamp,
    };
  }
  if (type === "session.completed") {
    return {
      kind: "status",
      tone: "completed",
      label: t("done"),
      body: event.summary || t("sessionCompleted"),
      timestamp: event.timestamp,
    };
  }
  if (type === "session.failed" || type === "ui.followup.failed") {
    return {
      kind: "status",
      tone: "failed",
      label: type === "ui.followup.failed" ? t("sendFailed") : t("failed"),
      body: event.message || t("sendFailed"),
      timestamp: event.timestamp,
    };
  }
  if (type === "ui.followup.sent") {
    return {
      kind: "status",
      tone: "queued",
      label: t("queued"),
      body: event.content || t("sentWaiting"),
      timestamp: event.timestamp,
    };
  }
  return null;
}

function normalizeMobileSessionTranscript() {
  const entries = [];
  let order = 0;
  for (const message of state.currentSession?.messages || []) {
    const content = normalizeDisplayText(message.content);
    const attachments = message.attachments || [];
    if (!content && !attachments.length) {
      continue;
    }
    entries.push({
      kind: "message",
      role: message.role === "user" ? "user" : "assistant",
      label: message.role === "user" ? t("user") : t("assistant"),
      content,
      attachments,
      draft: Boolean(message.pending),
      timestamp: message.createdAt || message.timestamp,
      order: ++order,
      expandKey: mobileExpandKey("session", state.currentSessionId, "message", order),
    });
  }
  for (const event of state.sessionEvents) {
    if (!shouldDisplaySessionEvent(event)) {
      continue;
    }
    const entry = normalizeMobileSessionStatusEvent(event);
    if (!entry || !normalizeDisplayText(entry.body)) {
      continue;
    }
    entries.push({
      ...entry,
      order: ++order,
      expandKey: mobileExpandKey("session", state.currentSessionId, "status", order),
    });
  }
  if (state.assistantDraft && normalizeDisplayText(state.assistantDraft)) {
    entries.push({
      kind: "message",
      role: "assistant",
      label: t("assistant"),
      content: state.assistantDraft,
      draft: true,
      timestamp: new Date().toISOString(),
      order: ++order,
      expandKey: mobileExpandKey("session", state.currentSessionId, "draft", order),
    });
  }
  return entries.sort((left, right) => {
    const a = Date.parse(String(left.timestamp || "")) || 0;
    const b = Date.parse(String(right.timestamp || "")) || 0;
    if (a !== b) {
      return a - b;
    }
    return (left.order || 0) - (right.order || 0);
  });
}

function mobileReaderMeta(entry) {
  return [
    entry?.label || "",
    entry?.timestamp ? formatTime(entry.timestamp) : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function renderReaderSheet() {
  const show = isMobilePlainMode() && Boolean(state.readerItem);
  if (!show) {
    setPanel(dom.readerPanel, false);
    dom.readerMeta.textContent = t("details");
    dom.readerContent.innerHTML = "";
    return;
  }
  dom.readerMark.textContent = t("details");
  dom.readerMeta.textContent = mobileReaderMeta(state.readerItem) || t("details");
  dom.readerContent.innerHTML = `
    ${renderMessageAttachments(state.readerItem.attachments || [])}
    ${renderRichText(state.readerItem.content || state.readerItem.body || "")}
  `;
}

function renderActivityStrip() {
  dom.activityStrip.innerHTML = "";
}

function activeApprovalItems() {
  return state.approvals.filter((item) => item.status === "pending");
}

function currentDesktopApprovalSession() {
  const session = state.currentSession;
  if (!session || session.pendingApprovalSource !== "desktop") {
    return null;
  }
  if (activeApprovalItems().length) {
    return null;
  }
  return session;
}

function renderDesktopApprovalStrip() {
  const session = currentDesktopApprovalSession();
  if (!session) {
    dom.desktopApprovalStrip.innerHTML = "";
    dom.desktopApprovalStrip.classList.remove("has-items");
    if (dom.desktopApprovalPanel.dataset.open === "true") {
      setPanel(dom.desktopApprovalPanel, false);
    }
    return;
  }
  const disabled = !session.desktopApprovalControllable || state.mode !== "direct";
  dom.desktopApprovalStrip.classList.add("has-items");
  dom.desktopApprovalStrip.innerHTML = `
    <div class="desktop-approval-item">
      <div class="approval-title">${escapeHtml(t("desktopApprovalTitle"))}</div>
      <div>${escapeHtml(t("approvalRequired"))}</div>
      <div class="desktop-approval-copy">${escapeHtml(t("desktopApprovalHint"))}</div>
      <div class="desktop-approval-actions">
        <button type="button" data-action="open-desktop-approval" ${disabled ? "disabled" : ""}>${escapeHtml(disabled ? t("desktopApprovalUnavailable") : t("openDesktopApproval"))}</button>
      </div>
    </div>
  `;
}

function renderApprovals() {
  if (!state.currentSessionId) {
    dom.approvalStrip.innerHTML = "";
    dom.approvalStrip.classList.remove("has-items");
    dom.desktopApprovalStrip.innerHTML = "";
    dom.desktopApprovalStrip.classList.remove("has-items");
    return;
  }
  const active = activeApprovalItems();
  dom.approvalStrip.classList.toggle("has-items", active.length > 0);
  dom.approvalStrip.innerHTML = active
    .map((item) => {
      const form = renderApprovalInputFields(item);
      const buttons = (item.availableActions || [])
        .map((action) => {
          const danger = action === "reject" || action === "cancel" ? ` data-kind="danger"` : "";
          return `<button type="button"${danger} data-approval-id="${escapeHtml(item.approvalId)}" data-action="${escapeHtml(action)}">${escapeHtml(actionLabel(action))}</button>`;
        })
        .join("");
      return `
        <div class="approval-item">
          <div class="approval-title">${escapeHtml(t("approval"))}</div>
          <div>${escapeHtml(item.title || t("approvalRequired"))}</div>
          <div class="approval-copy">${escapeHtml(shortText(item.summary || t("approvalRequired"), 160))}</div>
          ${form}
          <div class="approval-actions">${buttons}</div>
        </div>
      `;
    })
    .join("");
  renderDesktopApprovalStrip();
}

function renderApprovalInputFields(item) {
  const params = item?.payload?.params || {};
  const questions = Array.isArray(params.questions) ? params.questions : [];
  if (item.kind !== "item/tool/requestUserInput") {
    return "";
  }
  if (questions.length) {
    return `
      <div class="approval-form" data-approval-form="${escapeHtml(item.approvalId)}">
        ${questions.map((question) => renderApprovalQuestionInput(item.approvalId, question)).join("")}
      </div>
    `;
  }
  return `
    <div class="approval-form" data-approval-form="${escapeHtml(item.approvalId)}">
      <textarea
        class="approval-textarea"
        data-approval-content="${escapeHtml(item.approvalId)}"
        rows="3"
        placeholder="${escapeHtml(t("inputPrompt"))}"
      ></textarea>
    </div>
  `;
}

function renderApprovalQuestionInput(approvalId, question) {
  const questionId = String(question?.id || "").trim();
  const label = String(question?.question || questionId || t("inputPrompt"));
  const options = Array.isArray(question?.options) ? question.options : [];
  if (options.length) {
    return `
      <label class="approval-field">
        <span>${escapeHtml(label)}</span>
        <select data-approval-question="${escapeHtml(approvalId)}" data-question-id="${escapeHtml(questionId)}">
          ${options
            .map((option) => `<option value="${escapeHtml(String(option?.label || ""))}">${escapeHtml(String(option?.label || ""))}</option>`)
            .join("")}
        </select>
      </label>
    `;
  }
  return `
    <label class="approval-field">
      <span>${escapeHtml(label)}</span>
      <input
        type="text"
        data-approval-question="${escapeHtml(approvalId)}"
        data-question-id="${escapeHtml(questionId)}"
        placeholder="${escapeHtml(label)}"
      />
    </label>
  `;
}

function renderSessionConversation() {
  if (isMobilePlainMode()) {
    const entries = normalizeMobileSessionTranscript();
    const previewEntries = entries.map((entry, index) => ({
      ...entry,
      readerKey: mobileExpandKey("session", state.currentSessionId, "reader", index + 1),
    }));
    setMobileReaderItems(previewEntries);
    dom.conversationLog.innerHTML = previewEntries.length
      ? `<div class="preview-list">${previewEntries.map(renderMobilePreviewItem).join("")}</div>`
      : "";
    return;
  }
  setMobileReaderItems([]);
  const timeline = normalizeSessionTimeline();
  dom.conversationLog.innerHTML = timeline.length
    ? `<div class="timeline-group">${timeline.map(renderTimelineEntry).join("")}</div>`
    : "";
}

function renderSessionContext() {
  const session = state.currentSession;
  if (!session) {
    dom.sessionContext.innerHTML = "";
    dom.sendFollowup.disabled = true;
    return;
  }
  const desktopSendBlocked = !sessionIsDesktopAligned(session, "default");
  const chips = [
    session.workspace,
    statusLabel(session.status),
    sessionKindLabel(session.sessionKind),
    sessionSyncLabel(session),
    session.isActive ? t("active") : "",
    session.lastThreadSyncAt ? t("syncAt").replace("{time}", formatTime(session.lastThreadSyncAt)) : "",
  ]
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");
  dom.sessionContext.innerHTML = `
    <div class="context-title">${escapeHtml(shortText(session.title || t("untitled"), 72))}</div>
    <div class="context-subline">${chips}</div>
  `;
  dom.sendFollowup.disabled = state.sending || desktopSendBlocked;
  dom.sendFollowup.title = desktopSendBlocked ? t("desktopAlignRequired") : "";
  dom.cancelSession.disabled = false;
}

function renderSessionDebug() {
  dom.sessionDebug.classList.toggle("hidden", isMobilePlainMode());
  if (isMobilePlainMode()) {
    dom.debugLog.innerHTML = "";
    return;
  }
  dom.debugLog.innerHTML = state.sessionEvents.length
    ? state.sessionEvents
        .slice(-24)
        .reverse()
        .map(
          (item) => `
            <div class="debug-item">
              <div>${escapeHtml(item.type || t("event"))}</div>
              <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
            </div>
          `,
        )
        .join("")
    : `<div class="nav-meta">${escapeHtml(t("noDebugEvents"))}</div>`;
}

function normalizeThreadTurns(thread) {
  return (thread.turns || []).map((turn, index) => {
    const entries = [];
    const toolChips = [];
    let commandExecutionCount = 0;
    let commandExecutionDone = 0;
    for (const item of turn.items || []) {
      const type = String(item.type || "");
      if (type === "userMessage") {
        const text = textFromParts(item.content);
        if (text) {
          entries.push({
            kind: "message",
            role: "user",
            label: t("user"),
            content: text,
          });
        }
        continue;
      }
      if (type === "agentMessage") {
        const text = textFromParts(item.content) || item.text || "";
        if (!text) {
          continue;
        }
        if (item.phase === "commentary") {
          if (!isDesktop()) {
            continue;
          }
          entries.push({
            kind: "reasoning",
            label: t("reasoning"),
            content: text,
          });
        } else {
          entries.push({
            kind: "message",
            role: "assistant",
            label: t("assistant"),
            content: text,
          });
        }
        continue;
      }
      if (type.includes("plan")) {
        entries.push({
          kind: "activity",
          label: t("plan"),
          chips: Array.isArray(item.plan) ? item.plan.map((step) => shortText(step.step || step, 48)) : [shortText(item.summary || t("planUpdated"), 48)],
          body: "",
        });
        continue;
      }
      if (type.includes("diff")) {
        entries.push({
          kind: "activity",
          label: t("diff"),
          chips: Array.isArray(item.files) ? item.files.map((file) => shortText(file, 32)) : [shortText(item.summary || t("diffUpdated"), 48)],
          body: "",
        });
        continue;
      }
      if (type.includes("approval")) {
        entries.push({
          kind: "status",
          tone: "waiting",
          label: t("approval"),
          body: shortText(item.summary || item.title || t("approvalRequired"), 180),
        });
        continue;
      }
      if (type === "commandExecution") {
        commandExecutionCount += 1;
        if (String(item.status || "").toLowerCase() === "completed") {
          commandExecutionDone += 1;
        }
        continue;
      }
      const summary = shortText(item.summary || item.title || item.name || type, 32);
      if (summary) {
        toolChips.push(summary);
      }
    }
    if (commandExecutionCount) {
      toolChips.unshift(
        `${commandExecutionCount} ${t("tools")}`,
        commandExecutionDone === commandExecutionCount ? t("toolCompleted") : t("toolRunning"),
      );
    }
    const compactToolChips = toolChips.slice(0, 6);
    if (toolChips.length > compactToolChips.length) {
      compactToolChips.push(`+${toolChips.length - compactToolChips.length}`);
    }
    if (compactToolChips.length) {
      entries.push({
        kind: "activity",
        label: t("tools"),
        chips: compactToolChips,
        body: "",
      });
    }
    if (turn.error) {
      entries.push({
        kind: "status",
        tone: "failed",
        label: t("failed"),
        body: turn.error,
      });
    }
    const renderableEntries = entries.filter(isRenderableTimelineEntry);
    return {
      turnId: turn.turnId,
      index: index + 1,
      status: turn.status,
      timestamp: turn.updatedAt || turn.completedAt || turn.createdAt || thread.updatedAt,
      entries: renderableEntries,
    };
  });
}

function normalizeMobileThreadTranscript(thread) {
  const entries = [];
  let order = 0;
  for (const turn of thread.turns || []) {
    for (const item of turn.items || []) {
      const type = String(item.type || "");
      if (type === "userMessage") {
        const content = normalizeDisplayText(textFromParts(item.content));
        if (!content) {
          continue;
        }
        entries.push({
          kind: "message",
          role: "user",
          label: t("user"),
          content,
          timestamp: item.createdAt || turn.updatedAt || thread.updatedAt,
          order: ++order,
          expandKey: mobileExpandKey("thread", thread.threadId, "message", order),
        });
        continue;
      }
      if (type === "agentMessage") {
        if (item.phase === "commentary") {
          continue;
        }
        const content = normalizeDisplayText(textFromParts(item.content) || item.text || "");
        if (!content) {
          continue;
        }
        entries.push({
          kind: "message",
          role: "assistant",
          label: t("assistant"),
          content,
          timestamp: item.createdAt || turn.updatedAt || thread.updatedAt,
          order: ++order,
          expandKey: mobileExpandKey("thread", thread.threadId, "message", order),
        });
      }
    }
    const turnStatus = String(turn.status || "").toLowerCase();
    const error = normalizeDisplayText(turn.error || "");
    if (error) {
      entries.push({
        kind: "status",
        tone: "failed",
        label: t("failed"),
        body: error,
        timestamp: turn.updatedAt || thread.updatedAt,
        order: ++order,
        expandKey: mobileExpandKey("thread", thread.threadId, "status", order),
      });
      continue;
    }
    if (turnStatus === "waiting" || turnStatus === "failed") {
      entries.push({
        kind: "status",
        tone: turnStatus === "failed" ? "failed" : "waiting",
        label: statusLabel(turnStatus),
        body: statusLabel(turnStatus),
        timestamp: turn.updatedAt || thread.updatedAt,
        order: ++order,
        expandKey: mobileExpandKey("thread", thread.threadId, "status", order),
      });
    }
  }
  return entries.sort((left, right) => {
    const a = Date.parse(String(left.timestamp || "")) || 0;
    const b = Date.parse(String(right.timestamp || "")) || 0;
    if (a !== b) {
      return a - b;
    }
    return (left.order || 0) - (right.order || 0);
  });
}

function renderThreadContext() {
  const thread = state.currentThread;
  if (!thread) {
    dom.threadContext.innerHTML = "";
    dom.resumeThread.disabled = true;
    dom.resumeThreadInline.disabled = true;
    return;
  }
  const linked = findSessionForThread(thread.threadId);
  const aligning = state.aligningThread;
  const chips = [
    thread.workspace,
    statusLabel(thread.status),
    linked ? (linked.isActive ? t("active") : t("adopted")) : "",
    thread.updatedAt ? formatRelativeTimeLabel(thread.updatedAt) : "",
  ]
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");
  dom.threadContext.innerHTML = `
    <div class="context-title">${escapeHtml(shortText(thread.title || thread.preview || t("untitled"), 72))}</div>
    <div class="context-subline">${chips}</div>
    ${linked?.desktopTargetMessage ? `<div class="nav-meta">${escapeHtml(linked.desktopTargetMessage)}</div>` : ""}
  `;
  dom.resumeThread.disabled = aligning;
  dom.resumeThreadInline.disabled = aligning;
  dom.resumeThreadInline.textContent = aligning ? t("desktopAligning") : t("continueThread");
}

function renderThreadSummary() {
  if (isMobilePlainMode()) {
    dom.threadSummary.innerHTML = "";
    return;
  }
  const thread = state.currentThread;
  if (!thread) {
    dom.threadSummary.innerHTML = "";
    return;
  }
  const cards = [
    thread.preview ? { label: t("preview"), body: thread.preview } : null,
    thread.path ? { label: t("path"), body: thread.path } : null,
  ]
    .filter(Boolean)
    .map(renderActivityCard)
    .join("");
  dom.threadSummary.innerHTML = cards;
}

function renderThreadConversation() {
  const thread = state.currentThread;
  if (!thread) {
    dom.threadLog.innerHTML = "";
    return;
  }
  if (isMobilePlainMode()) {
    const entries = normalizeMobileThreadTranscript(thread);
    const previewEntries = entries.map((entry, index) => ({
      ...entry,
      readerKey: mobileExpandKey("thread", thread.threadId, "reader", index + 1),
    }));
    setMobileReaderItems(previewEntries);
    dom.threadLog.innerHTML = previewEntries.length
      ? `<div class="preview-list">${previewEntries.map(renderMobilePreviewItem).join("")}</div>`
      : "";
    return;
  }
  setMobileReaderItems([]);
  const turns = normalizeThreadTurns(thread).filter((turn) => turn.entries.length);
  dom.threadLog.innerHTML = turns.length
    ? `<div class="timeline-group">${turns
        .map((turn) => {
          const meta = [
            t("threadTurn").replace("{count}", turn.index),
            statusLabel(turn.status),
            turn.timestamp ? formatTime(turn.timestamp) : "",
          ]
            .filter(Boolean)
            .join(" · ");
          return `
            <section class="turn-shell">
              <div class="turn-meta">${escapeHtml(meta)}</div>
              ${turn.entries.map(renderTimelineEntry).join("")}
            </section>
          `;
        })
        .join("")}</div>`
    : "";
}

function renderThreadDebug() {
  dom.threadDebugFold.classList.toggle("hidden", isMobilePlainMode());
  if (isMobilePlainMode()) {
    dom.threadDebug.innerHTML = "";
    return;
  }
  const turns = state.currentThread?.turns || [];
  dom.threadDebug.innerHTML = turns.length
    ? turns
        .slice()
        .reverse()
        .map(
          (item) => `
            <div class="debug-item">
              <div>${escapeHtml(item.turnId || t("event"))}</div>
              <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
            </div>
          `,
        )
        .join("")
    : `<div class="nav-meta">${escapeHtml(t("noTurnData"))}</div>`;
}

function resetDesktopPreviewState({ keepSocket = false } = {}) {
  if (!keepSocket && state.desktopPreview.socket) {
    state.desktopPreview.socket.close();
    state.desktopPreview.socket = null;
  }
  state.desktopPreview.connected = false;
  state.desktopPreview.status = "idle";
  state.desktopPreview.unavailable = "";
  state.desktopPreview.pointerActive = false;
  state.desktopPreview.frameSrc = "";
}

function renderDesktopApprovalPanel() {
  const session = currentDesktopApprovalSession();
  const panelOpen = dom.desktopApprovalPanel.dataset.open === "true";
  if (!panelOpen) {
    dom.desktopPreviewImage.classList.add("hidden");
    dom.desktopPreviewImage.removeAttribute("src");
    dom.desktopPreviewEmpty.classList.remove("hidden");
    dom.desktopPreviewEmpty.textContent = t("desktopPreviewUnavailable");
    dom.desktopApprovalStatus.textContent = t("desktopPreviewWaiting");
    return;
  }
  dom.desktopApprovalMark.textContent = t("desktopApprovalPanel");
  if (!session) {
    dom.desktopApprovalStatus.textContent = t("desktopApprovalUnavailable");
    dom.desktopPreviewImage.classList.add("hidden");
    dom.desktopPreviewImage.removeAttribute("src");
    dom.desktopPreviewEmpty.classList.remove("hidden");
    dom.desktopPreviewEmpty.textContent = t("desktopPreviewUnavailable");
    return;
  }
  if (state.desktopPreview.frameSrc) {
    dom.desktopPreviewImage.src = state.desktopPreview.frameSrc;
    dom.desktopPreviewImage.classList.remove("hidden");
    dom.desktopPreviewEmpty.classList.add("hidden");
  } else {
    dom.desktopPreviewImage.classList.add("hidden");
    dom.desktopPreviewImage.removeAttribute("src");
    dom.desktopPreviewEmpty.classList.remove("hidden");
    dom.desktopPreviewEmpty.textContent = state.desktopPreview.unavailable || t("desktopPreviewWaiting");
  }
  dom.desktopApprovalStatus.textContent = state.desktopPreview.unavailable
    ? state.desktopPreview.unavailable
    : state.desktopPreview.connected
      ? t("desktopApprovalTitle")
      : t("desktopPreviewWaiting");
}

function desktopPreviewRatiosFromEvent(event) {
  const image = dom.desktopPreviewImage;
  if (!image || image.classList.contains("hidden")) {
    return null;
  }
  const rect = image.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }
  const xRatio = (event.clientX - rect.left) / rect.width;
  const yRatio = (event.clientY - rect.top) / rect.height;
  return {
    xRatio: Math.min(1, Math.max(0, xRatio)),
    yRatio: Math.min(1, Math.max(0, yRatio)),
  };
}

function handleDesktopSocketMessage(message) {
  const type = String(message?.type || "");
  if (type === "ready" || type === "state") {
    state.desktopPreview.connected = Boolean(message.connected ?? true);
    state.desktopPreview.unavailable = "";
    renderDesktopApprovalPanel();
    return;
  }
  if (type === "preview.frame") {
    state.desktopPreview.connected = true;
    state.desktopPreview.unavailable = "";
    state.desktopPreview.frameSrc = `data:image/jpeg;base64,${message.data || ""}`;
    renderDesktopApprovalPanel();
    return;
  }
  if (type === "preview.unavailable") {
    state.desktopPreview.unavailable = String(message.message || t("desktopPreviewUnavailable"));
    renderDesktopApprovalPanel();
    return;
  }
  if (type === "error") {
    state.desktopPreview.unavailable = String(message.message || t("desktopPreviewUnavailable"));
    renderDesktopApprovalPanel();
  }
}

async function ensureDesktopPreviewSocket() {
  if (state.mode !== "direct") {
    throw new Error("desktop preview is only available over direct bridge access");
  }
  if (state.desktopPreview.socket && state.desktopPreview.socket.readyState === WebSocket.OPEN) {
    return state.desktopPreview.socket;
  }
  if (!client.createDesktopSocket) {
    throw new Error("desktop preview is unavailable");
  }
  const socket = client.createDesktopSocket();
  if (!socket) {
    throw new Error("desktop preview is unavailable");
  }
  state.desktopPreview.socket = socket;
  state.desktopPreview.status = "connecting";
  return await new Promise((resolve, reject) => {
    let opened = false;
    socket.addEventListener("open", () => {
      opened = true;
      state.desktopPreview.connected = true;
      state.desktopPreview.unavailable = "";
      resolve(socket);
      renderDesktopApprovalPanel();
    });
    socket.addEventListener("message", (event) => {
      handleDesktopSocketMessage(JSON.parse(event.data));
    });
    socket.addEventListener("close", () => {
      state.desktopPreview.connected = false;
      state.desktopPreview.pointerActive = false;
      state.desktopPreview.socket = null;
      renderDesktopApprovalPanel();
      if (!opened) {
        reject(new Error("desktop preview connection failed"));
      }
    });
    socket.addEventListener("error", () => {
      state.desktopPreview.unavailable = t("desktopPreviewUnavailable");
      renderDesktopApprovalPanel();
      if (!opened) {
        reject(new Error("desktop preview connection failed"));
      }
    });
  });
}

async function sendDesktopPreviewCommand(payload) {
  const socket = await ensureDesktopPreviewSocket();
  socket.send(JSON.stringify(payload));
}

async function openDesktopApprovalPanel() {
  setPanel(dom.desktopApprovalPanel, true);
  renderDesktopApprovalPanel();
  try {
    await sendDesktopPreviewCommand({ type: "preview.subscribe", id: crypto.randomUUID() });
  } catch (error) {
    state.desktopPreview.unavailable = error.message || t("desktopPreviewUnavailable");
    renderDesktopApprovalPanel();
  }
}

function currentViewKey() {
  if (state.currentView === "wall") {
    return "wall";
  }
  if (state.currentSessionId) {
    return `session:${state.currentSessionId}`;
  }
  if (state.currentThreadId) {
    return `thread:${state.currentThreadId}`;
  }
  return "empty";
}

function currentScrollContainer() {
  if (state.currentView === "wall") {
    return dom.wallView;
  }
  if (state.currentSessionId) {
    return dom.conversationLog;
  }
  if (state.currentThreadId) {
    return dom.threadLog;
  }
  return null;
}

function nearLatest(container, threshold = 72) {
  if (!container) {
    return true;
  }
  return container.scrollHeight - container.clientHeight - container.scrollTop <= threshold;
}

function captureScrollState() {
  const container = currentScrollContainer();
  return {
    key: currentViewKey(),
    scrollTop: container ? container.scrollTop : 0,
    nearLatest: nearLatest(container),
  };
}

function syncJumpLatest() {
  const shouldShow = Boolean((state.hasUnreadBelow || !state.isNearLatest) && currentScrollContainer());
  dom.jumpLatest.classList.toggle("hidden", !shouldShow);
}

function visibleBlockHeight(element) {
  if (!element || element.classList.contains("hidden")) {
    return 0;
  }
  const style = window.getComputedStyle(element);
  if (style.display === "none" || style.visibility === "hidden") {
    return 0;
  }
  return Math.ceil(element.getBoundingClientRect().height);
}

function updateFloatingLayout() {
  const sessionVisible = !dom.sessionView.classList.contains("hidden");
  const threadVisible = !dom.threadView.classList.contains("hidden");
  const dockHeight = sessionVisible
    ? Math.max(visibleBlockHeight(dom.composerDock), 96)
    : threadVisible
      ? Math.max(visibleBlockHeight(dom.threadDock), 72)
      : 24;
  document.documentElement.style.setProperty("--dock-height", `${dockHeight}px`);
  renderDesktopApprovalPanel();
}

function scrollCurrentToLatest({ smooth = false } = {}) {
  const container = currentScrollContainer();
  if (!container) {
    return;
  }
  container.scrollTo({ top: container.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  state.pendingScrollToLatest = false;
  state.isNearLatest = true;
  state.hasUnreadBelow = false;
  syncJumpLatest();
}

function noteIncomingUpdate({ forceLatest = false } = {}) {
  if (forceLatest) {
    state.pendingScrollToLatest = true;
    state.hasUnreadBelow = false;
    return;
  }
  const container = currentScrollContainer();
  if (container && !nearLatest(container)) {
    state.hasUnreadBelow = true;
    state.isNearLatest = false;
  }
}

function finalizeScroll(snapshot, { forceLatest = false } = {}) {
  const container = currentScrollContainer();
  if (!container) {
    state.isNearLatest = true;
    state.hasUnreadBelow = false;
    syncJumpLatest();
    return;
  }
  const switchedView = snapshot?.key !== currentViewKey();
  const snapToLatest = forceLatest || state.pendingScrollToLatest || switchedView || snapshot?.nearLatest;
  if (snapToLatest) {
    window.requestAnimationFrame(() => scrollCurrentToLatest({ smooth: false }));
    return;
  }
  const maxTop = Math.max(container.scrollHeight - container.clientHeight, 0);
  container.scrollTop = Math.min(snapshot?.scrollTop || 0, maxTop);
  state.isNearLatest = nearLatest(container);
  syncJumpLatest();
}

function renderMainView({ forceLatest = false } = {}) {
  const snapshot = captureScrollState();
  const showWall = state.currentView === "wall";
  const hasSession = !showWall && Boolean(state.currentSession);
  const hasThread = !showWall && Boolean(state.currentThread);
  dom.emptyView.classList.toggle("hidden", hasSession || hasThread || showWall);
  dom.wallView.classList.toggle("hidden", !showWall);
  dom.sessionView.classList.toggle("hidden", !hasSession);
  dom.threadView.classList.toggle("hidden", !hasThread);
  if (showWall) {
    renderWallView();
  }
  if (hasSession) {
    renderSessionContext();
    renderApprovals();
    renderAttachmentStrip();
    renderActivityStrip();
    renderSessionConversation();
    renderSessionDebug();
  }
  if (hasThread) {
    renderThreadContext();
    renderThreadSummary();
    renderThreadConversation();
    renderThreadDebug();
  }
  if (!hasSession && !hasThread) {
    setMobileReaderItems([]);
    state.readerItem = null;
  }
  renderReaderSheet();
  renderStatus();
  renderLibrary();
  renderViewActionsPanel();
  updateFloatingLayout();
  finalizeScroll(snapshot, { forceLatest });
}

function replaceSessionInState(session) {
  state.currentSession = session;
  state.currentSessionId = session?.sessionId || null;
  if (!session) {
    return;
  }
  const next = state.sessions.filter((item) => item.sessionId !== session.sessionId);
  next.push(session);
  state.sessions = sortByUpdated(next);
  if (session.sessionId === state.currentSessionId) {
    pruneSessionEventHistory();
  }
}

function renderWorkspaceOptions() {
  dom.workspaceSelect.innerHTML = state.workspaces
    .map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`)
    .join("");
}

function optimisticSendEvent(content) {
  state.sessionEvents.push({
    type: "ui.followup.sent",
    content,
    timestamp: new Date().toISOString(),
  });
}

function optimisticFailEvent(message) {
  state.sessionEvents.push({
    type: "ui.followup.failed",
    message,
    timestamp: new Date().toISOString(),
  });
}

async function refreshHealth() {
  try {
    const payload = await client.health();
    state.backendAvailable = Boolean(payload.backendAvailable);
    state.backendName = payload.backend || state.backendName;
    state.backendError = payload.backendLastError || "";
  } catch (error) {
    state.backendAvailable = false;
    state.backendError = error.message;
  }
  renderStatus();
}

async function loadWorkspaces() {
  const payload = await client.listWorkspaces();
  state.workspaces = payload.items || [];
  renderWorkspaceOptions();
}

async function refreshSessions({ openActive = false, retries = 1 } = {}) {
  state.sessionsLoading = true;
  state.sessionsError = "";
  renderMainView();
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const payload = await client.listSessions();
      state.sessions = sortByUpdated(payload.items || []);
      state.sessionsLoaded = true;
      state.sessionsError = "";
      const active = state.sessions.find((item) => item.isActive) || null;
      if (active) {
        state.activeSession = {
          activeSessionId: active.sessionId,
          source: state.activeSession.source,
          updatedAt: state.activeSession.updatedAt,
        };
      }
      if (openActive && active) {
        state.sessionsLoading = false;
        await openSession(active.sessionId, { announce: false });
        return;
      }
      if (state.currentSessionId) {
        const current = findSession(state.currentSessionId);
        if (current) {
          state.currentSession = { ...state.currentSession, ...current };
          pruneSessionEventHistory();
        }
      }
      state.sessionsLoading = false;
      maybeOpenDefaultTarget();
      renderMainView();
      return;
    } catch (error) {
      lastError = error;
      if (attempt < retries) {
        await sleep(220 * (attempt + 1));
      }
    }
  }
  state.sessionsLoading = false;
  state.sessionsError = lastError?.message || t("loadFailed");
  renderMainView();
  throw lastError;
}

async function loadThreads({ retries = 1 } = {}) {
  state.threadsLoading = true;
  state.threadsError = "";
  renderMainView();
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const payload = await client.listThreads();
      state.threads = sortByUpdated(payload.items || []);
      state.threadsLoaded = true;
      state.threadsError = "";
      state.threadsLoading = false;
      maybeOpenDefaultTarget();
      renderMainView();
      return;
    } catch (error) {
      lastError = error;
      if (attempt < retries) {
        await sleep(220 * (attempt + 1));
      }
    }
  }
  state.threadsLoading = false;
  state.threadsError = lastError?.message || t("loadFailed");
  renderMainView();
  throw lastError;
}

async function refreshActiveSession() {
  try {
    state.activeSession = await client.getActiveSession();
  } catch (error) {
    state.activeSession = { activeSessionId: null, source: null, updatedAt: null };
  }
  renderStatus();
}

function defaultOpenTarget() {
  const activeSessionId = state.activeSession.activeSessionId || state.sessions.find((item) => item.isActive)?.sessionId || null;
  if (activeSessionId) {
    return { kind: "session", id: activeSessionId };
  }
  const liveSession = state.sessions.find((item) => ACTIVE_THREAD_STATUSES.has(String(item.status || "").toLowerCase()));
  if (liveSession) {
    return { kind: "session", id: liveSession.sessionId };
  }
  const recentThread = sortByUpdated(state.threads)[0];
  if (recentThread?.threadId) {
    return { kind: "thread", id: recentThread.threadId };
  }
  return null;
}

function maybeOpenDefaultTarget() {
  if (state.currentSessionId || state.currentThreadId) {
    return;
  }
  const target = defaultOpenTarget();
  if (!target) {
    return;
  }
  if (target.kind === "session") {
    openSession(target.id, { announce: false }).catch(() => {});
    return;
  }
  openThread(target.id).catch(() => {});
}

function scheduleLibraryRecovery() {
  if (state.currentSessionId || state.currentThreadId) {
    return;
  }
  window.setTimeout(() => {
    if (!state.threads.length && !state.threadsLoading) {
      loadThreads({ retries: 2 }).catch(() => {});
    }
    if (!state.sessions.length && !state.sessionsLoading) {
      refreshSessions({ retries: 2 }).catch(() => {});
    }
  }, 800);
}

async function switchUiSubscription() {
  if (!state.accessToken) {
    return;
  }
  if (state.uiUnsubscribe) {
    await state.uiUnsubscribe();
  }
  state.uiUnsubscribe = await client.subscribeUi(handleUiEvent);
}

async function switchSessionSubscription(sessionId) {
  if (state.sessionUnsubscribe) {
    await state.sessionUnsubscribe();
    state.sessionUnsubscribe = null;
  }
  state.sessionEvents = [];
  state.assistantDraft = "";
  if (!sessionId) {
    renderMainView();
    return;
  }
  state.sessionUnsubscribe = await client.subscribeSession(sessionId, (event) => handleSessionEvent(sessionId, event));
}

function scheduleRefresh() {
  window.clearTimeout(state.refreshTimer);
  state.refreshTimer = window.setTimeout(async () => {
    state.syncStatus = "syncing";
    renderStatus();
    try {
      await Promise.all([refreshSessions(), loadThreads()]);
      if (state.currentSessionId) {
        const [session, approvals] = await Promise.all([
          client.getSession(state.currentSessionId),
          client.listApprovals(state.currentSessionId),
        ]);
        noteIncomingUpdate();
        replaceSessionInState(session);
        state.approvals = approvals.items || [];
      }
      if (state.currentThreadId) {
        noteIncomingUpdate();
        state.currentThread = await client.getThread(state.currentThreadId);
      }
      state.syncStatus = "live";
    } catch (error) {
      state.syncStatus = "partial";
    }
    renderMainView();
  }, 240);
}

function mergeApproval(approval) {
  if (!approval?.approvalId) {
    return;
  }
  state.approvals = [
    approval,
    ...state.approvals.filter((item) => item.approvalId !== approval.approvalId),
  ];
}

function removeApproval(approvalId) {
  if (!approvalId) {
    return;
  }
  state.approvals = state.approvals.filter((item) => item.approvalId !== approvalId);
}

async function refreshApprovalsNow(sessionId = state.currentSessionId) {
  if (!sessionId) {
    return;
  }
  try {
    const approvals = await client.listApprovals(sessionId);
    if (sessionId === state.currentSessionId) {
      state.approvals = approvals.items || [];
      renderApprovals();
      updateFloatingLayout();
    }
  } catch (error) {
    // A later full refresh will surface connection errors.
  }
}

async function announceActiveSession(sessionId, source) {
  state.activeSession = await client.setActiveSession(sessionId, source);
  renderStatus();
}

async function openSession(sessionId, { announce = true, localOnly = false, autoAlign = false } = {}) {
  const ticket = ++state.sessionTicket;
  state.currentView = "remote";
  state.mobileExpanded = Object.create(null);
  state.readerItem = null;
  resetDesktopPreviewState({ keepSocket: false });
  setPanel(dom.readerPanel, false);
  setPanel(dom.desktopApprovalPanel, false);
  state.currentThread = null;
  state.currentThreadId = null;
  state.currentSessionId = sessionId;
  state.currentSession = findSession(sessionId) || {
    sessionId,
    title: t("loading"),
    workspace: "",
    status: "running",
    sessionKind: "new",
    messages: [],
  };
  noteIncomingUpdate({ forceLatest: true });
  renderMainView({ forceLatest: true });
  if (announce && !localOnly) {
    announceActiveSession(sessionId, isDesktop() ? "desktop_open" : "mobile_open").catch(() => {});
  }
  await switchSessionSubscription(sessionId);
  let [session, approvals] = await Promise.all([
    client.getSession(sessionId),
    client.listApprovals(sessionId),
  ]);
  if (ticket !== state.sessionTicket) {
    return;
  }
  replaceSessionInState(session);
  state.approvals = approvals.items || [];
  state.currentThread = null;
  setPanel(dom.libraryPanel, false);
  setPanel(dom.viewActionsPanel, false);
  if (autoAlign && !localOnly && sessionNeedsDesktopAlignment(session) && sessionThreadId(session)) {
    state.aligningThread = true;
    renderMainView({ forceLatest: true });
    try {
      const aligned = await client.alignSession(sessionId);
      if (ticket !== state.sessionTicket) {
        return;
      }
      replaceSessionInState(aligned);
      session = findSession(sessionId) || aligned;
      state.currentSession = session;
    } catch (error) {
      const current = findSession(sessionId) || state.currentSession;
      if (current) {
        current.desktopTargetMessage = error.message || t("desktopAlignFailed");
      }
    } finally {
      state.aligningThread = false;
    }
  }
  renderMainView({ forceLatest: true });
}

async function openThread(threadId, options = {}) {
  const ticket = ++state.threadTicket;
  state.currentView = "remote";
  state.mobileExpanded = Object.create(null);
  state.readerItem = null;
  resetDesktopPreviewState({ keepSocket: false });
  setPanel(dom.readerPanel, false);
  setPanel(dom.desktopApprovalPanel, false);
  state.currentThreadId = threadId;
  state.currentThread = {
    threadId,
    title: t("loading"),
    workspace: "",
    status: "idle",
    turns: [],
  };
  state.currentSession = null;
  state.currentSessionId = null;
  state.approvals = [];
  await switchSessionSubscription(null);
  noteIncomingUpdate({ forceLatest: true });
  renderMainView({ forceLatest: true });
  const detail = await client.getThread(threadId);
  if (ticket !== state.threadTicket) {
    return;
  }
  state.currentThread = detail;
  setPanel(dom.libraryPanel, false);
  setPanel(dom.viewActionsPanel, false);
  renderMainView({ forceLatest: true });
  if (options.autoAlign) {
    await handleResumeThread();
  }
}

function mergeAssistantDraft(delta) {
  state.assistantDraft = `${state.assistantDraft || ""}${delta || ""}`;
}

function applySessionEvent(sessionId, event) {
  if (event.type === "message.delta" && event.role === "assistant") {
    mergeAssistantDraft(event.delta || "");
    return;
  }
  if (event.type === "message.completed") {
    if (event.role === "assistant") {
      state.assistantDraft = "";
    }
    if (state.currentSession && state.currentSessionId === sessionId) {
      const role = event.role === "user" ? "user" : "assistant";
      const content = event.content || "";
      const attachments = event.attachments || [];
      state.currentSession.messages = [
        ...(state.currentSession.messages || []).filter(
          (item) => !(item.pending && item.role === role && item.content === content),
        ),
        {
          role,
          content,
          attachments,
          createdAt: event.timestamp || new Date().toISOString(),
        },
      ];
    }
    return;
  }
  if (event.type === "session.completed" && state.currentSession) {
    state.currentSession.status = "completed";
    state.currentSession.resultSummary = event.summary || state.currentSession.resultSummary;
    return;
  }
  if (event.type === "session.failed" && state.currentSession) {
    state.currentSession.status = "failed";
    state.currentSession.lastError = event.message || "";
    return;
  }
  if (event.type === "session.waiting" && state.currentSession) {
    state.currentSession.status = "waiting";
    state.currentSession.lastError = "";
    pruneSessionEventHistory();
    return;
  }
  if (event.type === "thread.mirrored" && state.currentSession) {
    state.currentSession.status = event.status || state.currentSession.status;
    state.currentSession.lastThreadSyncAt = event.timestamp || state.currentSession.lastThreadSyncAt;
    if (event.status && String(event.status).toLowerCase() !== "failed") {
      state.currentSession.lastError = "";
    }
    pruneSessionEventHistory();
  }
}

function handleSessionEvent(sessionId, event) {
  if (sessionId !== state.currentSessionId) {
    return;
  }
  state.sessionEvents = [...state.sessionEvents, event].slice(-200);
  applySessionEvent(sessionId, event);
  if (event.type === "approval.required") {
    mergeApproval(event.approval);
  }
  if (event.type === "approval.resolved") {
    removeApproval(event.approvalId);
  }
  if (event.type === "session.waiting") {
    refreshApprovalsNow(sessionId);
  }
  pruneSessionEventHistory();
  noteIncomingUpdate();
  if (
    event.type === "approval.required"
    || event.type === "approval.resolved"
    || event.type === "session.completed"
    || event.type === "session.failed"
    || event.type === "thread.mirrored"
  ) {
    scheduleRefresh();
  }
  renderMainView();
}

function handleUiEvent(event) {
  const type = String(event?.type || "");
  if (type === "activeSession.changed") {
    state.activeSession = {
      activeSessionId: event.activeSessionId || null,
      source: event.source || null,
      updatedAt: event.updatedAt || null,
    };
    if (
      state.currentView !== "wall"
      && state.activeSession.activeSessionId
      && !state.currentThreadId
      && (state.autoFollow || !isDesktop())
      && state.activeSession.activeSessionId !== state.currentSessionId
    ) {
      openSession(state.activeSession.activeSessionId, { announce: false, localOnly: true }).catch(() => {});
      return;
    }
    renderStatus();
    renderLibrary();
    return;
  }
  if (type === "sessions.changed") {
    scheduleRefresh();
  }
}

async function handlePair() {
  const code = dom.pairCode.value.trim();
  if (!code || state.pairing) {
    return;
  }
  state.pairing = true;
  dom.pairButton.disabled = true;
  dom.pairStatus.textContent = t("pairing");
  try {
    const payload = await client.pair(code);
    saveToken(payload.accessToken);
    setBodyState();
    state.syncStatus = "syncing";
    renderStatus();
    dom.pairStatus.textContent = t("paired");
    await afterPair();
  } catch (error) {
    dom.pairStatus.textContent = error.message || t("routeError");
  } finally {
    state.pairing = false;
    dom.pairButton.disabled = false;
  }
}

async function afterPair() {
  setBodyState();
  state.syncStatus = "syncing";
  renderStatus();
  await refreshHealth();
  await switchUiSubscription();
  const results = await Promise.allSettled([
    loadWorkspaces(),
    refreshActiveSession(),
    refreshSessions({ retries: 2 }),
    loadThreads({ retries: 2 }),
  ]);
  const failed = results.some((item) => item.status === "rejected");
  const target = defaultOpenTarget();
  if (target?.kind === "session") {
    await openSession(target.id, { announce: false });
  } else if (target?.kind === "thread") {
    await openThread(target.id);
  } else {
    scheduleLibraryRecovery();
  }
  state.syncStatus = failed ? "partial" : "live";
  renderMainView({ forceLatest: true });
}

async function handleCreateSession(interactionMode = "default") {
  const workspace = dom.workspaceSelect.value;
  const prompt = dom.promptInput.value.trim();
  const title = dom.titleInput.value.trim();
  if (!workspace || !prompt) {
    return;
  }
  state.syncStatus = "creating";
  renderStatus();
  const session = await client.createSession(workspace, prompt, title, interactionMode);
  dom.promptInput.value = "";
  dom.titleInput.value = "";
  await Promise.all([refreshSessions(), loadThreads()]);
  await openSession(session.sessionId, { announce: false });
  setPanel(dom.composePanel, false);
  state.syncStatus = "live";
  renderStatus();
}

async function handleFollowupSubmit(event, interactionMode = "default") {
  event?.preventDefault?.();
  if (!state.currentSessionId || state.sending) {
    return;
  }
  const hasAttachments = state.pendingAttachments.length > 0;
  const content = dom.followupInput.value.trim() || (hasAttachments ? "请查看我发送的图片。" : "");
  if (!content && !hasAttachments) {
    return;
  }
  if (hasAttachments && interactionMode !== "plan" && state.mode === "cloud") {
    optimisticFailEvent("图片消息请长按发送，使用计划模式进入 app-server。");
    renderMainView();
    return;
  }
  if (!sessionIsDesktopAligned(state.currentSession, interactionMode)) {
    optimisticFailEvent(t("desktopAlignRequired"));
    renderMainView();
    return;
  }
  state.sending = true;
  dom.sendFollowup.disabled = true;
  let tempId = "";
  try {
    const localAttachments = state.pendingAttachments.map((item) => ({
      fileName: item.file?.name || "image",
      mimeType: item.file?.type || "image/jpeg",
      sizeBytes: item.file?.size || 0,
      localPreviewUrl: item.previewUrl,
    }));
    const attachmentIds = await uploadPendingAttachments();
    tempId = `pending-${Date.now()}`;
    state.currentSession.messages = [
      ...(state.currentSession.messages || []),
      { role: "user", content, attachments: localAttachments, createdAt: new Date().toISOString(), pending: true, tempId },
    ];
    clearLocalFollowupFailures();
    optimisticSendEvent(content);
    noteIncomingUpdate({ forceLatest: true });
    renderMainView({ forceLatest: true });
    await announceActiveSession(state.currentSessionId, "send_followup");
    await client.continueSession(state.currentSessionId, content, interactionMode, attachmentIds);
    clearLocalFollowupFailures();
    dom.followupInput.value = "";
    clearPendingAttachments();
    scheduleRefresh();
  } catch (error) {
    if (tempId) {
      state.currentSession.messages = (state.currentSession.messages || []).filter((item) => item.tempId !== tempId);
    }
    optimisticFailEvent(error.message || "send failed");
    renderMainView();
  } finally {
    state.sending = false;
    renderMainView();
  }
}

async function handleCancelSession() {
  if (!state.currentSessionId) {
    return;
  }
  await client.cancelSession(state.currentSessionId);
  scheduleRefresh();
}

async function handleResumeThread(interactionMode = "default") {
  if (!state.currentThreadId || state.aligningThread) {
    return;
  }
  const shouldAlignDesktop = interactionMode !== "plan";
  let session = findSessionForThread(state.currentThreadId);
  state.aligningThread = shouldAlignDesktop;
  renderMainView();
  try {
    if (session) {
      if (isDesktop()) {
        state.autoFollow = true;
      }
    } else {
      session = await client.resumeThread(state.currentThreadId, null, interactionMode);
      await refreshSessions();
      session = findSession(session.sessionId) || session;
    }
    if (shouldAlignDesktop) {
      const aligned = await client.alignSession(session.sessionId);
      replaceSessionInState(aligned);
      session = aligned;
    }
    await Promise.all([refreshSessions(), loadThreads()]);
    await openSession(session.sessionId, { announce: !shouldAlignDesktop });
  } catch (error) {
    await refreshSessions().catch(() => {});
    const linked = findSessionForThread(state.currentThreadId);
    if (linked) {
      linked.desktopTargetMessage = error.message || t("desktopAlignFailed");
    }
    renderMainView();
  } finally {
    state.aligningThread = false;
    renderMainView();
  }
}

async function handleViewActionsPrimary() {
  const action = String(dom.viewActionsPrimary.dataset.action || "");
  if (!action) {
    return;
  }
  if (action === "cancel-session") {
    await handleCancelSession();
    setPanel(dom.viewActionsPanel, false);
    return;
  }
  if (action === "resume-thread") {
    await handleResumeThread();
    setPanel(dom.viewActionsPanel, false);
  }
}

async function handleApproval(action, approvalId) {
  if (!state.currentSessionId) {
    return;
  }
  const approval = state.approvals.find((item) => item.approvalId === approvalId);
  if (!approval) {
    return;
  }
  const payload = { action };
  if (action === "submit") {
    const questions = approval.payload?.params?.questions;
    if (Array.isArray(questions) && questions.length) {
      payload.answers = questions.map((item) => {
        const field = dom.approvalStrip.querySelector(
          `[data-approval-question="${CSS.escape(approvalId)}"][data-question-id="${CSS.escape(String(item.id || ""))}"]`,
        );
        return {
          id: item.id,
          answer: field instanceof HTMLInputElement || field instanceof HTMLSelectElement ? field.value : "",
        };
      });
    } else {
      const field = dom.approvalStrip.querySelector(
        `[data-approval-content="${CSS.escape(approvalId)}"]`,
      );
      payload.content = field instanceof HTMLTextAreaElement ? field.value : "";
    }
  }
  await client.resolveApproval(state.currentSessionId, approvalId, payload);
  scheduleRefresh();
}

function bindPlanLongPress(button, kind) {
  const timerKey = kind === "create" ? "createTimer" : "sendTimer";
  const triggeredKey = kind === "create" ? "createTriggered" : "sendTriggered";
  const runPlanAction = async () => {
    if (kind === "create") {
      await handleCreateSession("plan");
      return;
    }
    await handleFollowupSubmit(null, "plan");
  };
  const clearTimer = () => {
    if (longPressState[timerKey]) {
      window.clearTimeout(longPressState[timerKey]);
      longPressState[timerKey] = null;
    }
  };
  button.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) {
      return;
    }
    longPressState[triggeredKey] = false;
    clearTimer();
    longPressState[timerKey] = window.setTimeout(() => {
      longPressState[triggeredKey] = true;
      runPlanAction().catch(console.error);
    }, PLAN_LONG_PRESS_MS);
  });
  const clearPress = () => clearTimer();
  button.addEventListener("pointerup", clearPress);
  button.addEventListener("pointercancel", clearPress);
  button.addEventListener("pointerleave", clearPress);
  button.addEventListener("click", (event) => {
    if (!longPressState[triggeredKey]) {
      return;
    }
    longPressState[triggeredKey] = false;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
}

function handleNavClick(event) {
  const sessionButton = event.target.closest("[data-session-id]");
  if (sessionButton) {
    const sessionId = sessionButton.dataset.sessionId;
    if (isDesktop() && state.autoFollow === false) {
      openSession(sessionId, { announce: false, localOnly: true }).catch(() => {});
      return;
    }
    openSession(sessionId, { announce: true, autoAlign: !isDesktop() }).catch(() => {});
    return;
  }
  const threadButton = event.target.closest("[data-thread-id]");
  if (threadButton) {
    if (isDesktop()) {
      state.autoFollow = false;
    }
    openThread(threadButton.dataset.threadId).catch(() => {});
  }
}

function handleConversationScroll() {
  const container = currentScrollContainer();
  state.isNearLatest = nearLatest(container);
  if (state.isNearLatest) {
    state.hasUnreadBelow = false;
  }
  syncJumpLatest();
}

function handleTranscriptClick(event) {
  const target = event.target.closest("[data-reader-key]");
  if (!target) {
    return;
  }
  event.preventDefault();
  const item = state.mobileReaderItems[target.dataset.readerKey];
  if (!item) {
    return;
  }
  state.readerItem = item;
  renderReaderSheet();
  setPanel(dom.readerPanel, true);
}

async function bootstrap() {
  state.accessToken = localStorage.getItem(storageKey()) || "";
  loadWallItems();
  state.ui.lang = loadPreference("lang", "zh-CN");
  state.ui.theme = loadPreference("theme", "dark");
  applyUiChrome();
  setPanel(dom.libraryPanel, false);
  setPanel(dom.composePanel, false);
  setPanel(dom.settingsPanel, false);
  setBodyState();
  renderStatus();
  await refreshHealth();
  if (state.accessToken) {
    try {
      await afterPair();
    } catch (error) {
      clearToken();
      setBodyState();
      dom.pairStatus.textContent = t("sessionExpired");
      renderStatus();
    }
  }
}

dom.pairButton.addEventListener("click", () => {
  handlePair().catch((error) => {
    dom.pairStatus.textContent = error.message || t("routeError");
  });
});
dom.pairCode.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    handlePair().catch(() => {});
  }
});
dom.openLibrary.addEventListener("click", () => {
  const nextOpen = dom.libraryPanel.dataset.open !== "true";
  setPanel(dom.readerPanel, false);
  setPanel(dom.viewActionsPanel, false);
  setPanel(dom.libraryPanel, nextOpen);
  if (!nextOpen) {
    return;
  }
  if ((!state.threadsLoaded && !state.threadsLoading) || state.threadsError) {
    loadThreads({ retries: 2 }).catch(console.error);
  }
  if ((!state.sessionsLoaded && !state.sessionsLoading) || state.sessionsError) {
    refreshSessions({ retries: 2 }).catch(console.error);
  }
});
dom.openCompose.addEventListener("click", () => {
  setPanel(dom.readerPanel, false);
  setPanel(dom.viewActionsPanel, false);
  setPanel(dom.composePanel, true);
});
dom.openWall.addEventListener("click", () => {
  openWallView();
});
dom.libraryCompose.addEventListener("click", () => {
  setPanel(dom.readerPanel, false);
  setPanel(dom.viewActionsPanel, false);
  setPanel(dom.composePanel, true);
});
dom.openSettings.addEventListener("click", () => {
  setPanel(dom.readerPanel, false);
  setPanel(dom.viewActionsPanel, false);
  setPanel(dom.settingsPanel, true);
});
dom.langToggle.addEventListener("click", () => {
  state.ui.lang = state.ui.lang === "zh-CN" ? "en" : "zh-CN";
  savePreference("lang", state.ui.lang);
  renderMainView();
});
dom.themeToggle.addEventListener("click", () => {
  state.ui.theme = state.ui.theme === "dark" ? "light" : "dark";
  savePreference("theme", state.ui.theme);
  renderMainView();
});
dom.overlay.addEventListener("click", () => {
  state.readerItem = null;
  setPanel(dom.libraryPanel, false);
  setPanel(dom.composePanel, false);
  setPanel(dom.settingsPanel, false);
  setPanel(dom.viewActionsPanel, false);
  setPanel(dom.readerPanel, false);
  setPanel(dom.desktopApprovalPanel, false);
});
dom.closeCompose.addEventListener("click", () => setPanel(dom.composePanel, false));
dom.closeSettings.addEventListener("click", () => setPanel(dom.settingsPanel, false));
dom.closeViewActions.addEventListener("click", () => setPanel(dom.viewActionsPanel, false));
dom.closeReader.addEventListener("click", () => {
  state.readerItem = null;
  setPanel(dom.readerPanel, false);
});
dom.closeDesktopApproval.addEventListener("click", () => setPanel(dom.desktopApprovalPanel, false));
dom.createSession.addEventListener("click", () => handleCreateSession().catch(console.error));
bindPlanLongPress(dom.createSession, "create");
dom.refreshAll.addEventListener("click", () => {
  Promise.all([refreshHealth(), refreshActiveSession(), refreshSessions(), loadThreads()])
    .then(async () => {
      if (state.currentThreadId) {
        state.currentThread = await client.getThread(state.currentThreadId);
      }
      renderMainView();
    })
    .catch(console.error);
});
if (dom.followActive) {
  dom.followActive.addEventListener("click", async () => {
    state.autoFollow = !state.autoFollow;
    renderStatus();
    if (state.autoFollow && state.activeSession.activeSessionId) {
      await openSession(state.activeSession.activeSessionId, { announce: false, localOnly: true });
    }
  });
}
dom.cancelSession.addEventListener("click", () => openCurrentViewActions());
dom.resumeThread.addEventListener("click", () => openCurrentViewActions());
dom.viewActionsPrimary.addEventListener("click", () => handleViewActionsPrimary().catch(console.error));
dom.composer.addEventListener("submit", (event) => handleFollowupSubmit(event).catch(console.error));
bindPlanLongPress(dom.sendFollowup, "send");
dom.attachImage?.addEventListener("click", () => dom.imageInput?.click());
dom.imageInput?.addEventListener("change", (event) => {
  addImageFiles(event.target.files).catch(console.error);
  event.target.value = "";
});
dom.composer.addEventListener("paste", (event) => {
  const files = Array.from(event.clipboardData?.files || []).filter((file) => file.type.startsWith("image/"));
  if (files.length) {
    addImageFiles(files).catch(console.error);
  }
});
dom.attachmentStrip?.addEventListener("click", (event) => {
  const target = event.target.closest("[data-remove-attachment]");
  if (target) {
    removePendingAttachment(target.dataset.removeAttachment);
  }
});
dom.resumeThreadInline.addEventListener("click", () => handleResumeThread().catch(console.error));
dom.followupInput.addEventListener("input", () => {
  window.requestAnimationFrame(updateFloatingLayout);
});
dom.liveList.addEventListener("click", handleNavClick);
dom.recentList.addEventListener("click", handleNavClick);
dom.historyList.addEventListener("click", handleNavClick);
dom.historyFold.addEventListener("toggle", () => {
  state.historyOpen = dom.historyFold.open;
});
dom.jumpLatest.addEventListener("click", () => scrollCurrentToLatest({ smooth: true }));
dom.conversationLog.addEventListener("scroll", handleConversationScroll);
dom.threadLog.addEventListener("scroll", handleConversationScroll);
dom.conversationLog.addEventListener("click", handleTranscriptClick);
dom.threadLog.addEventListener("click", handleTranscriptClick);
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-attachment-preview]");
  if (!target) {
    return;
  }
  const url = target.dataset.attachmentPreview;
  if (url) {
    window.open(url, "_blank", "noopener");
  }
});
dom.wallView.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-wall-form='composer']");
  if (!form) {
    return;
  }
  event.preventDefault();
  const payload = new FormData(form);
  const title = String(payload.get("title") || "").trim();
  const content = String(payload.get("content") || "").trim();
  if (!title && !content) {
    return;
  }
  const now = new Date().toISOString();
  const existing = wallDraftItem();
  const nextItem = {
    id: existing?.id || crypto.randomUUID(),
    title: title || "未命名灵感",
    content,
    tags: normalizeWallTags(payload.get("tags")),
    color: String(payload.get("color") || "#f4b183"),
    favorite: Boolean(existing?.favorite),
    createdAt: existing?.createdAt || now,
    updatedAt: now,
  };
  state.wall.items = sortedWallItems([
    ...state.wall.items.filter((item) => item.id !== nextItem.id),
    nextItem,
  ]);
  saveWallItems();
  resetWallComposer();
  renderMainView();
});
dom.wallView.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
    return;
  }
  if (target.name === "wall-query") {
    state.wall.query = target.value;
    renderMainView();
    return;
  }
  if (target.name === "wall-filter-tag") {
    state.wall.tag = target.value || "all";
    renderMainView();
    return;
  }
  if (target.name === "wall-favorites") {
    state.wall.favoritesOnly = target.checked;
    renderMainView();
  }
});
dom.wallView.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-wall-action]");
  if (!actionButton) {
    return;
  }
  const action = actionButton.dataset.wallAction;
  const wallId = actionButton.dataset.wallId || "";
  const item = state.wall.items.find((entry) => entry.id === wallId) || null;
  if (action === "reset-composer") {
    resetWallComposer();
    renderMainView();
    return;
  }
  if (action === "seed-sample") {
    const now = new Date().toISOString();
    const seeds = [
      {
        id: crypto.randomUUID(),
        title: "把实时状态做成会呼吸的界面",
        content: "不是一堆冷数据，而是把同步状态、线程状态、审批状态做成有节奏的视觉层次。",
        tags: ["界面", "状态"],
        color: "#7dc4ff",
        favorite: true,
        createdAt: now,
        updatedAt: now,
      },
      {
        id: crypto.randomUUID(),
        title: "移动端像贴纸墙一样组织任务",
        content: "把会话、线程、审批、灵感都做成可筛选卡片，让手机端不只是遥控器，而像工作台。",
        tags: ["产品", "移动端"],
        color: "#f29eb0",
        favorite: false,
        createdAt: now,
        updatedAt: now,
      },
    ];
    state.wall.items = sortedWallItems([...seeds, ...state.wall.items]);
    saveWallItems();
    renderMainView();
    return;
  }
  if (action === "filter-tag") {
    state.wall.tag = actionButton.dataset.wallTag || "all";
    renderMainView();
    return;
  }
  if (!item) {
    return;
  }
  if (action === "toggle-favorite") {
    item.favorite = !item.favorite;
    item.updatedAt = new Date().toISOString();
  } else if (action === "edit") {
    state.wall.editingId = item.id;
  } else if (action === "duplicate") {
    const now = new Date().toISOString();
    state.wall.items = [
      {
        ...item,
        id: crypto.randomUUID(),
        title: `${item.title} · 副本`,
        createdAt: now,
        updatedAt: now,
      },
      ...state.wall.items,
    ];
  } else if (action === "delete") {
    if (!window.confirm(`删除这张卡片？\n\n${item.title}`)) {
      return;
    }
    state.wall.items = state.wall.items.filter((entry) => entry.id !== item.id);
    if (state.wall.editingId === item.id) {
      resetWallComposer();
    }
  }
  saveWallItems();
  renderMainView();
});
dom.approvalStrip.addEventListener("click", (event) => {
  const button = event.target.closest("[data-approval-id][data-action]");
  if (!button) {
    return;
  }
  handleApproval(button.dataset.action, button.dataset.approvalId).catch(console.error);
});
dom.desktopApprovalStrip.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action='open-desktop-approval']");
  if (!button || button.disabled) {
    return;
  }
  openDesktopApprovalPanel().catch(console.error);
});
dom.desktopPreviewStage.addEventListener("pointerdown", (event) => {
  if (dom.desktopApprovalPanel.dataset.open !== "true") {
    return;
  }
  const ratios = desktopPreviewRatiosFromEvent(event);
  if (!ratios) {
    return;
  }
  state.desktopPreview.pointerActive = true;
  dom.desktopPreviewStage.setPointerCapture?.(event.pointerId);
  sendDesktopPreviewCommand({
    type: "pointer.down",
    id: crypto.randomUUID(),
    xRatio: ratios.xRatio,
    yRatio: ratios.yRatio,
  }).catch(console.error);
});
dom.desktopPreviewStage.addEventListener("pointermove", (event) => {
  if (!state.desktopPreview.pointerActive) {
    return;
  }
  const ratios = desktopPreviewRatiosFromEvent(event);
  if (!ratios) {
    return;
  }
  sendDesktopPreviewCommand({
    type: "pointer.move",
    id: crypto.randomUUID(),
    xRatio: ratios.xRatio,
    yRatio: ratios.yRatio,
  }).catch(console.error);
});
dom.desktopPreviewStage.addEventListener("pointerup", (event) => {
  if (!state.desktopPreview.pointerActive) {
    return;
  }
  const ratios = desktopPreviewRatiosFromEvent(event);
  state.desktopPreview.pointerActive = false;
  dom.desktopPreviewStage.releasePointerCapture?.(event.pointerId);
  if (!ratios) {
    return;
  }
  sendDesktopPreviewCommand({
    type: "pointer.up",
    id: crypto.randomUUID(),
    xRatio: ratios.xRatio,
    yRatio: ratios.yRatio,
  }).catch(console.error);
});
dom.desktopPreviewStage.addEventListener("pointercancel", (event) => {
  if (!state.desktopPreview.pointerActive) {
    return;
  }
  const ratios = desktopPreviewRatiosFromEvent(event) || { xRatio: 0.5, yRatio: 0.5 };
  state.desktopPreview.pointerActive = false;
  dom.desktopPreviewStage.releasePointerCapture?.(event.pointerId);
  sendDesktopPreviewCommand({
    type: "pointer.up",
    id: crypto.randomUUID(),
    xRatio: ratios.xRatio,
    yRatio: ratios.yRatio,
  }).catch(console.error);
});
dom.desktopPreviewStage.addEventListener("wheel", (event) => {
  if (dom.desktopApprovalPanel.dataset.open !== "true") {
    return;
  }
  const ratios = desktopPreviewRatiosFromEvent(event) || { xRatio: 0.5, yRatio: 0.5 };
  event.preventDefault();
  sendDesktopPreviewCommand({
    type: "gesture.scroll",
    id: crypto.randomUUID(),
    dy: event.deltaY,
    xRatio: ratios.xRatio,
    yRatio: ratios.yRatio,
  }).catch(console.error);
}, { passive: false });
window.addEventListener("resize", () => {
  if (isDesktop()) {
    setPanel(dom.libraryPanel, false);
  }
  renderStatus();
  updateFloatingLayout();
  handleConversationScroll();
});

if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", () => {
    window.requestAnimationFrame(updateFloatingLayout);
  });
}

bootstrap().catch(console.error);
