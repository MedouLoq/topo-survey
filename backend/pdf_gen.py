"""
Levé Topo — PDF generation (ReportLab)

Terminology:
  Rapport Journalier   = daily field report   (one per working day)
  Rapport Hebdomadaire = weekly summary report (one per ISO week)

Fonts: DejaVu Sans (system TTF) for full Unicode support (weather, symbols, etc.)
"""
import os
import math
import urllib.request
from io import BytesIO
from typing import Optional, List, Tuple

from PIL import Image as PILImage, ImageDraw as PILDraw

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Register DejaVu TrueType fonts (full Unicode support) ─────────────────
_FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_FONTS_OK = False
try:
    pdfmetrics.registerFont(TTFont("DV",     os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DV-B",   os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DV-M",   os.path.join(_FONT_DIR, "DejaVuSansMono.ttf")))
    pdfmetrics.registerFont(TTFont("DV-MB",  os.path.join(_FONT_DIR, "DejaVuSansMono-Bold.ttf")))
    _FONTS_OK = True
except Exception:
    pass  # Fall back to Helvetica if fonts missing

F_BODY  = "DV"    if _FONTS_OK else "Helvetica"
F_BOLD  = "DV-B"  if _FONTS_OK else "Helvetica-Bold"
F_MONO  = "DV-M"  if _FONTS_OK else "Courier"
F_MONOB = "DV-MB" if _FONTS_OK else "Courier-Bold"

PAGE_W, PAGE_H = A4
M_L = 2.0 * cm
M_R = 2.0 * cm
M_T = 3.2 * cm
M_B = 2.0 * cm
CW  = PAGE_W - M_L - M_R   # usable content width ≈ 171 mm

# ── Colour palette (print-optimised, white background) ────────────────────
C_NAVY    = colors.HexColor("#0f2545")
C_BLUE    = colors.HexColor("#1d4ed8")
C_CYAN    = colors.HexColor("#0891b2")
C_GREEN   = colors.HexColor("#15803d")
C_AMBER   = colors.HexColor("#b45309")
C_RED     = colors.HexColor("#b91c1c")
C_TEXT    = colors.HexColor("#1e293b")
C_TEXT2   = colors.HexColor("#475569")
C_TEXT3   = colors.HexColor("#94a3b8")
C_BG_ROW  = colors.HexColor("#f8fafc")
C_BORDER  = colors.HexColor("#e2e8f0")
C_WHITE   = colors.white
C_HDR_ROW = colors.HexColor("#0f2545")

def weather_label(w: str) -> str:
    """Weather as plain text (emoji icons are not in DejaVu and render as empty boxes)."""
    return w or "—"


# French names, independent of the server locale
_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre"]


def fr_long_date(d) -> str:
    """lundi 16 mars 2026"""
    return f"{_JOURS[d.weekday()]} {d.day} {_MOIS[d.month - 1]} {d.year}"


def fr_short_day(d) -> str:
    """Lun 16/03"""
    return f"{_JOURS[d.weekday()][:3].capitalize()} {d:%d/%m}"


