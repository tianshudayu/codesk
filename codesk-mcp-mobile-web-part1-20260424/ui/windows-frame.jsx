// Windows 11 frame — frameless dark window with custom caption bar.
// No deps. Exports WinWindow, WinCaption, WinTrayFlyout.

const WIN_FONT = "'Segoe UI Variable', 'Segoe UI', 'Inter', system-ui, sans-serif";

function WinCaption({ title, subtitle, onMin, onMax, onClose, accent = '#8B5CF6' }) {
  const btn = (label, hoverBg, hoverColor, onClick, children) => (
    <button
      onClick={onClick}
      onMouseEnter={e => { e.currentTarget.style.background = hoverBg; if (hoverColor) e.currentTarget.style.color = hoverColor; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgba(255,255,255,0.55)'; }}
      aria-label={label}
      style={{
        width: 46, height: 32, border: 'none', background: 'transparent',
        color: 'rgba(255,255,255,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', transition: 'background 0.12s',
        WebkitAppRegion: 'no-drag',
      }}
    >{children}</button>
  );
  return (
    <div style={{
      height: 32, flexShrink: 0, display: 'flex', alignItems: 'stretch',
      background: 'transparent', borderBottom: '1px solid rgba(255,255,255,0.04)',
      WebkitAppRegion: 'drag', userSelect: 'none',
    }}>
      {/* title */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '0 12px',
        fontFamily: WIN_FONT, fontSize: 12, color: 'rgba(255,255,255,0.72)', flex: 1, minWidth: 0,
      }}>
        <svg width="14" height="14" viewBox="0 0 256 256" fill="none" style={{ flexShrink: 0 }}>
          <path d="M72 112V86C72 71.64 83.64 60 98 60H122" stroke="#FFFFFF" strokeWidth="28" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M134 60H158C172.36 60 184 71.64 184 86V122" stroke={accent} strokeWidth="28" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M184 134V158C184 172.36 172.36 184 158 184H134" stroke="#FFFFFF" strokeWidth="28" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M122 184H98C83.64 184 72 172.36 72 158V134" stroke={accent} strokeWidth="28" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span style={{ fontWeight: 500, whiteSpace: 'nowrap' }}>{title || 'Codesk'}</span>
        {subtitle && (
          <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            — {subtitle}
          </span>
        )}
      </div>
      {/* window controls */}
      {btn('minimize', 'rgba(255,255,255,0.06)', null, onMin, (
        <svg width="10" height="10" viewBox="0 0 10 10"><path d="M1 5H9" stroke="currentColor" strokeWidth="1" /></svg>
      ))}
      {btn('maximize', 'rgba(255,255,255,0.06)', null, onMax, (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><rect x="1" y="1" width="8" height="8" stroke="currentColor" strokeWidth="1" /></svg>
      ))}
      {btn('close', '#C42B1C', '#fff', onClose, (
        <svg width="10" height="10" viewBox="0 0 10 10"><path d="M1 1l8 8M9 1l-8 8" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/></svg>
      ))}
    </div>
  );
}

function WinWindow({ title, subtitle, width = 1180, height = 760, accent, children }) {
  return (
    <div style={{
      width, height, borderRadius: 8, overflow: 'hidden',
      background: '#0B0B0F',
      boxShadow: '0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)',
      display: 'flex', flexDirection: 'column',
      fontFamily: WIN_FONT,
    }}>
      <WinCaption title={title} subtitle={subtitle} accent={accent} />
      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>{children}</div>
    </div>
  );
}

// Tray flyout — anchored bottom-right, sharp top edge
function WinTrayFlyout({ width = 360, height = 440, accent = '#8B5CF6', children }) {
  return (
    <div style={{
      width, height, borderRadius: 8, overflow: 'hidden',
      background: '#0B0B0F',
      border: '1px solid rgba(255,255,255,0.08)',
      boxShadow: '0 20px 60px rgba(0,0,0,0.7)',
      display: 'flex', flexDirection: 'column',
      fontFamily: WIN_FONT, position: 'relative',
    }}>
      {children}
      {/* tray pointer */}
      <div style={{
        position: 'absolute', bottom: -7, right: 20, width: 14, height: 14,
        background: '#0B0B0F', transform: 'rotate(45deg)',
        borderRight: '1px solid rgba(255,255,255,0.08)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}/>
    </div>
  );
}

Object.assign(window, { WinWindow, WinCaption, WinTrayFlyout, WIN_FONT });
