// Codesk Windows — screen components
// Uses C, MONO, SANS, BrandIcon, PulseDot (injected from host)

// ─── Sidebar ───────────────────────────────────────────────
function Sidebar({ active, setActive, accent }) {
  const items = [
    { id: 'library', label: '会话', badge: 2, icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 4h12v9H4l-2 2V4z" stroke="currentColor" strokeWidth="1.3"/></svg>
    )},
    { id: 'compose', label: '新建任务', icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>
    )},
    { id: 'workspaces', label: '工作区', icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.3"/><rect x="9" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.3"/><rect x="2" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.3"/><rect x="9" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.3"/></svg>
    )},
    { id: 'pair', label: '配对', icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.3"/><rect x="9" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.3"/><rect x="2" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.3"/><path d="M10 10h1M13 10v1M10 13h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>
    )},
    { id: 'settings', label: '设置', icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.5 1.5M11.5 11.5L13 13M3 13l1.5-1.5M11.5 4.5L13 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>
    )},
  ];

  return (
    <div style={{
      width: 208, flexShrink: 0, background: 'rgba(255,255,255,0.015)',
      borderRight: `1px solid ${C.line}`, display: 'flex', flexDirection: 'column',
      padding: '12px 0',
    }}>
      {/* status block */}
      <div style={{ padding: '4px 14px 14px', borderBottom: `1px solid ${C.line}`, marginBottom: 8 }}>
        <div style={{ fontSize: 10.5, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>本机</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <StatusRow label="Bridge" state="ok" detail="127.0.0.1:7788" />
          <StatusRow label="Relay" state="ok" detail="wss://…codesk.io" />
          <StatusRow label="Agent" state="ok" detail="v0.4.2" />
        </div>
      </div>

      {items.map(it => {
        const isActive = active === it.id;
        return (
          <button key={it.id} onClick={() => setActive(it.id)} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            height: 34, padding: '0 14px', margin: '0 8px',
            background: isActive ? 'rgba(255,255,255,0.05)' : 'transparent',
            border: 'none', borderRadius: 6, cursor: 'pointer', position: 'relative',
            color: isActive ? C.text : C.textSoft,
            fontFamily: 'inherit', fontSize: 13, fontWeight: isActive ? 500 : 400,
            transition: 'background 0.1s',
            textAlign: 'left',
          }}
          onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.025)'; }}
          onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}>
            {isActive && <div style={{ position: 'absolute', left: 0, top: 8, bottom: 8, width: 2, background: accent, borderRadius: 1 }}/>}
            <span style={{ opacity: isActive ? 1 : 0.55, display: 'flex' }}>{it.icon}</span>
            <span style={{ flex: 1 }}>{it.label}</span>
            {it.badge && (
              <span style={{
                minWidth: 18, height: 18, padding: '0 5px', borderRadius: 9,
                background: accent, color: '#fff', fontSize: 10, fontWeight: 600,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>{it.badge}</span>
            )}
          </button>
        );
      })}

      <div style={{ flex: 1 }} />

      {/* account pill */}
      <div style={{ padding: '12px 14px', borderTop: `1px solid ${C.line}`, marginTop: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: `linear-gradient(135deg, ${accent}, #5B21B6)`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 600, color: '#fff' }}>ZS</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, color: C.text, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>zhang.sh</div>
            <div style={{ fontSize: 10.5, color: C.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>DESKTOP-7H2K</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, state, detail }) {
  const color = state === 'ok' ? C.success : state === 'warn' ? C.warn : C.danger;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <PulseDot color={color} />
      <span style={{ fontSize: 11.5, color: C.textSoft, fontWeight: 500 }}>{label}</span>
      <span style={{ marginLeft: 'auto', fontFamily: MONO, fontSize: 10, color: C.muted, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110 }}>{detail}</span>
    </div>
  );
}