# ── Paragraph styles ──────────────────────────────────────────────────────
def _styles():
    def ps(name, **kw):
        params = {"fontName": F_BODY, "textColor": C_TEXT}
        params.update(kw)
        return ParagraphStyle(name, **params)

    return {
        "doc_title": ps("dt",  fontSize=20, fontName=F_BOLD,
                        textColor=C_NAVY, leading=26, spaceAfter=3),
        "doc_sub":   ps("ds",  fontSize=10.5, textColor=C_TEXT2, leading=15, spaceAfter=14),
        "meta_lbl":  ps("ml",  fontSize=7,  fontName=F_BOLD,
                        textColor=C_TEXT3, leading=10),
        "meta_val":  ps("mv",  fontSize=10, textColor=C_TEXT, leading=14),
        "section":   ps("sec", fontSize=8.5, fontName=F_BOLD,
                        textColor=C_NAVY, spaceBefore=16, spaceAfter=6,
                        textTransform="uppercase", letterSpacing=0.8),
        "body":      ps("body", fontSize=9.5, leading=15, spaceAfter=4),
        "body2":     ps("b2",   fontSize=9,   textColor=C_TEXT2, leading=14, spaceAfter=3),
        "ok":        ps("ok",   fontSize=9.5, textColor=C_GREEN, leading=14),
        "warn":      ps("wn",   fontSize=9.5, textColor=C_AMBER, leading=15, leftIndent=10),
        "note":      ps("nt",   fontSize=9.5, textColor=C_TEXT2, leading=15,
                        backColor=colors.HexColor("#f0f9ff"),
                        borderLeftWidth=3, borderLeftColor=C_CYAN,
                        borderPad=8, spaceAfter=4),
        "synth":     ps("sy",   fontSize=9.5, textColor=C_TEXT2, leading=16,
                        backColor=C_BG_ROW,
                        borderLeftWidth=3, borderLeftColor=C_BLUE,
                        borderPad=10),
        "kpi_val":   ps("kv",  fontSize=18, fontName=F_BOLD,
                        textColor=C_NAVY, leading=22),
        "kpi_lbl":   ps("kl",  fontSize=7,  fontName=F_BOLD,
                        textColor=C_TEXT3, leading=10),
        "kpi_sub":   ps("ks",  fontSize=8,  textColor=C_TEXT2, leading=11),
        "footer":    ps("ft",  fontSize=7,  textColor=C_TEXT3, alignment=1),
        "coords":    ps("co",  fontSize=8,  fontName=F_MONO, textColor=C_TEXT2, leading=12),
        "signed":    ps("sg",  fontSize=9,  textColor=C_TEXT2, leading=14),
    }


# ── Page template: header band + logo + footer ────────────────────────────
def _page_canvas(canvas, doc, project: str, report_type: str,
                 logo_path: Optional[str] = None,
                 engineer_name: str = ""):
    canvas.saveState()

    band = 2.2 * cm
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, PAGE_H - band, PAGE_W, band, fill=1, stroke=0)

    canvas.setStrokeColor(C_CYAN)
    canvas.setLineWidth(2)
    canvas.line(0, PAGE_H - band, PAGE_W, PAGE_H - band)

    # Logo (top-left inside band)
    if logo_path and os.path.isfile(logo_path):
        try:
            logo_h = band * 0.72
            logo_w = logo_h * 2.5   # assume max 2.5:1 ratio; ReportLab will scale
            canvas.drawImage(
                logo_path,
                M_L, PAGE_H - band + (band - logo_h) / 2,
                width=logo_w, height=logo_h,
                preserveAspectRatio=True, mask="auto",
            )
            text_x = M_L + logo_w + 8
        except Exception:
            text_x = M_L
    else:
        text_x = M_L

    # Project name
    canvas.setFont(F_BOLD, 9.5)
    canvas.setFillColor(C_WHITE)
    canvas.drawString(text_x, PAGE_H - 1.35 * cm, project.upper())

    # Report type (right)
    canvas.setFont(F_BODY, 8)
    canvas.setFillColor(colors.HexColor("#7dd3fc"))
    canvas.drawRightString(PAGE_W - M_R, PAGE_H - 1.35 * cm, report_type)

    # Footer rule
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(M_L, 1.5 * cm, PAGE_W - M_R, 1.5 * cm)

    # Footer text
    canvas.setFont(F_BODY, 7)
    canvas.setFillColor(C_TEXT3)
    footer_parts = [f"Levé Topographique MT  ·  Page {doc.page}"]
    if engineer_name:
        footer_parts.insert(0, f"Établi par : {engineer_name}")
    canvas.drawCentredString(PAGE_W / 2, 1.0 * cm, "    |    ".join(footer_parts))

    canvas.restoreState()


def _doc(buffer, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=M_L, rightMargin=M_R,
        topMargin=M_T, bottomMargin=M_B + 0.5 * cm,
        title=title,
        author="Système Levé Topo",
    )


# ── Progress bar ──────────────────────────────────────────────────────────
def _progress_bar(pct: float) -> Drawing:
    h = 16
    d = Drawing(CW, h + 8)
    d.add(Rect(0, 4, CW, h,
               fillColor=C_BG_ROW, strokeColor=C_BORDER, strokeWidth=0.5))
    fill = max(h, min(CW, pct / 100 * CW))
    fill_col = C_GREEN if pct >= 75 else (C_BLUE if pct >= 40 else C_AMBER)
    d.add(Rect(0, 4, fill, h, fillColor=fill_col, strokeColor=None))
    lx     = fill / 2
    lcolor = C_WHITE if pct > 22 else C_TEXT
    d.add(String(lx, 8, f"{pct:.1f}%",
                 fontSize=7.5, fontName=F_MONOB,
                 fillColor=lcolor, textAnchor="middle"))
    return d


