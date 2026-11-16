const BASE = import.meta.env.VITE_API_BASE || "/api";

async function req(method, path, body) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erreur serveur");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // config
  getConfig: () => req("GET", "/config"),
  updateConfig: (data) => req("PATCH", "/config", data),

  // logo
  uploadLogo: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${BASE}/config/logo`, {
      method: "POST",
      body: fd,
    });
    if (r.ok) return r.json();
    // Try to parse JSON error, fall back to status text
    const text = await r.text().catch(() => "");
    let msg = `Erreur ${r.status}`;
    try { msg = JSON.parse(text).detail || msg; } catch {}
    throw new Error(msg);
  },
  deleteLogo: () => req("DELETE", "/config/logo"),

  // stats
  getStats: () => req("GET", "/stats"),

  // reports
  listReports: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return req("GET", `/reports${q ? "?" + q : ""}`);
  },
  getReport: (id) => req("GET", `/reports/${id}`),
  createReport: (data) => req("POST", "/reports", data),
  updateReport: (id, data) => req("PATCH", `/reports/${id}`, data),
  deleteReport: (id) => req("DELETE", `/reports/${id}`),

  // weeks
  listWeeks: () => req("GET", "/weeks"),

  // PDF
  dailyPdfUrl: (id) => `${BASE}/reports/${id}/pdf`,
  weeklyPdfUrl: (year, week) => `${BASE}/weeks/${year}/${week}/pdf`,
};