// ─── Library Screen ───────────────────────────────────────
function LibraryScreen({ onOpen, onNew, accent }) {
  const [filter, setFilter] = React.useState('all');
  const sessions = [
    { id: 's1', title: '重构 agent 调度队列的超时处理', workspace: 'bridge', state: 'awaiting', updated: '刚刚', turns: 14, branch: 'main', pendingApproval: true },
    { id: 's2', title: '修复 MCP relay 心跳丢失重连', workspace: 'mcp-relay', state: 'running', updated: '2 分钟前', turns: 8, branch: 'fix/heartbeat', progress: '编辑 heartbeat.rs' },
    { id: 's3', title: '给 Windows 客户端增加 acrylic 背景', workspace: 'clients/windows', state: 'idle', updated: '1 小时前', turns: 22, branch: 'ui/acrylic' },
    { id: 's4', title: '把 Android 侧的消息气泡做成自适应宽度', workspace: 'android_app', state: 'done', updated: '今天 10:32', turns: 31, branch: 'ui/bubble' },
    { id: 's5', title: '探索 SQLite → DuckDB 迁移路径', workspace: 'bridge', state: 'idle', updated: '昨天', turns: 47, branch: 'main' },
  ];
  const filtered = filter === 'all' ? sessions : sessions.filter(s => s.state === filter);

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      {/* header */}
      <div style={{ padding: '20px 28px 14px', display: 'flex', alignItems: 'flex-end', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>会话线程</div>
          <div style={{ fontSize: 22, fontWeight: 600, color: C.text, letterSpacing: '-0.01em' }}>会话</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <SearchBox />
          <button onClick={onNew} style={{
            height: 32, paddingInline: 14, background: accent, border: 'none', borderRadius: 6,
            color: '#fff', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'inherit',
          }}>
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M5.5 1v9M1 5.5h9" stroke="white" strokeWidth="1.6" strokeLinecap="round"/></svg>
            新建任务
          </button>
        </div>
      </div>

      {/* filter tabs */}
      <div style={{ padding: '0 28px', borderBottom: `1px solid ${C.line}`, display: 'flex', gap: 4, alignItems: 'center' }}>
        {[
          ['all', '全部', sessions.length],
          ['awaiting', '待审批', sessions.filter(s => s.state === 'awaiting').length],
          ['running', '运行中', sessions.filter(s => s.state === 'running').length],
          ['idle', '空闲', sessions.filter(s => s.state === 'idle').length],
          ['done', '已完成', sessions.filter(s => s.state === 'done').length],
        ].map(([id, label, count]) => (
          <button key={id} onClick={() => setFilter(id)} style={{
            height: 34, paddingInline: 14, background: 'transparent', border: 'none',
            color: filter === id ? C.text : C.textSoft,
            fontSize: 12.5, fontWeight: filter === id ? 500 : 400,
            cursor: 'pointer', position: 'relative', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            {label}
            <span style={{ fontSize: 10.5, color: C.muted, fontFamily: MONO }}>{count}</span>
            {filter === id && <div style={{ position: 'absolute', left: 10, right: 10, bottom: -1, height: 2, background: accent }}/>}
          </button>
        ))}
        <div style={{ flex: 1 }}/>
        <div style={{ fontSize: 11, color: C.muted, fontFamily: MONO }}>{filtered.length} threads</div>
      </div>

      {/* list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {filtered.map(s => <SessionRow key={s.id} session={s} onOpen={onOpen} accent={accent} />)}
      </div>
    </div>
  );
}

function SearchBox() {
  return (
    <div style={{
      width: 260, height: 32, borderRadius: 6, background: C.panel, border: `1px solid ${C.line}`,
      display: 'flex', alignItems: 'center', gap: 8, padding: '0 10px',
    }}>
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="5" cy="5" r="3.5" stroke={C.muted} strokeWidth="1.3"/><path d="M8 8l3 3" stroke={C.muted} strokeWidth="1.3" strokeLinecap="round"/></svg>
      <input placeholder="搜索线程 / 仓库 / 分支…" style={{
        flex: 1, background: 'transparent', border: 'none', outline: 'none',
        color: C.text, fontSize: 12, fontFamily: 'inherit',
      }}/>
      <kbd style={{ fontFamily: MONO, fontSize: 10, color: C.muted, background: 'rgba(255,255,255,0.04)', padding: '1px 5px', borderRadius: 3, border: `1px solid ${C.line}` }}>Ctrl K</kbd>
    </div>
  );
}

function StateBadge({ state }) {
  const map = {
    awaiting: { label: '待审批', color: C.warn, bg: 'rgba(233,226,191,0.08)' },
    running:  { label: '运行中', color: C.success, bg: 'rgba(134,239,172,0.08)' },
    idle:     { label: '空闲',   color: C.textSoft, bg: 'rgba(255,255,255,0.04)' },
    done:     { label: '已完成', color: C.muted, bg: 'rgba(255,255,255,0.03)' },
  };
  const m = map[state];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      height: 20, paddingInline: 7, borderRadius: 4,
      background: m.bg, color: m.color,
      fontSize: 10.5, fontWeight: 500, letterSpacing: '0.02em',
    }}>
      {state === 'running' && <PulseDot color={m.color}/>}
      {state === 'awaiting' && <div style={{ width: 5, height: 5, borderRadius: '50%', background: m.color }}/>}
      {m.label}
    </span>
  );
}

function SessionRow({ session, onOpen, accent }) {
  const [hover, setHover] = React.useState(false);
  return (
    <div
      onClick={() => onOpen(session)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: '14px 28px', borderBottom: `1px solid ${C.line}`,
        background: hover ? 'rgba(255,255,255,0.02)' : 'transparent',
        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 20,
        transition: 'background 0.1s',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 5 }}>
          <StateBadge state={session.state}/>
          <span style={{ fontFamily: MONO, fontSize: 11, color: C.muted }}>{session.workspace}</span>
          <span style={{ fontSize: 11, color: C.muted }}>•</span>
          <span style={{ fontFamily: MONO, fontSize: 11, color: C.muted }}>{session.branch}</span>
          {session.pendingApproval && (
            <span style={{ marginLeft: 6, display: 'inline-flex', alignItems: 'center', gap: 4, color: C.warn, fontSize: 11 }}>
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M5 1l4 7H1l4-7z" stroke={C.warn} strokeWidth="1.2"/></svg>
              1 个审批请求
            </span>
          )}
        </div>
        <div style={{ fontSize: 14, color: C.text, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', letterSpacing: '-0.005em' }}>
          {session.title}
        </div>
        {session.progress && (
          <div style={{ fontFamily: MONO, fontSize: 11, color: C.muted, marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: accent }}>▸</span>{session.progress}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, minWidth: 90 }}>
        <div style={{ fontSize: 11, color: C.textSoft }}>{session.updated}</div>
        <div style={{ fontFamily: MONO, fontSize: 10.5, color: C.muted, marginTop: 3 }}>{session.turns} turns</div>
      </div>
    </div>
  );
}

// ─── Session Screen ───────────────────────────────────────
function SessionScreen({ session, onBack, accent }) {
  const [approved, setApproved] = React.useState(false);
  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      {/* subheader */}
      <div style={{ padding: '14px 28px', borderBottom: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', gap: 14 }}>
        <button onClick={onBack} style={{
          width: 28, height: 28, borderRadius: 5, background: 'transparent',
          border: `1px solid ${C.line}`, color: C.textSoft, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M6.5 1L2 5l4.5 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {session?.title || '重构 agent 调度队列的超时处理'}
          </div>
          <div style={{ fontFamily: MONO, fontSize: 11, color: C.muted, marginTop: 2 }}>
            bridge · <span style={{ color: C.textSoft }}>main</span> · session <span style={{ color: C.textSoft }}>a3f8c</span>
          </div>
        </div>
        <StateBadge state={approved ? 'running' : 'awaiting'}/>
        <button style={{ height: 28, paddingInline: 10, borderRadius: 5, background: 'transparent', border: `1px solid ${C.line}`, color: C.textSoft, fontSize: 11.5, fontFamily: 'inherit', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M4 2L7 5.5 4 9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>
          在终端打开
        </button>
      </div>

      {/* conversation + inspector split */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        {/* conversation */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflow: 'auto', padding: '22px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>
            <Msg role="user" text="现在的 agent 队列里，超时的任务会一直挂在队列头部，后面的请求也被阻塞。帮我排查一下，分析出问题后再改。"/>
            <Msg role="assistant" text="我来看一下 queue.rs 的超时处理路径。"/>
            <ToolCall tool="read_file" path="bridge/src/queue.rs" lines="lines 1–180" done/>
            <ToolCall tool="grep" path='"timeout|await"' lines="in bridge/" done/>
            <Msg role="assistant" text={
              <>
                找到问题了：<Code>process_next()</Code> 在 await 任务时没有套 <Code>tokio::select!</Code> 的超时分支，所以 <Code>queue_timeout_ms</Code> 只在调度入口生效。我打算加一个 <Code>drive_with_timeout</Code> 包装，并在超时时把任务从队头移出重入尾部。
              </>
            }/>
            <ApprovalCard approved={approved} onApprove={() => setApproved(true)} accent={accent}/>
            {approved && (
              <>
                <ToolCall tool="apply_patch" path="bridge/src/queue.rs" lines="+28 −6" done/>
                <ToolCall tool="cargo check" path="-p codesk-bridge" running/>
              </>
            )}
          </div>

          {/* composer */}
          <div style={{ padding: '12px 20px 20px', borderTop: `1px solid ${C.line}`, background: 'rgba(0,0,0,0.4)' }}>
            <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 8, padding: 10 }}>
              <textarea placeholder="继续对话…   Ctrl+↩ 发送" style={{
                width: '100%', background: 'transparent', border: 'none', outline: 'none',
                color: C.text, fontSize: 13, fontFamily: 'inherit', resize: 'none',
                minHeight: 38, lineHeight: 1.5,
              }}/>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                <IconBtn>
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M5 8l3-3m0 0L5 2m3 3H2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" transform="rotate(45 6.5 6.5)"/></svg>
                </IconBtn>
                <IconBtn>
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="2" y="2" width="9" height="9" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M4 6l1.5 1.5L9 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
                </IconBtn>
                <IconBtn>
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M3 6.5l3 3 5-5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>
                </IconBtn>
                <span style={{ fontSize: 11, color: C.muted, marginLeft: 6 }}>模型 <span style={{ color: C.textSoft }}>claude-sonnet</span></span>
                <div style={{ flex: 1 }}/>
                <button style={{ height: 28, paddingInline: 12, borderRadius: 5, background: accent, border: 'none', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 6 }}>
                  发送
                  <kbd style={{ fontFamily: MONO, fontSize: 9.5, opacity: 0.7 }}>Ctrl ↩</kbd>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* inspector */}
        <div style={{ width: 280, flexShrink: 0, borderLeft: `1px solid ${C.line}`, background: 'rgba(255,255,255,0.01)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '14px 18px', borderBottom: `1px solid ${C.line}` }}>
            <div style={{ fontSize: 10.5, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>工作区</div>
            <div style={{ fontFamily: MONO, fontSize: 11.5, color: C.textSoft, lineHeight: 1.7 }}>
              <div>~/code/codesk/bridge</div>
              <div style={{ color: C.muted }}>↳ branch <span style={{ color: C.text }}>main</span></div>
              <div style={{ color: C.muted }}>↳ head <span style={{ color: C.text }}>a3f8c · 42 ahead</span></div>
            </div>
          </div>
          <div style={{ padding: '14px 18px', borderBottom: `1px solid ${C.line}` }}>
            <div style={{ fontSize: 10.5, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>改动</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <DiffRow path="bridge/src/queue.rs" add={28} del={6}/>
              <DiffRow path="bridge/src/scheduler.rs" add={4} del={0}/>
              <DiffRow path="bridge/tests/queue.rs" add={18} del={0}/>
            </div>
          </div>
          <div style={{ padding: '14px 18px', flex: 1 }}>
            <div style={{ fontSize: 10.5, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>上下文</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <ContextChip label="bridge/src/queue.rs"/>
              <ContextChip label="bridge/src/scheduler.rs"/>
              <ContextChip label="design/queue-timeout.md"/>
              <button style={{ height: 26, border: `1px dashed ${C.line}`, borderRadius: 5, background: 'transparent', color: C.muted, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}>
                + 添加引用
              </button>
            </div>
          </div>
          <div style={{ padding: '14px 18px', borderTop: `1px solid ${C.line}`, display: 'flex', gap: 14, fontFamily: MONO, fontSize: 10.5, color: C.muted }}>
            <span>tok <span style={{ color: C.textSoft }}>14.2k</span></span>
            <span>in <span style={{ color: C.textSoft }}>$0.04</span></span>
            <span>out <span style={{ color: C.textSoft }}>$0.11</span></span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Msg({ role, text }) {
  const isUser = role === 'user';
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <div style={{
        width: 22, height: 22, borderRadius: 4, flexShrink: 0, marginTop: 1,
        background: isUser ? 'rgba(255,255,255,0.04)' : 'transparent',
        border: isUser ? `1px solid ${C.line}` : `1px solid ${C.accent}66`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 600, color: isUser ? C.textSoft : C.accent,
      }}>{isUser ? 'U' : 'A'}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 10.5, color: C.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
          {isUser ? '你' : 'Assistant'}
        </div>
        <div style={{ fontSize: 13.5, color: C.text, lineHeight: 1.65, textWrap: 'pretty' }}>{text}</div>
      </div>
    </div>
  );
}

function Code({ children }) {
  return <span style={{ fontFamily: MONO, fontSize: 12, background: 'rgba(255,255,255,0.05)', padding: '1px 5px', borderRadius: 3, color: C.text }}>{children}</span>;
}

function ToolCall({ tool, path, lines, running, done }) {
  return (
    <div style={{ marginLeft: 34, padding: '8px 12px', background: 'rgba(255,255,255,0.015)', border: `1px solid ${C.line}`, borderRadius: 6, display: 'flex', alignItems: 'center', gap: 10 }}>
      {running ? (
        <div style={{ width: 10, height: 10, borderRadius: '50%', border: `1.5px solid ${C.accent}`, borderTopColor: 'transparent', animation: 'spin 1s linear infinite' }}/>
      ) : done ? (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1.5 5.5l2.5 2.5L8.5 2" stroke={C.success} strokeWidth="1.5" strokeLinecap="round"/></svg>
      ) : null}
      <span style={{ fontFamily: MONO, fontSize: 11.5, color: C.accent }}>{tool}</span>
      <span style={{ fontFamily: MONO, fontSize: 11.5, color: C.textSoft, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{path}</span>
      <span style={{ fontFamily: MONO, fontSize: 10.5, color: C.muted, marginLeft: 'auto' }}>{lines}</span>
    </div>
  );
}

function ApprovalCard({ approved, onApprove, accent }) {
  if (approved) {
    return (
      <div style={{ marginLeft: 34, padding: '8px 12px', background: 'rgba(134,239,172,0.04)', border: `1px solid ${C.success}33`, borderRadius: 6, display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-6" stroke={C.success} strokeWidth="1.4" strokeLinecap="round"/></svg>
        <span style={{ color: C.text }}>已批准 · 本会话内同类操作自动放行</span>
        <button style={{ marginLeft: 'auto', height: 22, paddingInline: 8, background: 'transparent', border: `1px solid ${C.line}`, borderRadius: 4, color: C.muted, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}>撤销</button>
      </div>
    );
  }
  return (
    <div style={{ marginLeft: 34, border: `1px solid ${C.warn}33`, borderRadius: 8, overflow: 'hidden' }}>
      <div style={{ padding: '10px 14px', background: 'rgba(233,226,191,0.04)', borderBottom: `1px solid ${C.warn}22` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1l5 9H1l5-9z" stroke={C.warn} strokeWidth="1.3"/><path d="M6 4.5v2.5M6 8.5v.5" stroke={C.warn} strokeWidth="1.3" strokeLinecap="round"/></svg>
          <span style={{ fontSize: 12.5, fontWeight: 500, color: C.text }}>请求审批 · 写入 3 个文件</span>
          <span style={{ marginLeft: 'auto', fontFamily: MONO, fontSize: 10.5, color: C.muted }}>+50  −6</span>
        </div>
      </div>
      <div style={{ padding: '4px 0', background: C.panel }}>
        {[
          ['bridge/src/queue.rs', '+28 −6'],
          ['bridge/src/scheduler.rs', '+4 −0'],
          ['bridge/tests/queue.rs', '+18 −0'],
        ].map(([p, d]) => (
          <div key={p} style={{ padding: '5px 14px', display: 'flex', alignItems: 'center', gap: 10, fontSize: 11.5 }}>
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 1h4l3 3v5H2V1z" stroke={C.muted} strokeWidth="1"/></svg>
            <span style={{ fontFamily: MONO, color: C.textSoft }}>{p}</span>
            <span style={{ marginLeft: 'auto', fontFamily: MONO, color: C.muted, fontSize: 10.5 }}>{d}</span>
          </div>
        ))}
      </div>
      <div style={{ padding: '10px 14px', background: C.panel, borderTop: `1px solid ${C.line}`, display: 'flex', gap: 8 }}>
        <button onClick={onApprove} style={{ height: 30, paddingInline: 14, background: accent, border: 'none', borderRadius: 5, color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>批准</button>
        <button style={{ height: 30, paddingInline: 12, background: 'transparent', border: `1px solid ${C.line}`, borderRadius: 5, color: C.textSoft, fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>本会话始终批准</button>
        <button style={{ height: 30, paddingInline: 12, background: 'transparent', border: `1px solid ${C.line}`, borderRadius: 5, color: C.textSoft, fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>查看 diff</button>
        <div style={{ flex: 1 }}/>
        <button style={{ height: 30, paddingInline: 12, background: 'transparent', border: `1px solid ${C.danger}44`, borderRadius: 5, color: C.danger, fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>拒绝</button>
      </div>
    </div>
  );
}

function DiffRow({ path, add, del }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, fontFamily: MONO }}>
      <span style={{ flex: 1, color: C.textSoft, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{path}</span>
      {add > 0 && <span style={{ color: C.success }}>+{add}</span>}
      {del > 0 && <span style={{ color: C.danger }}>−{del}</span>}
    </div>
  );
}

function ContextChip({ label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, height: 24, paddingInline: 8, background: 'rgba(255,255,255,0.025)', border: `1px solid ${C.line}`, borderRadius: 4 }}>
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 1h4l3 3v5H2V1z" stroke={C.muted} strokeWidth="1"/></svg>
      <span style={{ fontFamily: MONO, fontSize: 11, color: C.textSoft, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
    </div>
  );
}

function IconBtn({ children }) {
  return (
    <button style={{
      width: 26, height: 26, borderRadius: 4, background: 'transparent',
      border: `1px solid ${C.line}`, color: C.muted, cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>{children}</button>
  );
}

// ─── Pair Screen ───────────────────────────────────────────
function PairScreen({ accent }) {
  // simple QR-like grid
  const cells = React.useMemo(() => {
    const arr = [];
    for (let i = 0; i < 21 * 21; i++) arr.push(Math.random() > 0.5);
    // hardcode 3 finder patterns
    const finder = (r0, c0) => {
      for (let r = 0; r < 7; r++) for (let c = 0; c < 7; c++) {
        const on = r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4);
        arr[(r0 + r) * 21 + (c0 + c)] = on;
      }
    };
    finder(0, 0); finder(0, 14); finder(14, 0);
    return arr;
  }, []);

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex' }}>
      <div style={{ flex: 1, padding: '40px 56px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontSize: 11, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase' }}>配对手机</div>
        <div style={{ fontSize: 26, fontWeight: 600, color: C.text, marginTop: 6, letterSpacing: '-0.015em' }}>让这台电脑接收来自手机的任务</div>
        <div style={{ fontSize: 13.5, color: C.textSoft, marginTop: 10, lineHeight: 1.65, maxWidth: 480 }}>
          在手机 Codesk 应用里点 <b style={{ color: C.text }}>扫码配对</b>，对准右侧二维码即可。配对后手机可向本机发送任务、审批工具调用、接管 Codex Desktop。
        </div>

        {/* steps */}
        <div style={{ marginTop: 32, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <PairStep n={1} title="Bridge 已就绪" detail="127.0.0.1:7788 · 本机进程" state="ok"/>
          <PairStep n={2} title="Relay 通道已连接" detail="wss://relay-hk1.codesk.io · 12 ms" state="ok"/>
          <PairStep n={3} title="Codex Desktop" detail="v0.9.1 · 保持此窗口在前台以接收任务" state="ok"/>
          <PairStep n={4} title="等待手机扫码" detail="配对码 6 分钟内有效" state="wait"/>
        </div>

        <div style={{ flex: 1 }}/>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button style={{ height: 32, paddingInline: 14, borderRadius: 5, background: 'transparent', border: `1px solid ${C.line}`, color: C.textSoft, fontSize: 12.5, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M10 3a4 4 0 11-4-2M10 3V1M10 3H8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>
            刷新二维码
          </button>
          <button style={{ height: 32, paddingInline: 14, borderRadius: 5, background: 'transparent', border: `1px solid ${C.line}`, color: C.textSoft, fontSize: 12.5, cursor: 'pointer', fontFamily: 'inherit' }}>复制配对链接</button>
          <div style={{ flex: 1 }}/>
          <span style={{ fontFamily: MONO, fontSize: 11, color: C.muted }}>自动在托盘运行 · 开机启动已开启</span>
        </div>
      </div>

      <div style={{ width: 420, flexShrink: 0, borderLeft: `1px solid ${C.line}`, background: 'rgba(255,255,255,0.01)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 36 }}>
        {/* QR card */}
        <div style={{ background: '#FAFAFA', padding: 22, borderRadius: 10, display: 'grid', gridTemplateColumns: 'repeat(21, 1fr)', gap: 0, width: 240, height: 240, position: 'relative' }}>
          {cells.map((on, i) => (
            <div key={i} style={{ background: on ? '#0A0A0A' : 'transparent', aspectRatio: '1/1' }}/>
          ))}
          {/* center logo */}
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 52, height: 52, borderRadius: 10, background: '#0A0A0A', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <BrandIcon size={34}/>
            </div>
          </div>
        </div>
        <div style={{ marginTop: 22, fontFamily: MONO, fontSize: 15, color: C.text, letterSpacing: '0.14em', fontWeight: 500 }}>CDS-8K4Q-WN7R</div>
        <div style={{ marginTop: 6, fontSize: 11.5, color: C.muted }}>或手动输入此配对码 · <span style={{ color: accent }}>05:42</span> 后刷新</div>
      </div>
    </div>
  );
}

function PairStep({ n, title, detail, state }) {
  const color = state === 'ok' ? C.success : state === 'wait' ? C.accent : C.warn;
  return (
    <div style={{ display: 'flex', gap: 14, padding: '10px 0', borderBottom: `1px solid ${C.line}` }}>
      <div style={{ width: 22, height: 22, borderRadius: '50%', border: `1px solid ${color}66`, background: `${color}14`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
        {state === 'ok' ? (
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1.5 5l2.5 2.5L8.5 2" stroke={color} strokeWidth="1.6" strokeLinecap="round"/></svg>
        ) : state === 'wait' ? (
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, animation: 'pulse 1.6s infinite' }}/>
        ) : (
          <span style={{ fontSize: 10, color, fontWeight: 600 }}>{n}</span>
        )}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: C.text, fontWeight: 500 }}>{title}</div>
        <div style={{ fontFamily: MONO, fontSize: 11, color: C.muted, marginTop: 2 }}>{detail}</div>
      </div>
    </div>
  );
}

// ─── Compose Screen ───────────────────────────────────────
function ComposeScreen({ onCancel, accent }) {
  const [workspace, setWorkspace] = React.useState('bridge');
  const [prompt, setPrompt] = React.useState('');
  const workspaces = [
    { id: 'bridge', path: '~/code/codesk/bridge', branch: 'main', dirty: 0 },
    { id: 'mcp-relay', path: '~/code/codesk/mcp-relay', branch: 'fix/heartbeat', dirty: 3 },
    { id: 'android_app', path: '~/code/codesk/android_app', branch: 'ui/bubble', dirty: 1 },
    { id: 'clients/windows', path: '~/code/codesk/clients/windows', branch: 'ui/acrylic', dirty: 0 },
  ];
  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '20px 28px 14px', borderBottom: `1px solid ${C.line}`, display: 'flex', alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>新建任务</div>
          <div style={{ fontSize: 22, fontWeight: 600, color: C.text, letterSpacing: '-0.01em' }}>告诉 Codex 做什么</div>
        </div>
        <button onClick={onCancel} style={{ height: 30, paddingInline: 12, borderRadius: 5, background: 'transparent', border: `1px solid ${C.line}`, color: C.textSoft, fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>取消</button>
        <button disabled={!prompt.trim()} style={{ marginLeft: 8, height: 30, paddingInline: 16, borderRadius: 5, background: prompt.trim() ? accent : 'rgba(255,255,255,0.04)', border: 'none', color: prompt.trim() ? '#fff' : C.muted, fontSize: 12, fontWeight: 600, cursor: prompt.trim() ? 'pointer' : 'not-allowed', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 6 }}>
          启动任务
          <kbd style={{ fontFamily: MONO, fontSize: 9.5, opacity: 0.7 }}>Ctrl ↩</kbd>
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '22px 28px', display: 'flex', flexDirection: 'column', gap: 22, maxWidth: 900 }}>
        {/* workspace */}
        <Section label="工作区">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {workspaces.map(w => (
              <button key={w.id} onClick={() => setWorkspace(w.id)} style={{
                padding: '12px 14px', background: workspace === w.id ? 'rgba(139,92,246,0.08)' : C.panel,
                border: `1px solid ${workspace === w.id ? accent + '66' : C.line}`, borderRadius: 6,
                textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit',
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1 3l2-2h3l1 1h4v7H1V3z" stroke={workspace === w.id ? accent : C.textSoft} strokeWidth="1.2"/></svg>
                  <span style={{ fontSize: 13, color: C.text, fontWeight: 500 }}>{w.id}</span>
                  {w.dirty > 0 && <span style={{ fontSize: 10.5, color: C.warn, marginLeft: 'auto' }}>● {w.dirty} uncommitted</span>}
                </div>
                <div style={{ fontFamily: MONO, fontSize: 10.5, color: C.muted }}>{w.path} · <span style={{ color: C.textSoft }}>{w.branch}</span></div>
              </button>
            ))}
          </div>
        </Section>

        {/* prompt */}
        <Section label="任务描述">
          <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 6, padding: 14 }}>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
              placeholder="例如：在 bridge 的 queue.rs 里加入一个 drive_with_timeout 包装；超时的任务应该被移到队尾，而不是阻塞队列。写测试。"
              style={{
                width: '100%', minHeight: 120, background: 'transparent', border: 'none', outline: 'none',
                color: C.text, fontSize: 14, fontFamily: 'inherit', resize: 'vertical', lineHeight: 1.6,
              }}/>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, paddingTop: 8, borderTop: `1px solid ${C.line}` }}>
              <IconBtn>
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M2 2h9v9H2V2z" stroke="currentColor" strokeWidth="1.2"/><path d="M4 7l2 2 3-4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
              </IconBtn>
              <IconBtn>
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M4 6V4a2.5 2.5 0 115 0v2M3 6h7v6H3V6z" stroke="currentColor" strokeWidth="1.2"/></svg>
              </IconBtn>
              <span style={{ fontSize: 11, color: C.muted }}>引用文件 · 历史任务 · 从剪贴板插入</span>
              <div style={{ flex: 1 }}/>
              <span style={{ fontFamily: MONO, fontSize: 10.5, color: C.muted }}>{prompt.length} / 12000</span>
            </div>
          </div>
        </Section>

        {/* options */}
        <Section label="运行选项">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            <OptionRow label="模型" value="claude-sonnet-4.5"/>
            <OptionRow label="批准策略" value="敏感操作需确认"/>
            <OptionRow label="可写入目录" value="仅当前工作区"/>
            <OptionRow label="网络访问" value="关闭" disabled/>
          </div>
        </Section>

        {/* templates */}
        <Section label="模板">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[
              ['修复报错', '粘贴报错堆栈 · 定位原因 · 最小修复'],
              ['实现功能', '写出设计思路 · 实现 · 覆盖测试'],
              ['代码审阅', '审阅指定分支 · 给出具体改进建议'],
              ['重构', '不改行为 · 改进结构 · 增加注释'],
            ].map(([t, d], i) => (
              <button key={i} onClick={() => setPrompt(d)} style={{
                padding: '10px 12px', background: 'transparent', border: `1px solid ${C.line}`, borderRadius: 5,
                display: 'flex', alignItems: 'center', gap: 14, cursor: 'pointer', fontFamily: 'inherit',
                textAlign: 'left',
              }}>
                <span style={{ fontSize: 12.5, color: C.text, fontWeight: 500, width: 80, flexShrink: 0 }}>{t}</span>
                <span style={{ fontSize: 12, color: C.muted, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d}</span>
              </button>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>{label}</div>
      {children}
    </div>
  );
}

function OptionRow({ label, value, disabled }) {
  return (
    <div style={{ padding: '10px 12px', background: C.panel, border: `1px solid ${C.line}`, borderRadius: 5, display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{ fontSize: 12, color: C.textSoft }}>{label}</span>
      <span style={{ flex: 1 }}/>
      <span style={{ fontFamily: MONO, fontSize: 11.5, color: disabled ? C.muted : C.text }}>{value}</span>
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 4l3 3 3-3" stroke={C.muted} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>
    </div>
  );
}

// ─── Tray Flyout ───────────────────────────────────────────
function TrayFlyout({ accent }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#0B0B0F' }}>
      <div style={{ padding: '14px 16px', borderBottom: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', gap: 10 }}>
        <BrandIcon size={18}/>
        <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>Codesk</div>
        <PulseDot color={C.success}/>
        <span style={{ fontSize: 11, color: C.textSoft }}>已就绪</span>
        <div style={{ flex: 1 }}/>
        <button style={{ width: 22, height: 22, borderRadius: 4, background: 'transparent', border: 'none', color: C.muted, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="2" r="1" fill="currentColor"/><circle cx="6" cy="10" r="1" fill="currentColor"/></svg>
        </button>
      </div>

      {/* pending approval card */}
      <div style={{ padding: '12px 16px' }}>
        <div style={{ padding: 12, background: 'rgba(233,226,191,0.06)', border: `1px solid ${C.warn}33`, borderRadius: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M6 1l5 9H1l5-9z" stroke={C.warn} strokeWidth="1.3"/></svg>
            <span style={{ fontSize: 11.5, fontWeight: 600, color: C.text }}>1 个审批 · 来自 iPhone</span>
            <span style={{ marginLeft: 'auto', fontFamily: MONO, fontSize: 10, color: C.muted }}>刚刚</span>
          </div>
          <div style={{ fontSize: 12, color: C.textSoft, marginBottom: 10, lineHeight: 1.5 }}>
            写入 <span style={{ fontFamily: MONO, color: C.text }}>bridge/src/queue.rs</span> · <span style={{ fontFamily: MONO, color: C.success }}>+28</span> <span style={{ fontFamily: MONO, color: C.danger }}>−6</span>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button style={{ flex: 1, height: 28, background: accent, border: 'none', borderRadius: 4, color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>批准</button>
            <button style={{ height: 28, paddingInline: 10, background: 'transparent', border: `1px solid ${C.line}`, borderRadius: 4, color: C.textSoft, fontSize: 11.5, cursor: 'pointer', fontFamily: 'inherit' }}>查看</button>
            <button style={{ height: 28, paddingInline: 10, background: 'transparent', border: `1px solid ${C.danger}44`, borderRadius: 4, color: C.danger, fontSize: 11.5, cursor: 'pointer', fontFamily: 'inherit' }}>拒绝</button>
          </div>
        </div>
      </div>

      {/* active sessions */}
      <div style={{ padding: '0 16px 10px' }}>
        <div style={{ fontSize: 10, color: C.muted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>运行中</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <MiniSession title="修复 MCP relay 心跳丢失" detail="编辑 heartbeat.rs · 3 turns"/>
          <MiniSession title="重构调度队列超时" detail="等待审批"/>
        </div>
      </div>

      <div style={{ flex: 1 }}/>

      {/* footer actions */}
      <div style={{ padding: 10, borderTop: `1px solid ${C.line}`, display: 'flex', gap: 4, background: 'rgba(255,255,255,0.01)' }}>
        <FlyBtn icon={<svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 1v11M1 6.5h11" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>} label="新建任务"/>
        <FlyBtn icon={<svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="2" y="2" width="4" height="4" stroke="currentColor" strokeWidth="1.2"/><rect x="7" y="2" width="4" height="4" stroke="currentColor" strokeWidth="1.2"/><rect x="2" y="7" width="4" height="4" stroke="currentColor" strokeWidth="1.2"/><path d="M8 8h1M10 8v1M8 10h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>} label="配对"/>
        <FlyBtn icon={<svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M2 3h9v7H2V3z" stroke="currentColor" strokeWidth="1.2"/><path d="M5 3V2h3v1" stroke="currentColor" strokeWidth="1.2"/></svg>} label="打开主窗口"/>
      </div>
    </div>
  );
}

function MiniSession({ title, detail }) {
  return (
    <div style={{ padding: '8px 10px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${C.line}`, borderRadius: 5, display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
      <PulseDot color={C.accent}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11.5, color: C.text, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</div>
        <div style={{ fontFamily: MONO, fontSize: 10, color: C.muted, marginTop: 1 }}>{detail}</div>
      </div>
    </div>
  );
}

function FlyBtn({ icon, label }) {
  return (
    <button style={{
      flex: 1, padding: '8px 4px', background: 'transparent', border: 'none',
      color: C.textSoft, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
      borderRadius: 4,
    }} onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
       onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

Object.assign(window, {
  Sidebar, LibraryScreen, SessionScreen, PairScreen, ComposeScreen, TrayFlyout,
});