# ── KPI row ───────────────────────────────────────────────────────────────
def _kpi_table(kpis, st):
    n    = len(kpis)
    colw = CW / n
    top, lbl, sub = [], [], []
    for val, label, subsub, col in kpis:
        hex_col = col[1:] if col else "0f2545"
        top.append(Paragraph(f'<font color="#{hex_col}">{val}</font>', st["kpi_val"]))
        lbl.append(Paragraph(label.upper(), st["kpi_lbl"]))
        sub.append(Paragraph(subsub or "", st["kpi_sub"]))
    t = Table([top, lbl, sub], colWidths=[colw] * n)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_WHITE),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING",    (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 2), (-1, 2), 12),
    ]))
    return t


def _section_divider(els, label, st):
    els.append(Paragraph(label, st["section"]))
    els.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER,
                          spaceBefore=0, spaceAfter=8))


def _data_table(data, col_widths, extra_styles=None):
    t = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0), C_HDR_ROW),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), F_BOLD),
        ("FONTSIZE",      (0, 0), (-1, 0), 7.5),
        ("TOPPADDING",    (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("TEXTCOLOR",     (0, 1), (-1, -1), C_TEXT),
        ("TOPPADDING",    (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_BG_ROW]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME",      (0, 1), (-1, -1), F_BODY),
    ]
    if extra_styles:
        style.extend(extra_styles)
    t.setStyle(TableStyle(style))
    return t


def fmt_coord(lat: float, lon: float) -> str:
    """6-decimal coordinates with hemisphere letters, e.g. 16.123456° N, 12.345678° W."""
    return (f"{abs(lat):.6f}° {'N' if lat >= 0 else 'S'}, "
            f"{abs(lon):.6f}° {'E' if lon >= 0 else 'W'}")


# ── Tile-based map (OSM tiles + Pillow) ──────────────────────────────────
# Tiles © OpenStreetMap contributors (ODbL). Follow the tile usage policy:
# https://operations.osmfoundation.org/policies/tiles/ — set a User-Agent that
# identifies your deployment, or point MAP_TILE_URL at your own tile server.
MAP_TILES_ENABLED = os.getenv("MAP_TILES", "on").lower() not in ("0", "off", "false")
MAP_TILE_URL = os.getenv("MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
MAP_USER_AGENT = os.getenv("MAP_USER_AGENT", "topo-survey/1.0 (self-hosted field reporting app)")
OSM_ATTRIBUTION = "Fond de carte © contributeurs OpenStreetMap"
_TILE_PX = 256

def _merc_y_frac(lat_deg: float) -> float:
    """Web-Mercator Y as fraction [0,1]."""
    r = math.radians(lat_deg)
    return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2

def _tile_xy(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int(_merc_y_frac(lat) * n)
    return x, y

def _latlon_to_px(lat: float, lon: float,
                  x0: int, y0: int, zoom: int) -> Tuple[int, int]:
    n = 2 ** zoom
    fx = (lon + 180) / 360 * n
    fy = _merc_y_frac(lat) * n
    return int((fx - x0) * _TILE_PX), int((fy - y0) * _TILE_PX)

def _fetch_tile(x: int, y: int, zoom: int) -> Optional[PILImage.Image]:
    if not MAP_TILES_ENABLED:
        return None
    url = MAP_TILE_URL.format(z=zoom, x=x, y=y)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": MAP_USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as r:
            return PILImage.open(BytesIO(r.read())).convert("RGB")
    except Exception:
        return None

def _build_map_image(markers: List[Tuple[float, float]],
                     routes: Optional[List[List[Tuple[float, float]]]] = None,
                     out_w: int = 700, out_h: int = 280) -> Optional[PILImage.Image]:
    """
    Stitch OSM tiles, draw planned route (gray) + today's track (cyan) + markers.
    markers: [(lat,lon), ...]  — first=start (blue), last=end (red)
    routes: planned route polylines, each [(lat,lon), ...]
    """
    if not markers:
        return None

    all_lats = [p[0] for p in markers]
    all_lons = [p[1] for p in markers]
    route_points = [p for r in (routes or []) for p in r]
    if route_points:
        sample = route_points[::max(1, len(route_points) // 200)]
        all_lats += [p[0] for p in sample]
        all_lons += [p[1] for p in sample]

    min_lat, max_lat = min(all_lats), max(all_lats)
    min_lon, max_lon = min(all_lons), max(all_lons)

    pad = max(0.015, max(max_lat - min_lat, max_lon - min_lon) * 0.25)
    min_lat -= pad; max_lat += pad
    min_lon -= pad; max_lon += pad

    # Pick zoom so we get 2–9 tiles
    span = max(max_lat - min_lat, max_lon - min_lon)
    if   span < 0.02: zoom = 14
    elif span < 0.08: zoom = 12
    elif span < 0.4:  zoom = 10
    elif span < 1.5:  zoom = 9
    elif span < 4:    zoom = 8
    else:             zoom = 7

    x0, y0 = _tile_xy(max_lat, min_lon, zoom)
    x1, y1 = _tile_xy(min_lat, max_lon, zoom)
    x0 = max(0, x0 - 1);  x1 = min(2 ** zoom - 1, x1 + 1)
    y0 = max(0, y0 - 1);  y1 = min(2 ** zoom - 1, y1 + 1)

    # Cap tile count
    while (x1 - x0 + 1) * (y1 - y0 + 1) > 12 and zoom > 6:
        zoom -= 1
        x0, y0 = _tile_xy(max_lat, min_lon, zoom)
        x1, y1 = _tile_xy(min_lat, max_lon, zoom)
        x0 = max(0, x0 - 1);  x1 = min(2 ** zoom - 1, x1 + 1)
        y0 = max(0, y0 - 1);  y1 = min(2 ** zoom - 1, y1 + 1)

    cw = (x1 - x0 + 1) * _TILE_PX
    ch = (y1 - y0 + 1) * _TILE_PX
    canvas = PILImage.new("RGB", (cw, ch), (220, 220, 220))

    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            tile = _fetch_tile(tx, ty, zoom)
            if tile:
                canvas.paste(tile, ((tx - x0) * _TILE_PX, (ty - y0) * _TILE_PX))

    draw = PILDraw.Draw(canvas, "RGBA")

    def px(lat, lon):
        return _latlon_to_px(lat, lon, x0, y0, zoom)

    # Planned route — semi-transparent gray
    for route in routes or []:
        if len(route) > 1:
            draw.line([px(lat, lon) for lat, lon in route], fill=(80, 80, 80, 160), width=3, joint="curve")

    # Today's track — cyan line
    if len(markers) >= 2:
        p1 = px(*markers[0])
        p2 = px(*markers[-1])
        draw.line([p1, p2], fill=(0, 180, 220, 230), width=5)

    # Markers
    r = 9
    marker_colors = [(30, 120, 255), (210, 40, 40)]
    for i, (lat, lon) in enumerate(markers):
        cx, cy = px(lat, lon)
        col = marker_colors[min(i, len(marker_colors) - 1)]
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=col + (255,), outline=(255, 255, 255, 255))

    # Crop tightly around markers with padding
    if markers:
        pxs = [px(*m) for m in markers]
        mx0 = max(0,  min(p[0] for p in pxs) - 80)
        my0 = max(0,  min(p[1] for p in pxs) - 60)
        mx1 = min(cw, max(p[0] for p in pxs) + 80)
        my1 = min(ch, max(p[1] for p in pxs) + 60)
        if mx1 - mx0 < 180: mid = (mx0 + mx1) // 2; mx0 = max(0, mid - 120); mx1 = min(cw, mid + 120)
        if my1 - my0 < 100: mid = (my0 + my1) // 2; my0 = max(0, mid - 70);  my1 = min(ch, mid + 70)
        canvas = canvas.crop((mx0, my0, mx1, my1))

    canvas = canvas.resize((out_w, out_h), PILImage.LANCZOS)
    return canvas


def _map_to_rl_image(markers, routes=None, width_pts=None):
    """Build OSM tile map and return as a ReportLab Image flowable."""
    if not MAP_TILES_ENABLED:
        return None
    if routes is None:
        try:
            from route_parser import load_all_routes
            routes = load_all_routes() or None
        except Exception:
            routes = None

    img = _build_map_image(markers, routes)
    if img is None:
        return None
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    aspect = img.height / img.width
    w = width_pts or CW
    from reportlab.platypus import Image as RLImage
    return RLImage(buf, width=w, height=w * aspect)


# ══════════════════════════════════════════════════════════════════════════
#  RAPPORT JOURNALIER
# ══════════════════════════════════════════════════════════════════════════
def generate_daily_pdf(report, project_name: str,
                       total_km: float, km_done_total: float,
                       engineer_name: str = "",
                       logo_path: Optional[str] = None,
                       daily_target_km: float = 10.0) -> bytes:
    buffer = BytesIO()
    doc    = _doc(buffer, f"Rapport Journalier {report.date}")
    st     = _styles()
    els    = []

    date_str = fr_long_date(report.date) if hasattr(report.date, "weekday") else str(report.date)
    km_day   = round(report.kp_end - report.kp_start, 2)
    pct      = round(km_done_total / total_km * 100, 1) if total_km else 0
    target   = daily_target_km

    # Normalize obstacles
    raw_obs  = report.obstacles or []
    obstacles = []
    for o in raw_obs:
        if isinstance(o, str):
            obstacles.append({"name": o, "kp": None})
        elif isinstance(o, dict):
            obstacles.append(o)
        else:
            try:
                obstacles.append({"name": o.name, "kp": o.kp})
            except Exception:
                obstacles.append({"name": str(o), "kp": None})

    # ── Header block ──────────────────────────────────────────────────────
    els.append(Spacer(1, 0.3 * cm))
    els.append(Paragraph("Rapport Journalier", st["doc_title"]))
    els.append(Paragraph(date_str.capitalize(), st["doc_sub"]))

    if engineer_name:
        els.append(Paragraph(
            f'<font name="{F_BOLD}">Établi par :</font>  {engineer_name}',
            st["signed"]))
        els.append(Spacer(1, 4))

    els.append(HRFlowable(width="100%", thickness=1.5, color=C_BLUE, spaceAfter=16))

    # ── KPIs ──────────────────────────────────────────────────────────────
    km_col = "#15803d" if km_day >= target else "#b91c1c"
    els.append(_kpi_table([
        (f"{km_day:.2f} km",          "Levé du jour",    f"Objectif : {target:.0f} km", km_col),
        (f"{km_done_total:.1f} km",   "Cumul total",     f"Sur {total_km:.0f} km",      "#1d4ed8"),
        (f"{pct}%",                   "Avancement",      "Progression globale",         "#1d4ed8"),
        (str(report.points_captured), "Points levés",    "Profils 40m · 3pts/col.",     "#7c3aed"),
    ], st))
    els.append(Spacer(1, 14))

    # ── Progression ───────────────────────────────────────────────────────
    _section_divider(els, "Progression du tracé", st)
    els.append(_progress_bar(pct))
    els.append(Spacer(1, 6))
    els.append(Paragraph(
        f"Position actuelle : KP {report.kp_start} → KP {report.kp_end}   "
        f"Reste à lever : {round(total_km - km_done_total, 1)} km",
        st["body2"]))

    # ── Détails journée ───────────────────────────────────────────────────
    _section_divider(els, "Détails de la journée", st)
    density = f"{round(report.points_captured / km_day):.0f} pts/km" if km_day > 0 else "—"
    rows = [
        ["Paramètre",             "Valeur"],
        ["Date",                  date_str.capitalize()],
        ["KP Début",              f"{report.kp_start} km"],
        ["KP Fin",                f"{report.kp_end} km"],
        ["Kilomètres levés",      f"{km_day:.2f} km"],
        ["Points topographiques", str(report.points_captured)],
        ["Densité de mesure",     density],
        ["Effectif terrain",      f"{report.crew_count} personnes"],
        ["Météo",                 weather_label(report.weather)],
    ]
    # GPS coords rows
    has_gps = any([report.kp_start_lat, report.kp_start_lon,
                   report.kp_end_lat, report.kp_end_lon])
    if has_gps:
        if report.kp_start_lat is not None:
            rows.append(["Coordonnées début",
                         fmt_coord(report.kp_start_lat, report.kp_start_lon)])
        if report.kp_end_lat is not None:
            rows.append(["Coordonnées fin",
                         fmt_coord(report.kp_end_lat, report.kp_end_lon)])

    els.append(_data_table(rows, [CW * 0.42, CW * 0.58]))

    # ── Map (if GPS available) ─────────────────────────────────────────────
    if None not in (report.kp_start_lat, report.kp_start_lon,
                    report.kp_end_lat, report.kp_end_lon):
        _section_divider(els, "Localisation du tracé journalier", st)
        map_img = _map_to_rl_image(
            markers=[(report.kp_start_lat, report.kp_start_lon),
                     (report.kp_end_lat,   report.kp_end_lon)],
            width_pts=CW,
        )
        if map_img:
            els.append(map_img)
            els.append(Spacer(1, 4))
            els.append(Paragraph(
                "Bleu = point de départ (KP début)   Rouge = point d'arrivée (KP fin)   "
                "Gris = tracé planifié complet   ·   " + OSM_ATTRIBUTION,
                st["body2"]))
        else:
            els.append(Paragraph(
                f"Début : {fmt_coord(report.kp_start_lat, report.kp_start_lon)}  —  "
                f"Fin : {fmt_coord(report.kp_end_lat, report.kp_end_lon)}",
                st["coords"]))

    # ── Obstacles ─────────────────────────────────────────────────────────
    _section_divider(els, "Obstacles & contraintes identifiés", st)
    if obstacles:
        for o in obstacles:
            name = o.get("name", str(o))
            kp   = o.get("kp")
            kp_str = f"  [KP {kp:.2f} km]" if kp is not None else ""
            els.append(Paragraph(f"►  {name}{kp_str}", st["warn"]))
            els.append(Spacer(1, 2))
    else:
        els.append(Paragraph("Aucun obstacle identifié ce jour.", st["ok"]))

    # ── Note ingénieur ────────────────────────────────────────────────────
    _section_divider(els, "Note de l'ingénieur", st)
    note = (report.eng_note or "").strip() or "Aucune note renseignée."
    els.append(Paragraph(note, st["note"]))

    # ── Signature block ───────────────────────────────────────────────────
    if engineer_name:
        els.append(Spacer(1, 20))
        sig_data = [
            [Paragraph(f"Établi par :", st["meta_lbl"]),
             Paragraph("Visa / Approbation :", st["meta_lbl"])],
            [Paragraph(f'<font name="{F_BOLD}">{engineer_name}</font>', st["meta_val"]),
             Paragraph("", st["meta_val"])],
        ]
        sig_t = Table(sig_data, colWidths=[CW * 0.5, CW * 0.5])
        sig_t.setStyle(TableStyle([
            ("BOX",         (0, 0), (-1, -1), 0.5, C_BORDER),
            ("INNERGRID",   (0, 0), (-1, -1), 0.5, C_BORDER),
            ("TOPPADDING",  (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ]))
        els.append(sig_t)

    def _footer(c, d):
        _page_canvas(c, d, project_name, "RAPPORT JOURNALIER",
                     logo_path=logo_path, engineer_name=engineer_name)

    doc.build(els, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════════════════
#  RAPPORT HEBDOMADAIRE
# ══════════════════════════════════════════════════════════════════════════
def generate_weekly_pdf(reports: list, week_num: int, project_name: str,
                        total_km: float, km_done_total: float,
                        target_per_day: float = 10.0,
                        engineer_name: str = "",
                        logo_path: Optional[str] = None) -> bytes:
    buffer   = BytesIO()
    sorted_r = sorted(reports, key=lambda r: r.date)
    if not sorted_r:
        buffer.write(b"%PDF empty"); return buffer.getvalue()

    d1  = sorted_r[0].date.strftime("%d/%m/%Y")
    d2  = sorted_r[-1].date.strftime("%d/%m/%Y")
    doc = _doc(buffer, f"Rapport Hebdomadaire S{week_num}")
    st  = _styles()
    els = []

    km_week  = sum(r.kp_end - r.kp_start for r in sorted_r)
    pts_week = sum(r.points_captured for r in sorted_r)
    days     = len(sorted_r)
    pct      = round(km_done_total / total_km * 100, 1) if total_km else 0
    obj_wk   = target_per_day * days
    avg      = km_week / days if days else 0
    on_track = km_week >= obj_wk

    # Normalize all obstacles with date
    obs_all = []
    for r in sorted_r:
        for o in (r.obstacles or []):
            if isinstance(o, str):
                obs_all.append((r.date, o, None))
            elif isinstance(o, dict):
                obs_all.append((r.date, o.get("name", ""), o.get("kp")))
            else:
                try:
                    obs_all.append((r.date, o.name, o.kp))
                except Exception:
                    obs_all.append((r.date, str(o), None))

    # ── Header block ──────────────────────────────────────────────────────
    els.append(Spacer(1, 0.3 * cm))
    els.append(Paragraph("Rapport Hebdomadaire", st["doc_title"]))
    els.append(Paragraph(f"Semaine {week_num}  ·  {d1} – {d2}", st["doc_sub"]))

    if engineer_name:
        els.append(Paragraph(
            f'<font name="{F_BOLD}">Établi par :</font>  {engineer_name}',
            st["signed"]))
        els.append(Spacer(1, 4))

    els.append(HRFlowable(width="100%", thickness=1.5, color=C_BLUE, spaceAfter=16))

    # ── KPIs ──────────────────────────────────────────────────────────────
    km_col = "#15803d" if on_track else "#b45309"
    els.append(_kpi_table([
        (f"{km_week:.1f} km",  "Levé hebdomadaire", f"Objectif : {obj_wk:.0f} km",            km_col),
        (str(days),             "Jours travaillés",  "Journées de terrain",                    "#1d4ed8"),
        (str(pts_week),         "Points relevés",    f"Moy. {round(pts_week/days) if days else 0}/j", "#7c3aed"),
        (str(len(obs_all)),     "Obstacles",         "Contraintes identifiées",
         "#b45309" if obs_all else "#15803d"),
    ], st))
    els.append(Spacer(1, 14))

    # ── Avancement global ─────────────────────────────────────────────────
    _section_divider(els, "Avancement global du projet", st)
    els.append(_progress_bar(pct))
    els.append(Spacer(1, 6))
    els.append(Paragraph(
        f"Total levé : {km_done_total:.1f} km / {total_km:.0f} km   "
        f"Reste : {total_km - km_done_total:.1f} km   "
        f"Moyenne journalière : {avg:.1f} km/jour",
        st["body2"]))

    # ── Détail journalier ─────────────────────────────────────────────────
    _section_divider(els, "Détail journalier de la semaine", st)
    headers = [["Date", "KP Début", "KP Fin", "Km levés", "Points", "Météo", "Obs."]]
    body    = []
    extra   = []
    for i, r in enumerate(sorted_r, 1):
        km_r = round(r.kp_end - r.kp_start, 2)
        obs  = len(r.obstacles or [])
        body.append([
            fr_short_day(r.date),
            f"{r.kp_start}", f"{r.kp_end}",
            f"{km_r:.2f}", str(r.points_captured),
            weather_label(r.weather),
            f"{obs} (!)" if obs else "OK",
        ])
        c = C_GREEN if km_r >= target_per_day else C_RED
        extra += [
            ("TEXTCOLOR", (3, i), (3, i), c),
            ("FONTNAME",  (3, i), (3, i), F_BOLD),
        ]
        if obs:
            extra.append(("TEXTCOLOR", (6, i), (6, i), C_AMBER))

    cw = [CW * x for x in [0.14, 0.10, 0.10, 0.12, 0.10, 0.29, 0.15]]
    els.append(_data_table(headers + body, cw, extra))

    # ── Obstacles ─────────────────────────────────────────────────────────
    _section_divider(els, "Obstacles & contraintes identifiés", st)
    if obs_all:
        obs_hdr  = [["Date", "KP", "Contrainte identifiée"]]
        obs_rows = []
        obs_extra = []
        for idx, (d, name, kp) in enumerate(obs_all, 1):
            kp_str = f"{kp:.2f} km" if kp is not None else "—"
            obs_rows.append([d.strftime("%d/%m"), kp_str, name])
            obs_extra.append(("TEXTCOLOR", (0, idx), (-1, idx), C_AMBER))
        els.append(_data_table(obs_hdr + obs_rows,
                               [CW * 0.11, CW * 0.14, CW * 0.75], obs_extra))
    else:
        els.append(Paragraph("Aucun obstacle identifié durant cette semaine.", st["ok"]))

    # ── Map (weekly: use first start → last end GPS) ───────────────────────
    gps_starts = [(r.kp_start_lat, r.kp_start_lon) for r in sorted_r
                  if r.kp_start_lat is not None and r.kp_start_lon is not None]
    gps_ends   = [(r.kp_end_lat, r.kp_end_lon) for r in sorted_r
                  if r.kp_end_lat is not None and r.kp_end_lon is not None]
    if gps_starts and gps_ends:
        lat1, lon1 = gps_starts[0]
        lat2, lon2 = gps_ends[-1]
        _section_divider(els, "Localisation du tracé hebdomadaire", st)
        # Build list of all GPS points this week for the track
        all_markers = [gps_starts[0]] + gps_ends
        map_img = _map_to_rl_image(markers=all_markers, width_pts=CW)
        if map_img:
            els.append(map_img)
            els.append(Spacer(1, 4))
            els.append(Paragraph(
                "Bleu = départ semaine   Rouge = fin de semaine   Gris = tracé planifié complet"
                "   ·   " + OSM_ATTRIBUTION,
                st["body2"]))
        else:
            els.append(Paragraph(
                f"Départ : {fmt_coord(lat1, lon1)}  —  Fin : {fmt_coord(lat2, lon2)}",
                st["coords"]))

    # ── Notes ingénieur ───────────────────────────────────────────────────
    notes = [(r.date, r.eng_note) for r in sorted_r if r.eng_note and r.eng_note.strip()]
    if notes:
        _section_divider(els, "Notes de l'ingénieur", st)
        for d, note in notes:
            els.append(Paragraph(f"<b>{d.strftime('%d/%m')}</b>  —  {note}", st["note"]))
            els.append(Spacer(1, 4))

    # ── Synthèse ──────────────────────────────────────────────────────────
    _section_divider(els, "Synthèse hebdomadaire", st)
    ecart = (
        f"L'objectif hebdomadaire de {obj_wk:.0f} km a été atteint (+{km_week - obj_wk:.1f} km)."
        if on_track else
        f"Écart de {obj_wk - km_week:.1f} km par rapport à l'objectif de {obj_wk:.0f} km."
    )
    obs_str = (
        f"{len(obs_all)} contrainte(s) identifiées et documentées pour l'étude mécanique."
        if obs_all else
        "Aucune contrainte majeure identifiée durant cette semaine."
    )
    synth = (
        f"Durant la semaine {week_num} ({d1} – {d2}), l'équipe a réalisé un levé de "
        f"{km_week:.1f} km sur {days} journée(s), capturant {pts_week} points "
        f"topographiques (profils 40 m, 3 pts/couloir). "
        f"Moyenne journalière : {avg:.1f} km/jour. "
        f"{ecart} {obs_str}"
    )
    els.append(Paragraph(synth, st["synth"]))
    els.append(Spacer(1, 10))

    # ── Signature block ───────────────────────────────────────────────────
    if engineer_name:
        els.append(Spacer(1, 16))
        sig_data = [
            [Paragraph("Établi par :", st["meta_lbl"]),
             Paragraph("Visa / Approbation :", st["meta_lbl"])],
            [Paragraph(f'<font name="{F_BOLD}">{engineer_name}</font>', st["meta_val"]),
             Paragraph("", st["meta_val"])],
        ]
        sig_t = Table(sig_data, colWidths=[CW * 0.5, CW * 0.5])
        sig_t.setStyle(TableStyle([
            ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, C_BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ]))
        els.append(sig_t)

    def _footer(c, d):
        _page_canvas(c, d, project_name, f"RAPPORT HEBDOMADAIRE — SEMAINE {week_num}",
                     logo_path=logo_path, engineer_name=engineer_name)

    doc.build(els, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
