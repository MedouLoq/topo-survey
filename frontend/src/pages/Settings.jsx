import { useState, useEffect, useRef } from "react";
import toast from "react-hot-toast";
import { api } from "../api";
import { Card, SectionTitle, Input, Btn, Spinner } from "../components/ui";

export default function Settings() {
  const [form,      setForm]      = useState({});
  const [loading,   setLoading]   = useState(true);
  const [saving,    setSaving]    = useState(false);
  const [logoUrl,   setLogoUrl]   = useState("");
  const [logoLoading, setLogoLoading] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    api.getConfig().then(c => {
      setForm({
        project_name:    c.project_name,
        location:        c.location,
        total_km:        c.total_km,
        daily_target_km: c.daily_target_km,
        start_date:      c.start_date || "",
        engineer_name:   c.engineer_name || "",
      });
      if (c.logo_path) setLogoUrl(c.logo_path + "?t=" + Date.now());
    }).finally(() => setLoading(false));
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await api.updateConfig({
        ...form,
        total_km:        parseFloat(form.total_km),
        daily_target_km: parseFloat(form.daily_target_km),
        start_date:      form.start_date || null,
      });
      toast.success("Configuration mise à jour");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleLogoChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoLoading(true);
    try {
      const res = await api.uploadLogo(file);
      setLogoUrl(res.logo_path + "?t=" + Date.now());
      toast.success("Logo importé");
    } catch (err) {
      toast.error(err.message || "Erreur lors de l'import du logo");
    } finally {
      setLogoLoading(false);
      e.target.value = "";
    }
  };

  const handleDeleteLogo = async () => {
    setLogoLoading(true);
    try {
      await api.deleteLogo();
      setLogoUrl("");
      toast.success("Logo supprimé");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLogoLoading(false);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div style={{ maxWidth: 560, display: "flex", flexDirection: "column", gap: 14 }}>

      {/* ── Logo ── */}
      <Card>
        <SectionTitle>Logo de l'organisme / entreprise</SectionTitle>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          {/* Preview */}
          <div style={{
            width: 120, height: 64,
            border: "1px dashed var(--border2)",
            borderRadius: 8,
            display: "flex", alignItems: "center", justifyContent: "center",
            background: "var(--surface2)",
            flexShrink: 0,
            overflow: "hidden",
          }}>
            {logoUrl
              ? <img src={logoUrl} alt="Logo" style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
              : <span style={{ fontSize: 11, color: "var(--text3)", textAlign: "center", padding: "0 8px" }}>Aucun logo</span>
            }
          </div>

          {/* Actions */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <input
              ref={fileRef}
              type="file"
              accept=".png,.jpg,.jpeg"
              style={{ display: "none" }}
              onChange={handleLogoChange}
            />
            <Btn
              size="sm"
              onClick={() => fileRef.current?.click()}
              disabled={logoLoading}
            >
              {logoLoading ? "Import…" : logoUrl ? "Changer le logo" : "Importer un logo"}
            </Btn>
            {logoUrl && (
              <Btn size="sm" variant="ghost" onClick={handleDeleteLogo} disabled={logoLoading}>
                Supprimer
              </Btn>
            )}
            <span style={{ fontSize: 11, color: "var(--text3)" }}>PNG ou JPG · affiché dans les PDFs</span>
          </div>
        </div>
      </Card>

      {/* ── Config card ── */}
      <Card>
        <SectionTitle>Configuration du projet</SectionTitle>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Input label="Nom du projet"
            value={form.project_name || ""}
            onChange={e => set("project_name", e.target.value)} />
          <Input label="Ingénieur responsable (Établi par...)"
            value={form.engineer_name || ""}
            onChange={e => set("engineer_name", e.target.value)}
            placeholder="ex : M. Dupont — Ingénieur Topographe" />
          <Input label="Localisation / Région"
            value={form.location || ""}
            onChange={e => set("location", e.target.value)}
            placeholder="ex : Mauritanie — Axe Nord-Sud" />
          <div className="form-grid-2col">
            <Input label="Longueur totale (km)" type="number" step="0.1"
              value={form.total_km || ""}
              onChange={e => set("total_km", e.target.value)} />
            <Input label="Objectif journalier (km)" type="number" step="0.5"
              value={form.daily_target_km || ""}
              onChange={e => set("daily_target_km", e.target.value)} />
          </div>
          <Input label="Date de début du chantier" type="date"
            value={form.start_date || ""}
            onChange={e => set("start_date", e.target.value)} />
        </div>
        <div style={{ marginTop: 18, display: "flex", justifyContent: "flex-end" }}>
          <Btn size="sm" onClick={save} disabled={saving}>
            {saving ? "Sauvegarde…" : "Sauvegarder les paramètres"}
          </Btn>
        </div>
      </Card>

      {/* ── System info ── */}
      <Card>
        <SectionTitle>À propos du système</SectionTitle>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { icon: "◈", title: "Méthode de levé",       detail: "Profils tous les 40 m · 3 points/couloir" },
            { icon: "⌁", title: "Couloir électrique MT",  detail: "Zone de servitude pour étude mécanique de la ligne" },
            { icon: "⬡", title: "Rapports PDF",           detail: "Journaliers (par rapport) et hebdomadaires (par semaine)" },
            { icon: "◫", title: "Base de données",        detail: "SQLite locale — sauvegarder en copiant topo.db" },
          ].map(({ icon, title, detail }) => (
            <div key={title} className="info-row">
              <span className="info-icon mono" style={{ color: "var(--accent)", fontSize: 16 }}>{icon}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{title}</div>
                <div style={{ fontSize: 11.5, color: "var(--text3)", marginTop: 2 }}>{detail}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

    </div>
  );
}
