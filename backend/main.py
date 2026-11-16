import os
import shutil
import tempfile
from fastapi import FastAPI, Depends, HTTPException, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional
import math

from database import DATA_DIR, engine, get_db
import models, schemas
from models import DailyReport, ProjectConfig
from pdf_gen import generate_daily_pdf, generate_weekly_pdf
from route_parser import list_routes, import_kmz as parse_import_kmz

UPLOAD_DIR = os.getenv("TOPO_UPLOAD_DIR", os.path.join(DATA_DIR, "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Init DB ────────────────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Levé Topo API", version="1.0.0")

# Comma-separated list, e.g. "https://topo.example.com". Default: local dev servers.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files (logo etc.)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def get_config(db: Session) -> ProjectConfig:
    cfg = db.query(ProjectConfig).first()
    if not cfg:
        cfg = ProjectConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


# ══════════════════════════════════════════════════════════════════════════
# PROJECT CONFIG
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/config", response_model=schemas.ProjectConfigOut)
def read_config(db: Session = Depends(get_db)):
    return get_config(db)


@app.patch("/api/config", response_model=schemas.ProjectConfigOut)
def update_config(payload: schemas.ProjectConfigUpdate, db: Session = Depends(get_db)):
    cfg = get_config(db)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return cfg


@app.post("/api/config/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a logo image (PNG/JPG). Stored as uploads/logo.<ext> and drawn in PDF headers."""
    ext = os.path.splitext(file.filename or "logo.png")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(400, "Format non supporté. Utilisez PNG ou JPG.")
    # Remove any existing logo
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith("logo."):
            os.remove(os.path.join(UPLOAD_DIR, f))
    dest = os.path.join(UPLOAD_DIR, f"logo{ext}")
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    # Save path in config
    cfg = get_config(db)
    cfg.logo_path = f"/uploads/logo{ext}"
    db.commit()
    db.refresh(cfg)
    return {"logo_path": cfg.logo_path}


@app.delete("/api/config/logo")
def delete_logo(db: Session = Depends(get_db)):
    """Remove the current logo."""
    cfg = get_config(db)
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith("logo."):
            os.remove(os.path.join(UPLOAD_DIR, f))
    cfg.logo_path = ""
    db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/stats", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db)):
    cfg = get_config(db)
    reports = db.query(DailyReport).all()

    km_done = max((r.kp_end for r in reports), default=0.0)
    km_remaining = max(0.0, cfg.total_km - km_done)
    pct = round(km_done / cfg.total_km * 100, 2) if cfg.total_km else 0
    days_worked = len(reports)
    avg = (km_done / days_worked) if days_worked else cfg.daily_target_km
    days_remaining = math.ceil(km_remaining / avg) if avg > 0 else 0
    total_points = sum(r.points_captured for r in reports)
    total_obstacles = sum(len(r.obstacles or []) for r in reports)

    return schemas.StatsOut(
        total_km=cfg.total_km,
        daily_target_km=cfg.daily_target_km,
        km_done=round(km_done, 3),
        km_remaining=round(km_remaining, 3),
        pct_done=pct,
        days_worked=days_worked,
        days_remaining_estimated=days_remaining,
        total_points=total_points,
        total_obstacles=total_obstacles,
        avg_km_per_day=round(avg, 2),
    )


# ══════════════════════════════════════════════════════════════════════════
# DAILY REPORTS — CRUD
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/reports", response_model=List[schemas.DailyReportOut])
def list_reports(
    skip: int = 0,
    limit: int = 200,
    year: Optional[int] = None,
    week: Optional[int] = None,
    db: Session = Depends(get_db)
):
    reports = db.query(DailyReport).order_by(DailyReport.date.desc()).all()
    # Filter by ISO year/week in Python: SQLite's strftime('%W') is not ISO-8601
    if year:
        reports = [r for r in reports if r.date.isocalendar()[0] == year]
    if week:
        reports = [r for r in reports if r.date.isocalendar()[1] == week]
    return [schemas.DailyReportOut.from_orm_ext(r) for r in reports[skip:skip + limit]]


@app.get("/api/reports/{report_id}", response_model=schemas.DailyReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    r = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    return schemas.DailyReportOut.from_orm_ext(r)


@app.post("/api/reports", response_model=schemas.DailyReportOut, status_code=201)
def create_report(payload: schemas.DailyReportCreate, db: Session = Depends(get_db)):
    existing = db.query(DailyReport).filter(DailyReport.date == payload.date).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Un rapport existe déjà pour le {payload.date}")
    data = payload.model_dump_for_db()
    r = DailyReport(**data)
    db.add(r)
    db.commit()
    db.refresh(r)
    return schemas.DailyReportOut.from_orm_ext(r)


@app.patch("/api/reports/{report_id}", response_model=schemas.DailyReportOut)
def update_report(report_id: int, payload: schemas.DailyReportUpdate, db: Session = Depends(get_db)):
    r = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    data = payload.model_dump(exclude_none=True)
    if "obstacles" in data:
        data["obstacles"] = [o.model_dump() for o in payload.obstacles]
    for k, v in data.items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return schemas.DailyReportOut.from_orm_ext(r)


@app.delete("/api/reports/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    r = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    db.delete(r)
    db.commit()


# ══════════════════════════════════════════════════════════════════════════
# WEEKS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/weeks")
def list_weeks(db: Session = Depends(get_db)):
    reports = db.query(DailyReport).order_by(DailyReport.date).all()
    weeks = {}
    for r in reports:
        yr, w = r.date.isocalendar()[:2]
        key = f"{yr}-W{w:02d}"
        if key not in weeks:
            weeks[key] = {"week": w, "year": yr, "key": key, "days": 0,
                          "km_total": 0.0, "obstacles": 0,
                          "date_start": str(r.date), "date_end": str(r.date)}
        weeks[key]["days"] += 1
        weeks[key]["km_total"] = round(weeks[key]["km_total"] + (r.kp_end - r.kp_start), 2)
        weeks[key]["obstacles"] += len(r.obstacles or [])
        weeks[key]["date_end"] = str(r.date)
    return list(reversed(list(weeks.values())))


# ══════════════════════════════════════════════════════════════════════════
# PDF EXPORT
# ══════════════════════════════════════════════════════════════════════════

def _logo_abs_path(cfg: ProjectConfig) -> Optional[str]:
    """Return absolute filesystem path to logo, or None."""
    if not cfg.logo_path:
        return None
    path = os.path.join(UPLOAD_DIR, os.path.basename(cfg.logo_path))
    return path if os.path.isfile(path) else None


@app.get("/api/reports/{report_id}/pdf")
def export_daily_pdf(report_id: int, db: Session = Depends(get_db)):
    r = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    cfg = get_config(db)
    reports = db.query(DailyReport).all()
    km_done = max((x.kp_end for x in reports), default=0.0)

    pdf_bytes = generate_daily_pdf(
        r, cfg.project_name, cfg.total_km, km_done,
        engineer_name=cfg.engineer_name or "",
        logo_path=_logo_abs_path(cfg),
        daily_target_km=cfg.daily_target_km,
    )
    filename = f"rapport_journalier_{r.date}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/api/weeks/{year}/{week}/pdf")
def export_weekly_pdf(year: int, week: int, db: Session = Depends(get_db)):
    reports = db.query(DailyReport).all()
    week_reports = [r for r in reports if tuple(r.date.isocalendar()[:2]) == (year, week)]
    if not week_reports:
        raise HTTPException(status_code=404, detail="Aucun rapport pour cette semaine")
    cfg = get_config(db)
    km_done = max((r.kp_end for r in reports), default=0.0)

    pdf_bytes = generate_weekly_pdf(
        week_reports, week, cfg.project_name, cfg.total_km, km_done, cfg.daily_target_km,
        engineer_name=cfg.engineer_name or "",
        logo_path=_logo_abs_path(cfg),
    )
    filename = f"rapport_hebdo_{year}_S{week:02d}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ══════════════════════════════════════════════════════════════════════════
# ROUTES (KMZ)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/routes")
def get_routes():
    """List all imported KMZ routes with metadata."""
    return list_routes()


@app.post("/api/routes/import")
async def import_route_kmz(file: UploadFile = File(...)):
    """Upload and import a KMZ file as a route."""
    ext = os.path.splitext(file.filename or "route.kmz")[1].lower()
    if ext not in (".kmz", ".kml"):
        raise HTTPException(400, "Format non supporté. Utilisez KMZ ou KML.")
    # Write to a private temp dir under a safe name; the route keeps the original stem
    stem = os.path.splitext(os.path.basename(file.filename or "route"))[0] or "route"
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = os.path.join(tmp_dir, "upload" + ext)
        with open(tmp, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)
        result = parse_import_kmz(tmp, name=stem)
    if not result["points"]:
        raise HTTPException(422, "Aucune géométrie trouvée dans le fichier.")
    return result


@app.get("/health")
def health():
    return {"status": "ok"}
