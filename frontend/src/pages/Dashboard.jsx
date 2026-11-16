import { useEffect, useState } from "react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import { api } from "../api";
import {
  KpiCard, Card, SectionTitle, Badge, ProgressBar,
  Spinner, Empty, chartTooltipStyle,
} from "../components/ui";

export default function Dashboard() {
  const [stats,   setStats]   = useState(null);
  const [reports, setReports] = useState([]);
  const [config,  setConfig]  = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getStats(), api.listReports({ limit: 200 }), api.getConfig()])
      .then(([s, r, c]) => { setStats(s); setReports(r); setConfig(c); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;

  const total    = config?.total_km || 200;
  const target   = config?.daily_target_km || 10;
  const sorted   = [...reports].sort((a, b) => a.date.localeCompare(b.date));

  const barData  = sorted.map(r => ({ date: r.date.slice(5), km: r.km_done, target }));
  const areaData = sorted.map((r, i) => ({
    date:   r.date.slice(5),
    cumul:  r.kp_end,
    target: target * (i + 1),
  }));
  const segments = sorted.map(r => ({
    from:  (r.kp_start / total) * 100,
    width: (r.km_done  / total) * 100,
    color: r.obstacles.length > 0 ? "var(--amber)" : "var(--accent)",
    label: `${r.date}: KP${r.kp_start}–${r.kp_end}`,
  }));

  const projDate = new Date();
  projDate.setDate(projDate.getDate() + (stats?.days_remaining_estimated || 0));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

      {/* ── KPIs ── */}
      <div className="kpi-grid">
        <KpiCard large label="Avancement"
          value={`${stats?.pct_done?.toFixed(1) ?? "—"}%`}
          sub={`${stats?.km_done?.toFixed(1)} / ${total} km`}
          color="var(--accent)"
        />
        <KpiCard label="Reste à lever"
          value={`${stats?.km_remaining?.toFixed(1) ?? "—"} km`}
          sub={`≈ ${stats?.days_remaining_estimated ?? "—"} jours`}
          color="var(--amber)"
        />
        <KpiCard label="Fin projetée"
          value={projDate.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })}
          sub={`${stats?.avg_km_per_day?.toFixed(1) ?? "—"} km/jour moy.`}
          color="var(--purple)"
        />
        <KpiCard label="Points levés"
          value={(stats?.total_points ?? 0).toLocaleString("fr-FR")}
          sub={`${stats?.days_worked ?? 0} jours · ${stats?.total_obstacles ?? 0} obstacles`}
          color="var(--green)"
        />
      </div>

      {/* ── Progress bar ── */}
      <Card>
        <SectionTitle>Progression du tracé — KP 0 → KP {total}</SectionTitle>
        <ProgressBar pct={Math.min(100, stats?.pct_done || 0)} segments={segments} height={20} />
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 10, color: "var(--text3)" }}>
          <span className="mono">KP 0</span>
          <span className="mono">KP {total / 2}</span>
          <span className="mono">KP {total}</span>
        </div>
        <div style={{ display: "flex", gap: 18, marginTop: 10, fontSize: 10.5, color: "var(--text3)" }}>
          <span><span style={{ color: "var(--accent)" }}>■</span> Segment normal</span>
          <span><span style={{ color: "var(--amber)"  }}>■</span> Segment avec obstacle</span>
          <span style={{ marginLeft: "auto" }}>▏= position actuelle</span>
        </div>
      </Card>

      {/* ── Charts 2-col ── */}
      <div className="chart-grid-2col">

        <Card>
          <SectionTitle>Production journalière (km)</SectionTitle>
          {barData.length === 0 ? <Empty message="Aucun rapport journalier" /> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "var(--text3)", fontSize: 9, fontFamily: "Fira Code" }}
                  axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--text3)", fontSize: 9, fontFamily: "Fira Code" }}
                  axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chartTooltipStyle} cursor={{ fill: "rgba(255,255,255,0.02)" }} />
                <ReferenceLine y={target} stroke="var(--amber)" strokeDasharray="4 3"
                  label={{ value: `Obj.`, fill: "var(--amber)", fontSize: 9, position: "right" }} />
                <Bar dataKey="km" name="km levés" radius={[4, 4, 0, 0]} maxBarSize={28}>
                  {barData.map((d, i) => (
                    <Cell key={i} fill={d.km >= target ? "var(--green)" : "var(--red)"} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card>
          <SectionTitle>Avancement cumulé (km)</SectionTitle>
          {areaData.length === 0 ? <Empty message="Aucun rapport journalier" /> : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={areaData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                <defs>
                  <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="10%" stopColor="var(--accent)" stopOpacity={0.22} />
                    <stop offset="90%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gt" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="10%" stopColor="var(--amber)" stopOpacity={0.1} />
                    <stop offset="90%" stopColor="var(--amber)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "var(--text3)", fontSize: 9, fontFamily: "Fira Code" }}
                  axisLine={false} tickLine={false} />
                <YAxis domain={[0, total]} tick={{ fill: "var(--text3)", fontSize: 9, fontFamily: "Fira Code" }}
                  axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Area type="monotone" dataKey="target" name="Objectif"
                  stroke="var(--amber)" strokeDasharray="4 2" fill="url(#gt)"
                  strokeWidth={1.5} dot={false} />
                <Area type="monotone" dataKey="cumul" name="Réalisé"
                  stroke="var(--accent)" fill="url(#ga)" strokeWidth={2}
                  dot={{ fill: "var(--accent)", r: 2.5, strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* ── Journal table ── */}
      <Card>
        <SectionTitle>Journal de terrain</SectionTitle>
        {reports.length === 0 ? <Empty message="Aucun rapport saisi" /> : (
          <div className="scroll-x">
            <table className="data-table">
              <thead>
                <tr>
                  {["Date", "KP Déb.", "KP Fin", "Levé", "Points", "Météo", "Obstacles", "Note ingénieur"].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports.map(r => (
                  <tr key={r.id}>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--text2)", whiteSpace: "nowrap" }}>
                      {new Date(r.date).toLocaleDateString("fr-FR")}
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
                    <td style={{ fontSize: 12.5 }}>{r.weather || "—"}</td>
                    <td>
                      {r.obstacles.length > 0
                        ? <Badge color="var(--amber)">{r.obstacles.length} (!)</Badge>
                        : <span style={{ color: "var(--green)", fontSize: 12 }}>OK</span>}
                    </td>
                    <td style={{
                      color: "var(--text3)", fontSize: 11.5,
                      maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {r.eng_note || "—"}
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
