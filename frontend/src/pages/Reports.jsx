/**
 * Reports page — two tabs:
 *   "Journaliers"  : list of daily reports + daily PDF per row
 *   "Hebdomadaires": weekly summaries + weekly PDF download
 */
import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { api } from "../api";
import {
  Card, SectionTitle, Tabs, Badge, Btn, Spinner, Empty, chartTooltipStyle,
} from "../components/ui";

// ── Shared helpers ─────────────────────────────────────────────────
function fmtDate(str, opts = {}) {
  return new Date(str).toLocaleDateString("fr-FR", opts);
}

async function downloadBlob(url, filename) {
  const res  = await fetch(url);
  const blob = await res.blob();
  const a    = document.createElement("a");
  a.href     = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

// ══ Tab 1: Rapports Journaliers ════════════════════════════════════
function DailyReports({ config }) {
  const [reports,    setReports]    = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [pdfLoading, setPdfLoading] = useState(null); // report id
  const [deleting,   setDeleting]   = useState(null); // report id

  useEffect(() => {
    api.listReports({ limit: 500 })
      .then(r => setReports(r.sort((a, b) => b.date.localeCompare(a.date))))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (r) => {
    if (!window.confirm(`Supprimer le rapport du ${fmtDate(r.date, { weekday: "long", day: "2-digit", month: "long" })} ?\nCette action est irréversible.`))
      return;
    setDeleting(r.id);
    try {
      await api.deleteReport(r.id);
      setReports(prev => prev.filter(x => x.id !== r.id));
    } catch (e) {
      alert(e.message);
    } finally {
      setDeleting(null);
    }
  };

  const target = config?.daily_target_km || 10;

  const handlePdf = async (r) => {
    setPdfLoading(r.id);
    try {
      await downloadBlob(
        api.dailyPdfUrl(r.id),
        `rapport_journalier_${r.date}.pdf`,
      );
    } finally {
      setPdfLoading(null);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

      {/* Summary strip */}
      <div style={{
        display: "flex", gap: 16, flexWrap: "wrap",
        padding: "10px 16px",
        background: "var(--surface2)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        fontSize: 12, color: "var(--text2)",
      }}>
        <span><strong style={{ color: "var(--text)", fontFamily: "Fira Code, monospace" }}>{reports.length}</strong> rapports journaliers</span>
        <span><strong style={{ color: "var(--green)", fontFamily: "Fira Code, monospace" }}>
          {reports.filter(r => r.km_done >= target).length}
        </strong> objectif atteint</span>
        <span><strong style={{ color: "var(--red)", fontFamily: "Fira Code, monospace" }}>
          {reports.filter(r => r.km_done < target).length}
        </strong> en dessous</span>
      </div>

      <Card>
        <SectionTitle>Liste des rapports journaliers</SectionTitle>
        {reports.length === 0 ? (
          <Empty message="Aucun rapport journalier saisi" />
        ) : (
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  {["Date", "KP Déb.", "KP Fin", "Levé", "Points", "Météo", "Obstacles", "PDF", ""].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports.map(r => (
                  <tr key={r.id}>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)", whiteSpace: "nowrap" }}>
                      {fmtDate(r.date, { weekday: "short", day: "2-digit", month: "short" })}
                    </td>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)" }}>{r.kp_start}</td>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)" }}>{r.kp_end}</td>
                    <td className="mono" style={{
                      fontSize: 12, fontWeight: 600,
                      color: r.km_done >= target ? "var(--green)" : "var(--red)",
                    }}>
                      {r.km_done.toFixed(2)} km
                    </td>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)" }}>{r.points_captured}</td>
                    <td style={{ fontSize: 12, color: "var(--text2)" }}>{r.weather || "—"}</td>
                    <td>
                      {r.obstacles.length > 0
                        ? <Badge color="var(--amber)">{r.obstacles.length} (!)</Badge>
                        : <span style={{ color: "var(--green)", fontSize: 12 }}>OK</span>}
                    </td>
                    <td>
                      <Btn size="sm" variant="ghost"
                        disabled={pdfLoading === r.id}
                        onClick={() => handlePdf(r)}
                        style={{ fontSize: 11 }}>
                        {pdfLoading === r.id ? "…" : "⬇ PDF"}
                      </Btn>
                    </td>
                    <td>
                      <Btn size="sm" variant="danger"
                        disabled={deleting === r.id}
                        onClick={() => handleDelete(r)}
                        style={{ fontSize: 11 }}>
                        {deleting === r.id ? "…" : "Supprimer"}
                      </Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ══ Tab 2: Rapports Hebdomadaires ══════════════════════════════════
function WeeklyReports({ config }) {
  const [weeks,      setWeeks]      = useState([]);
  const [selected,   setSelected]   = useState(null);
  const [reports,    setReports]    = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [pdfLoading, setPdfLoading] = useState(false);

  useEffect(() => {
    api.listWeeks().then(setWeeks).finally(() => setLoading(false));
  }, []);

  const selectWeek = async (w) => {
    setSelected(w);
    const r = await api.listReports({ year: w.year, week: w.week });
    setReports(r.sort((a, b) => a.date.localeCompare(b.date)));
  };

  const handlePdf = async () => {
    if (!selected) return;
    setPdfLoading(true);
    try {
      await downloadBlob(
        api.weeklyPdfUrl(selected.year, selected.week),
        `rapport_hebdomadaire_S${selected.week}_${selected.year}.pdf`,
      );
    } finally {
      setPdfLoading(false);
    }
  };

  if (loading) return <Spinner />;

  const target = config?.daily_target_km || 10;

  /* ── Week list ── */
  if (!selected) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 680 }}>
        <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase",
          letterSpacing: 2, fontWeight: 700, marginBottom: 4 }}>
          Sélectionner une semaine
        </div>
        {weeks.length === 0 && <Empty message="Aucune semaine disponible" />}
        {weeks.map(w => {
          const obj     = target * w.days;
          const onTrack = w.km_total >= obj;
          return (
            <div key={w.key} className="list-card" onClick={() => selectWeek(w)}>
              <div>
                <div style={{ fontWeight: 600, color: "var(--text)", fontSize: 14 }}>
                  Semaine {w.week}
                  <span style={{ color: "var(--text3)", fontWeight: 400, fontSize: 12, marginLeft: 10 }}>
                    {w.date_start} – {w.date_end}
                  </span>
                </div>
                <div style={{ color: "var(--text3)", fontSize: 11.5, marginTop: 4 }}>
                  {w.days} jour{w.days > 1 ? "s" : ""} travaillé{w.days > 1 ? "s" : ""}
                  {w.obstacles > 0 && (
                    <span style={{ color: "var(--amber)", marginLeft: 10 }}>
                      · {w.obstacles} obstacle{w.obstacles > 1 ? "s" : ""}
                    </span>
                  )}
                </div>
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div className="mono" style={{
                  fontSize: 20, fontWeight: 700,
                  color: onTrack ? "var(--green)" : "var(--amber)",
                }}>
                  {w.km_total.toFixed(1)} km
                </div>
                <div style={{ fontSize: 10, color: "var(--text3)", marginTop: 2 }}>
                  obj. {obj.toFixed(0)} km
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  /* ── Week detail ── */
  const kmWeek       = reports.reduce((s, r) => s + r.km_done, 0);
  const ptsWeek      = reports.reduce((s, r) => s + r.points_captured, 0);
  // obstacles are now {name, kp} objects (or strings for old data)
  const obstaclesAll = reports.flatMap(r =>
    r.obstacles.map(o => ({
      date: r.date,
      name: typeof o === "string" ? o : o.name,
      kp:   typeof o === "string" ? null : o.kp,
    }))
  );
  const obj          = target * reports.length;
  const onTrack      = kmWeek >= obj;
  const avg          = kmWeek / (reports.length || 1);
  const barData      = reports.map(r => ({ date: r.date.slice(5), km: r.km_done }));

  return (
    <div style={{ maxWidth: 800, display: "flex", flexDirection: "column", gap: 14 }}>

      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <Btn variant="ghost" size="sm" onClick={() => { setSelected(null); setReports([]); }}>
          ← Toutes les semaines
        </Btn>
        <div style={{ flex: 1 }} />
        <Btn size="sm" variant={pdfLoading ? "ghost" : "primary"}
          onClick={handlePdf} disabled={pdfLoading}>
          {pdfLoading ? "Génération…" : "⬇ Rapport PDF"}
        </Btn>
      </div>

      {/* Week header */}
      <Card style={{ borderTop: "2px solid var(--accent)", padding: "14px 18px" }}>
        <div style={{ fontSize: 9, color: "var(--text3)", textTransform: "uppercase",
          letterSpacing: 2, fontWeight: 700, marginBottom: 4 }}>
          Rapport hebdomadaire
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", letterSpacing: -0.3 }}>
          Semaine {selected.week}
          <span style={{ fontSize: 14, color: "var(--text2)", fontWeight: 400, marginLeft: 12 }}>
            {selected.date_start} – {selected.date_end}
          </span>
        </div>
        {config?.project_name && (
          <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 3 }}>{config.project_name}</div>
        )}
      </Card>

      {/* Weekly KPIs */}
      <div className="kpi-grid">
        {[
          { label: "Levé hebdo",      value: `${kmWeek.toFixed(1)} km`, sub: `obj : ${obj.toFixed(0)} km`, color: onTrack ? "var(--green)" : "var(--amber)" },
          { label: "Jours travaillés",value: reports.length,            sub: "jours ouvrés",                color: "var(--accent)" },
          { label: "Points relevés",  value: ptsWeek.toLocaleString("fr-FR"), sub: `${Math.round(ptsWeek / (reports.length || 1))}/j`, color: "var(--purple)" },
          { label: "Obstacles",       value: obstaclesAll.length,        sub: obstaclesAll.length ? "identifiés" : "aucun", color: obstaclesAll.length ? "var(--amber)" : "var(--green)" },
        ].map((k, i) => (
          <div key={i} className="kpi-card" style={{ "--kpi-color": k.color }}>
            <div className="kpi-glow" />
            <div className="kpi-value mono">{k.value}</div>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Chart */}
      <Card>
        <SectionTitle>Production journalière — semaine {selected.week}</SectionTitle>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={barData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "var(--text3)", fontSize: 9, fontFamily: "Fira Code" }}
              axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "var(--text3)", fontSize: 9, fontFamily: "Fira Code" }}
              axisLine={false} tickLine={false} />
            <Tooltip contentStyle={chartTooltipStyle} />
            <ReferenceLine y={target} stroke="var(--amber)" strokeDasharray="4 2" />
            <Bar dataKey="km" name="km levés" radius={[4, 4, 0, 0]} maxBarSize={36}>
              {barData.map((d, i) => (
                <Cell key={i} fill={d.km >= target ? "var(--green)" : "var(--red)"} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Daily detail table */}
      <Card>
        <SectionTitle>Détail journalier</SectionTitle>
        <div className="scroll-x">
          <table className="data-table">
            <thead>
              <tr>
                {["Date", "KP Déb.", "KP Fin", "Levé", "Points", "Météo", "Note ingénieur"].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reports.map(r => (
                <tr key={r.id}>
                  <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)", whiteSpace: "nowrap" }}>
                    {fmtDate(r.date, { weekday: "short", day: "2-digit", month: "short" })}
                  </td>
                  <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)" }}>{r.kp_start}</td>
                  <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)" }}>{r.kp_end}</td>
                  <td className="mono" style={{
                    fontSize: 12, fontWeight: 600,
                    color: r.km_done >= target ? "var(--green)" : "var(--red)",
                  }}>
                    {r.km_done.toFixed(2)} km
                  </td>
                  <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)" }}>{r.points_captured}</td>
                  <td style={{ fontSize: 12 }}>{r.weather}</td>
                  <td style={{ color: "var(--text3)", fontSize: 11.5, maxWidth: 200,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.eng_note || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Obstacles */}
      {obstaclesAll.length > 0 && (
        <Card>
          <SectionTitle>Obstacles identifiés</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {obstaclesAll.map((item, i) => (
              <div key={i} style={{
                display: "flex", gap: 14, flexWrap: "wrap",
                padding: "8px 12px",
                background: "rgba(245,158,11,0.06)",
                border: "1px solid rgba(245,158,11,0.14)",
                borderRadius: 7,
              }}>
                <span className="mono" style={{ fontSize: 11, color: "var(--text3)", whiteSpace: "nowrap", marginTop: 1 }}>
                  {fmtDate(item.date, { day: "2-digit", month: "short" })}
                </span>
                {item.kp != null && (
                  <span className="mono" style={{ fontSize: 11, color: "var(--accent)", whiteSpace: "nowrap", marginTop: 1 }}>
                    KP {item.kp.toFixed(2)} km
                  </span>
                )}
                <span style={{ fontSize: 12.5, color: "var(--amber)" }}>▲ {item.name}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Synthesis */}
      <Card>
        <SectionTitle>Synthèse hebdomadaire</SectionTitle>
        <div className="synth-block">
          Durant la <strong style={{ color: "var(--text)" }}>semaine {selected.week}</strong>{" "}
          ({selected.date_start} – {selected.date_end}), l'équipe a réalisé un levé de{" "}
          <strong style={{ color: "var(--text)" }}>{kmWeek.toFixed(1)} km</strong> sur{" "}
          <strong style={{ color: "var(--text)" }}>{reports.length} journée{reports.length > 1 ? "s" : ""}</strong>,
          capturant <strong style={{ color: "var(--text)" }}>{ptsWeek} points topographiques</strong>{" "}
          (profils 40 m, 3 pts/couloir). Moyenne : <strong style={{ color: "var(--text)" }}>{avg.toFixed(1)} km/jour</strong>.{" "}
          {onTrack
            ? `Objectif hebdomadaire de ${obj.toFixed(0)} km atteint (+${(kmWeek - obj).toFixed(1)} km).`
            : `Écart de ${(obj - kmWeek).toFixed(1)} km par rapport à l'objectif de ${obj.toFixed(0)} km.`}{" "}
          {obstaclesAll.length > 0
            ? `${obstaclesAll.length} contrainte(s) identifiées et documentées pour l'étude mécanique du couloir.`
            : "Aucune contrainte majeure identifiée cette semaine."}
        </div>
      </Card>

    </div>
  );
}

// ══ Main component ═════════════════════════════════════════════════
export default function Reports() {
  const [tab,    setTab]    = useState("daily");
  const [config, setConfig] = useState(null);

  useEffect(() => { api.getConfig().then(setConfig); }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <Tabs
          tabs={[
            { id: "daily",  label: "Rapports journaliers" },
            { id: "weekly", label: "Rapports hebdomadaires" },
          ]}
          active={tab}
          onChange={setTab}
        />
        <div style={{ flex: 1 }} />
        <div className="tab-hint">
          {tab === "daily"
            ? "Un rapport par jour de terrain · PDF téléchargeable"
            : "Synthèse hebdomadaire · PDF complet"}
        </div>
      </div>

      <div className="divider" />

      {tab === "daily"  && <DailyReports  config={config} />}
      {tab === "weekly" && <WeeklyReports config={config} />}
    </div>
  );
}
