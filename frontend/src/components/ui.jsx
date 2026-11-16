// ── KPI Card ──────────────────────────────────────────────────────────────
export function KpiCard({ label, value, sub, color = "var(--accent)", large = false, icon }) {
  return (
    <div className="kpi-card" style={{ "--kpi-color": color }}>
      <div className="kpi-glow" />
      {icon && <span className="kpi-icon">{icon}</span>}
      <div className={`kpi-value mono${large ? " large" : ""}`}>{value}</div>
      <div className="kpi-label">{label}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────
export function Card({ children, style = {}, className = "" }) {
  return (
    <div className={`card ${className}`} style={style}>
      {children}
    </div>
  );
}

// ── Section Title ─────────────────────────────────────────────────────────
export function SectionTitle({ children, action }) {
  return (
    <div className="section-hd">
      <div className="section-hd-left">
        <div className="section-bar" />
        <span className="section-label">{children}</span>
      </div>
      {action}
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────
export function Badge({ children, color = "var(--amber)" }) {
  return (
    <span
      className="badge"
      style={{
        background: color + "18",
        color,
        border: `1px solid ${color}28`,
      }}
    >
      {children}
    </span>
  );
}

// ── Button ────────────────────────────────────────────────────────────────
export function Btn({ children, onClick, variant = "primary", size = "md", disabled = false, style = {} }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`btn btn-${variant} btn-${size}`}
      style={style}
    >
      {children}
    </button>
  );
}

// ── Input ─────────────────────────────────────────────────────────────────
export function Input({ label, ...props }) {
  return (
    <div>
      {label && <label className="field-label">{label}</label>}
      <input className="field-input" {...props} />
    </div>
  );
}

export function Select({ label, children, ...props }) {
  return (
    <div>
      {label && <label className="field-label">{label}</label>}
      <select className="field-input" style={{ appearance: "none", cursor: "pointer" }} {...props}>
        {children}
      </select>
    </div>
  );
}

export function Textarea({ label, ...props }) {
  return (
    <div>
      {label && <label className="field-label">{label}</label>}
      <textarea
        className="field-input"
        style={{ minHeight: 90, resize: "vertical", lineHeight: 1.6 }}
        {...props}
      />
    </div>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────
export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs">
      {tabs.map(t => (
        <button
          key={t.id}
          className={`tab${active === t.id ? " active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Progress Bar ──────────────────────────────────────────────────────────
export function ProgressBar({ pct, segments = [], height = 20 }) {
  return (
    <div className="progress-track" style={{ height }}>
      {segments.map((s, i) => (
        <div
          key={i}
          className="progress-segment"
          title={s.label}
          style={{ left: `${s.from}%`, width: `${s.width}%`, background: s.color || "var(--accent)" }}
        />
      ))}
      <div
        className="progress-cursor"
        style={{ left: `calc(${Math.min(100, pct)}% - 1.5px)` }}
      />
    </div>
  );
}

// ── Spinner ───────────────────────────────────────────────────────────────
export function Spinner() {
  return (
    <div className="spinner-wrap">
      <div className="spinner">
        <div className="spinner-outer" />
        <div className="spinner-inner" />
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────
export function Empty({ message = "Aucune donnée", icon = "·" }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <div className="empty-text">{message}</div>
    </div>
  );
}

// ── Chart tooltip style for Recharts ─────────────────────────────────────
export const chartTooltipStyle = {
  background: "#0c1524",
  border: "1px solid #1b2b40",
  color: "#f1f5f9",
  fontSize: 12,
  fontFamily: "'Fira Code', monospace",
  borderRadius: 8,
  boxShadow: "0 6px 24px rgba(0,0,0,0.5)",
};
