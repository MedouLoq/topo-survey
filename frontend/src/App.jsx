import { useState, useEffect } from "react";
import { Toaster } from "react-hot-toast";
import { api } from "./api";
import Dashboard    from "./pages/Dashboard";
import NewReport    from "./pages/NewReport";
import Reports      from "./pages/Reports";
import Settings     from "./pages/Settings";

// ── SVG Nav icons ─────────────────────────────────────────────────
const Icons = {
  Grid: () => (
    <svg viewBox="0 0 16 16" fill="none" className="nav-icon">
      <rect x="1" y="1" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9.5" y="1" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="1" y="9.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9.5" y="9.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  ),
  Plus: () => (
    <svg viewBox="0 0 16 16" fill="none" className="nav-icon">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M8 5v6M5 8h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  ),
  FileText: () => (
    <svg viewBox="0 0 16 16" fill="none" className="nav-icon">
      <path d="M9 1H3.5A1.5 1.5 0 002 2.5v11A1.5 1.5 0 003.5 15h9A1.5 1.5 0 0014 13.5V6L9 1z"
        stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
      <path d="M9 1v5h5" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
      <path d="M5 9h6M5 11.5h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  ),
  Settings: () => (
    <svg viewBox="0 0 16 16" fill="none" className="nav-icon">
      <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M11.2 4.8l1.4-1.4M3.4 12.6l1.4-1.4"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  ),
  Survey: () => (
    <svg viewBox="0 0 20 20" fill="none">
      <polyline points="2,15 6,7 9.5,11 13.5,4 18,8.5"
        stroke="var(--accent)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="2"  cy="15"  r="1.4" fill="var(--accent)" opacity="0.45"/>
      <circle cx="18" cy="8.5" r="1.7" fill="var(--accent)"/>
    </svg>
  ),
};

const NAV = [
  { id: "dashboard", label: "Tableau de bord",    short: "Bord",      Icon: Icons.Grid,     group: "Vue" },
  { id: "new",       label: "Nouveau rapport",     short: "Saisie",    Icon: Icons.Plus,     group: "Vue", cta: true },
  { id: "reports",   label: "Rapports",            short: "Rapports",  Icon: Icons.FileText, group: "Rapports" },
  { id: "settings",  label: "Paramètres",          short: "Config",    Icon: Icons.Settings, group: "Système" },
];

const META = {
  dashboard: { title: "Tableau de bord",   sub: "Vue d'ensemble du levé" },
  new:       { title: "Nouveau rapport",    sub: "Saisie journalière du levé" },
  reports:   { title: "Rapports",           sub: "Rapports journaliers & hebdomadaires" },
  settings:  { title: "Paramètres",         sub: "Configuration du projet" },
};

export default function App() {
  const [page,       setPage]       = useState("dashboard");
  const [refreshKey, setRefreshKey] = useState(0);

  const [project,    setProject]    = useState(null);

  // Project name and length come from the settings, not hardcoded labels
  useEffect(() => { api.getConfig().then(setProject).catch(() => {}); }, [page, refreshKey]);
  const projectLabel = project
    ? `${project.project_name} · ${Number(project.total_km).toLocaleString("fr-FR")} km`
    : "";

  const afterSave = () => { setRefreshKey(k => k + 1); setPage("dashboard"); };

  // Group nav items
  const groups = [...new Set(NAV.map(n => n.group))];

  return (
    <div className="app-shell">

      {/* ══ Sidebar ══════════════════════════════════════════════════ */}
      <aside className="sidebar">
        {/* Brand */}
        <div className="sidebar-brand">
          <div className="brand-icon"><Icons.Survey /></div>
          <div>
            <div className="brand-name">Levé Topo</div>
            <div className="brand-sub">{projectLabel}</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          {groups.map(group => (
            <div key={group}>
              <div className="nav-group-label">{group}</div>
              {NAV.filter(n => n.group === group).map(({ id, label, Icon, cta }) => (
                <button
                  key={id}
                  onClick={() => setPage(id)}
                  className={`nav-item${page === id ? " active" : ""}${cta ? " cta" : ""}`}
                  aria-current={page === id ? "page" : undefined}
                >
                  <Icon />
                  {label}
                </button>
              ))}
            </div>
          ))}
        </nav>

        {/* Status */}
        <div className="sidebar-footer">
          <div className="status-pill">
            <div className="status-dot" />
            <span className="status-text">Système actif</span>
          </div>
        </div>
      </aside>

      {/* ══ Main ═════════════════════════════════════════════════════ */}
      <div className="main-wrapper">
        {/* Top bar */}
        <div className="page-topbar">
          {/* Brand shown only on mobile (sidebar hidden) */}
          <div className="mobile-topbar-brand">
            <div className="brand-icon" style={{ width: 28, height: 28 }}><Icons.Survey /></div>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--accent)", letterSpacing: 2, textTransform: "uppercase" }}>Levé Topo</span>
          </div>
          <div className="page-topbar-title-block">
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)", lineHeight: 1.2 }}>
              {META[page].title}
            </div>
            <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2 }}>
              {page === "dashboard" && projectLabel ? `${META[page].sub} · ${projectLabel}` : META[page].sub}
            </div>
          </div>
          <span className="version-pill">v1.0.0</span>
        </div>

        {/* Page */}
        <main className="main-content">
          <div className="page-enter" key={page + refreshKey}>
            {page === "dashboard" && <Dashboard key={refreshKey} />}
            {page === "new"       && <NewReport  onSaved={afterSave} />}
            {page === "reports"   && <Reports />}
            {page === "settings"  && <Settings />}
          </div>
        </main>
      </div>

      {/* ══ Mobile Bottom Nav ════════════════════════════════════════ */}
      <nav className="mobile-nav" aria-label="Navigation principale">
        {NAV.map(({ id, short, Icon }) => (
          <button
            key={id}
            onClick={() => setPage(id)}
            className={`mobile-nav-item${page === id ? " active" : ""}`}
            aria-label={short}
            aria-current={page === id ? "page" : undefined}
          >
            <Icon />
            <span className="mobile-nav-label">{short}</span>
          </button>
        ))}
      </nav>

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#0c1524",
            border: "1px solid #1b2b40",
            color: "#f1f5f9",
            fontSize: 13,
            fontFamily: "'Fira Sans', sans-serif",
            borderRadius: 8,
            boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
          },
          success: { iconTheme: { primary: "var(--green)", secondary: "#0c1524" } },
          error:   { iconTheme: { primary: "var(--red)",   secondary: "#0c1524" } },
        }}
      />
    </div>
  );
}
