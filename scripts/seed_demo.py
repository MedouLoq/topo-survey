"""Fill a fresh database with a fictional demo project.

Everything here is invented: the route is a synthetic polyline, the project,
engineer and logo are placeholders, and the daily reports are generated.

    cd backend && TOPO_DATA_DIR=../demo-data python ../scripts/seed_demo.py
"""
import math
import os
import random
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from database import DATA_DIR, Base, SessionLocal, engine  # noqa: E402
from models import DailyReport, ProjectConfig  # noqa: E402
from route_parser import import_kmz  # noqa: E402

random.seed(42)
SAMPLES = ROOT / "samples"
TOTAL_KM = 60.0

# ── 1. Synthetic route: a gently curving ~60 km line ────────────────
START = (18.02, -15.80)   # arbitrary origin; the line itself is fictional


def synthetic_route(n=240):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        lat = START[0] + 0.30 * t + 0.035 * math.sin(t * 5.5)
        lon = START[1] + 0.42 * t + 0.025 * math.sin(t * 9.0 + 1.0)
        pts.append((lat, lon))
    return pts


def write_kmz(coords, path):
    coord_txt = " ".join(f"{lon:.6f},{lat:.6f},0" for lat, lon in coords)
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Tracé démo</name>
<Placemark><name>Ligne MT démo</name><LineString><coordinates>{coord_txt}</coordinates></LineString></Placemark>
</Document></kml>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)


def haversine(a, b):
    r = 6371.0
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def point_at_km(coords, km):
    """Position along the polyline at a given chainage (km)."""
    done = 0.0
    for a, b in zip(coords, coords[1:]):
        seg = haversine(a, b)
        if done + seg >= km:
            f = (km - done) / seg if seg else 0
            return a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
        done += seg
    return coords[-1]


def demo_logo(path):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (500, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 499, 199], radius=28, fill=(15, 37, 69, 255))
    try:
        f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    d.text((40, 30), "TOPO", font=f1, fill=(34, 211, 238, 255))
    d.text((44, 120), "démo · logo fictif", font=f2, fill=(226, 232, 240, 255))
    img.save(path)


# ── 2. Daily reports ────────────────────────────────────────────────
WEATHER = ["Ensoleillé"] * 6 + ["Nuageux"] * 2 + ["Brume / Sable", "Vent fort"]
OBSTACLES = ["Route nationale", "Oued / Zone inondable", "Ligne électrique existante",
             "Zone rocheuse difficile", "Bâtiment / Construction", "Terrain inaccessible"]
NOTES = [
    "RAS. Bornes posées tous les 500 m.",
    "Reprise du levé après contrôle des points de calage.",
    "Couloir dégagé, progression conforme au planning.",
    "Passage d'oued : relevé détaillé des berges sur 300 m.",
    "Vent de sable l'après-midi, arrêt anticipé à 16 h.",
    "Croisement avec une ligne existante : hauteurs relevées.",
]


def main():
    SAMPLES.mkdir(exist_ok=True)
    route = synthetic_route()
    kmz = SAMPLES / "demo_route.kmz"
    write_kmz(route, kmz)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(DailyReport).delete()
    db.query(ProjectConfig).delete()

    meta = import_kmz(str(kmz), name="Tracé démo")
    upload_dir = os.getenv("TOPO_UPLOAD_DIR", os.path.join(DATA_DIR, "uploads"))
    os.makedirs(upload_dir, exist_ok=True)
    demo_logo(os.path.join(upload_dir, "logo.png"))

    start = date(2026, 3, 2)  # a Monday
    db.add(ProjectConfig(total_km=round(meta["length_km"], 1), daily_target_km=3.0,
                         project_name="Ligne MT démo", location="Projet fictif",
                         start_date=start, engineer_name="Ingénieur Démo",
                         logo_path="/uploads/logo.png"))

    kp, day = 0.0, start
    for i in range(11):
        while day.weekday() >= 5:  # crews work Monday–Friday
            day += timedelta(days=1)
        km = round(random.uniform(2.6, 5.2), 2)
        weather = random.choice(WEATHER)
        if weather in ("Brume / Sable", "Vent fort"):
            km = round(km * 0.6, 2)
        obstacles = []
        if random.random() < 0.45:
            obstacles.append({"name": random.choice(OBSTACLES), "kp": round(kp + random.uniform(0.2, km - 0.2), 2)})
        a, b = point_at_km(route, kp), point_at_km(route, kp + km)
        db.add(DailyReport(
            date=day, kp_start=round(kp, 2), kp_end=round(kp + km, 2),
            points_captured=int(km * random.uniform(16, 22)), crew_count=random.choice([3, 4, 4, 5]),
            weather=weather, obstacles=obstacles, eng_note=random.choice(NOTES),
            kp_start_lat=round(a[0], 6), kp_start_lon=round(a[1], 6),
            kp_end_lat=round(b[0], 6), kp_end_lon=round(b[1], 6),
        ))
        kp += km
        day += timedelta(days=1)
    db.commit()
    print(f"Seeded: route {meta['length_km']} km, 11 reports, KP 0 → {kp:.2f} km, data in {DATA_DIR}")


if __name__ == "__main__":
    main()
