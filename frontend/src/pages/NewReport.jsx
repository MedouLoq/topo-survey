import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { api } from "../api";
import { Card, SectionTitle, Input, Select, Textarea, Btn } from "../components/ui";

const OBSTACLES = [
  "Bâtiment / Construction",
  "Ligne électrique existante",
  "Route nationale",
  "Oued / Zone inondable",
  "Zone militaire / Protégée",
  "Terrain inaccessible",
  "Zone rocheuse difficile",
  "Zone urbaine dense",
  "Autre contrainte",
];

const WEATHER = [
  "Ensoleillé",
  "Nuageux",
  "Brume / Sable",
  "Pluie",
  "Vent fort",
  "Orage",
];

const today = () => new Date().toISOString().split("T")[0];

// ── GPS / manual coordinate block ─────────────────────────────────────────
const isSecureContext = window.isSecureContext || location.protocol === "https:";

function GpsBtn({ label, onCapture, coords }) {
  const [loading, setLoading] = useState(false);
  const [manual,  setManual]  = useState(false);
  const [manLat,  setManLat]  = useState("");
  const [manLon,  setManLon]  = useState("");

  const captureGps = () => {
    setLoading(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        onCapture(pos.coords.latitude, pos.coords.longitude);
        setLoading(false);
        toast.success(`Position capturée`);
      },
      (err) => {
        setLoading(false);
        // Fall back to manual on any geolocation error
        setManual(true);
        toast.error("GPS indisponible — saisissez les coordonnées manuellement.");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const applyManual = () => {
    const lat = parseFloat(manLat);
    const lon = parseFloat(manLon);
    if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      toast.error("Coordonnées invalides.");
      return;
    }
    onCapture(lat, lon);
    setManual(false);
    toast.success("Coordonnées enregistrées");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label className="field-label">{label}</label>

      {/* GPS button — only shown if secure context */}
      {!manual && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          {isSecureContext ? (
            <Btn size="sm" variant={coords ? "ghost" : "primary"} onClick={captureGps} disabled={loading}>
              {loading ? "Localisation…" : coords ? "Recapturer GPS" : "Capturer GPS"}
            </Btn>
          ) : (
            <span style={{ fontSize: 11, color: "var(--amber)" }}>
              GPS nécessite HTTPS —
            </span>
          )}
          <Btn size="sm" variant="ghost" onClick={() => setManual(true)}>
            Saisir manuellement
          </Btn>
          {coords && (
            <>
              <span style={{ fontSize: 11, fontFamily: "Fira Code, monospace", color: "var(--accent)" }}>
                {coords.lat.toFixed(5)}°N, {coords.lon.toFixed(5)}°E
              </span>
              <Btn size="sm" variant="ghost" onClick={() => onCapture(null, null)}
                style={{ padding: "4px 8px", fontSize: 11 }}>✕</Btn>
            </>
          )}
        </div>
      )}

      {/* Manual input */}
      {manual && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 120px" }}>
            <label className="field-label" style={{ marginBottom: 4 }}>Latitude (°N)</label>
            <input
              className="field-input"
              type="number" step="0.000001" placeholder="ex : 20.123456"
              value={manLat} onChange={e => setManLat(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ flex: "1 1 120px" }}>
            <label className="field-label" style={{ marginBottom: 4 }}>Longitude (°E)</label>
            <input
              className="field-input"
              type="number" step="0.000001" placeholder="ex : -5.654321"
              value={manLon} onChange={e => setManLon(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <Btn size="sm" onClick={applyManual} style={{ marginBottom: 1 }}>OK</Btn>
          <Btn size="sm" variant="ghost" onClick={() => setManual(false)} style={{ marginBottom: 1 }}>Annuler</Btn>
        </div>
      )}
    </div>
  );
}

export default function NewReport({ onSaved }) {
  const [config,     setConfig]     = useState(null);
  const [lastReport, setLastReport] = useState(null);
  const [loading,    setLoading]    = useState(false);

  const [form, setForm] = useState({
    date:            today(),
    kp_start:        "",
    kp_end:          "",
    points_captured: "",
    crew_count:      5,
    weather:         "Ensoleillé",
    obstacles:       [],   // [{name, kp: null|float}]
    eng_note:        "",
    kp_start_lat:    null,
    kp_start_lon:    null,
    kp_end_lat:      null,
    kp_end_lon:      null,
  });

  useEffect(() => {
    Promise.all([api.getConfig(), api.listReports({ limit: 1 })]).then(([c, r]) => {
      setConfig(c);
      if (r.length > 0) {
        setLastReport(r[0]);
        setForm(f => ({ ...f, kp_start: r[0].kp_end }));
      }
    });
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  // Toggle obstacle chip on/off
  const toggleObstacle = (name) => {
    setForm(f => {
      const exists = f.obstacles.find(o => o.name === name);
      if (exists) {
        return { ...f, obstacles: f.obstacles.filter(o => o.name !== name) };
      }
      return { ...f, obstacles: [...f.obstacles, { name, kp: null }] };
    });
  };

  // Update KP for a specific obstacle
  const setObstacleKp = (name, kpVal) => {
    setForm(f => ({
      ...f,
      obstacles: f.obstacles.map(o =>
        o.name === name ? { ...o, kp: kpVal === "" ? null : parseFloat(kpVal) } : o
      ),
    }));
  };

  const isObstacleActive = (name) => form.obstacles.some(o => o.name === name);

  const kmDay  = parseFloat(form.kp_end) - parseFloat(form.kp_start);
  const valid  = form.date && !isNaN(kmDay) && kmDay > 0;
  const target = config?.daily_target_km || 10;
  const total  = config?.total_km || 200;
  const pctAfter = form.kp_end
    ? Math.min(100, (parseFloat(form.kp_end) / total) * 100).toFixed(1)
    : null;

  const handleSubmit = async () => {
    if (!valid) { toast.error("Vérifiez les valeurs KP de début et fin."); return; }
    setLoading(true);
    try {
      await api.createReport({
        ...form,
        kp_start:        parseFloat(form.kp_start),
        kp_end:          parseFloat(form.kp_end),
        points_captured: parseInt(form.points_captured) || 0,
        crew_count:      parseInt(form.crew_count) || 5,
        // obstacles already in [{name, kp}] format
      });
      toast.success("Rapport journalier enregistré");
      onSaved?.();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 740, display: "flex", flexDirection: "column", gap: 14 }}>

      {/* ── Live preview ── */}
      {valid && (
        <div className="preview-banner">
          <div>
            <div className="preview-label">Levé du jour</div>
            <div className="preview-val" style={{
              fontSize: 24,
              color: kmDay >= target ? "var(--green)" : "var(--red)",
            }}>
              {kmDay.toFixed(2)} km
            </div>
          </div>
          <div>
            <div className="preview-label">Avancement après saisie</div>
            <div className="preview-val" style={{ fontSize: 24, color: "var(--accent)" }}>
              {pctAfter}%
            </div>
          </div>
          <div>
            <div className="preview-label">vs Objectif ({target} km)</div>
            <div className="preview-val" style={{
              fontSize: 16,
              color: kmDay >= target ? "var(--green)" : "var(--amber)",
            }}>
              {kmDay >= target
                ? `+${(kmDay - target).toFixed(2)} km ✓`
                : `−${(target - kmDay).toFixed(2)} km`}
            </div>
          </div>
        </div>
      )}

      {/* ── Main fields ── */}
      <Card>
        <SectionTitle>Données de journée</SectionTitle>

        {lastReport && (
          <div style={{
            marginBottom: 16, padding: "8px 12px",
            background: "var(--surface2)", border: "1px solid var(--border2)",
            borderRadius: 7, fontSize: 11.5, color: "var(--text2)",
          }}>
            Dernier rapport :&nbsp;
            <span className="mono" style={{ color: "var(--text)" }}>{lastReport.date}</span>
            &nbsp;· KP jusqu'à&nbsp;
            <span className="mono" style={{ color: "var(--accent)" }}>{lastReport.kp_end}</span>
          </div>
        )}

        <div className="form-grid-2col">
          <Input label="Date" type="date" value={form.date}
            onChange={e => set("date", e.target.value)} />
          <Select label="Météo" value={form.weather}
            onChange={e => set("weather", e.target.value)}>
            {WEATHER.map(w => <option key={w}>{w}</option>)}
          </Select>
          <Input label="KP Début (km)" type="number" step="0.1"
            value={form.kp_start}
            onChange={e => set("kp_start", e.target.value)}
            placeholder={lastReport?.kp_end ?? "0"} />
          <Input label="KP Fin (km)" type="number" step="0.1"
            value={form.kp_end}
            onChange={e => set("kp_end", e.target.value)}
            placeholder="ex : 56.4" />
          <Input label="Points topographiques" type="number"
            value={form.points_captured}
            onChange={e => set("points_captured", e.target.value)}
            placeholder="ex : 75" />
          <Input label="Effectif terrain" type="number"
            value={form.crew_count}
            onChange={e => set("crew_count", e.target.value)} />
        </div>
      </Card>

      {/* ── GPS localisation ── */}
      <Card>
        <SectionTitle>Localisation GPS du tracé</SectionTitle>
        <div style={{ fontSize: 11.5, color: "var(--text3)", marginBottom: 12 }}>
          Capturez votre position sur le terrain pour inclure une carte dans le PDF.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <GpsBtn
            label="Point de départ (KP début)"
            coords={form.kp_start_lat != null ? { lat: form.kp_start_lat, lon: form.kp_start_lon } : null}
            onCapture={(lat, lon) => setForm(f => ({ ...f, kp_start_lat: lat, kp_start_lon: lon }))}
          />
          <GpsBtn
            label="Point d'arrivée (KP fin)"
            coords={form.kp_end_lat != null ? { lat: form.kp_end_lat, lon: form.kp_end_lon } : null}
            onCapture={(lat, lon) => setForm(f => ({ ...f, kp_end_lat: lat, kp_end_lon: lon }))}
          />
        </div>
        {(form.kp_start_lat && form.kp_end_lat) && (
          <div style={{
            marginTop: 10, padding: "8px 12px",
            background: "rgba(34,211,238,0.05)",
            border: "1px solid rgba(34,211,238,0.15)",
            borderRadius: 7, fontSize: 11.5, color: "var(--accent)",
          }}>
            Carte OpenStreetMap incluse dans le PDF journalier
          </div>
        )}
      </Card>

      {/* ── Obstacles ── */}
      <Card>
        <SectionTitle>Obstacles &amp; contraintes</SectionTitle>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
          {OBSTACLES.map(o => (
            <button
              key={o}
              onClick={() => toggleObstacle(o)}
              className={`chip${isObstacleActive(o) ? " active" : ""}`}
            >
              {o}
            </button>
          ))}
        </div>

        {/* KP inputs for active obstacles */}
        {form.obstacles.length > 0 && (
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text3)", textTransform: "uppercase", letterSpacing: 1.5 }}>
              Localisation des obstacles (KP)
            </div>
            {form.obstacles.map(o => {
              const kpMin = parseFloat(form.kp_start) || 0;
              const kpMax = parseFloat(form.kp_end) || undefined;
              return (
                <div key={o.name} style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <span style={{
                    fontSize: 12, color: "var(--amber)", flex: "1 1 180px",
                    minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    ▲ {o.name}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                    <Input
                      label=""
                      type="number"
                      step="0.01"
                      placeholder={`KP (${kpMin}–${kpMax ?? "?"})`}
                      value={o.kp ?? ""}
                      onChange={e => setObstacleKp(o.name, e.target.value)}
                      style={{ width: 130, marginBottom: 0 }}
                    />
                    <span style={{ fontSize: 11, color: "var(--text3)" }}>km</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {form.obstacles.length > 0 && (
          <div style={{ marginTop: 10, fontSize: 11.5, color: "var(--amber)", display: "flex", alignItems: "center", gap: 6 }}>
            <span>▲</span>
            {form.obstacles.length} contrainte{form.obstacles.length > 1 ? "s" : ""} sélectionnée{form.obstacles.length > 1 ? "s" : ""} — incluses dans le PDF journalier
          </div>
        )}
      </Card>

      {/* ── Engineer note ── */}
      <Card>
        <SectionTitle>Note de l'ingénieur</SectionTitle>
        <Textarea
          value={form.eng_note}
          onChange={e => set("eng_note", e.target.value)}
          placeholder="Observations techniques, décisions prises, points KP à vérifier, remarques sur le couloir..."
        />
      </Card>

      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
        <Btn variant="ghost" size="sm" onClick={() => onSaved?.()}>Annuler</Btn>
        <Btn size="sm" onClick={handleSubmit} disabled={!valid || loading}>
          {loading ? "Enregistrement…" : "Enregistrer le rapport journalier"}
        </Btn>
      </div>

    </div>
  );
}
