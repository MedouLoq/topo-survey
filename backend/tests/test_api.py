import importlib
import io
import sys
import zipfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def _kml(coords):
    pts = " ".join(f"{lon},{lat},0" for lat, lon in coords)
    return f'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><LineString><coordinates>{pts}</coordinates></LineString></Placemark></kml>'


def _kmz(coords) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", _kml(coords))
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TOPO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MAP_TILES", "off")
    for mod in ("database", "models", "schemas", "route_parser", "pdf_gen", "main"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    return TestClient(main.app)


def report(day, kp0, kp1, **kw):
    return {"date": day, "kp_start": kp0, "kp_end": kp1, "points_captured": 60, "crew_count": 4,
            "weather": "Ensoleillé", "obstacles": [], "eng_note": "", **kw}


def test_report_crud_and_stats(client):
    client.patch("/api/config", json={"total_km": 20, "daily_target_km": 5})
    r = client.post("/api/reports", json=report("2026-03-02", 0, 4.5))
    assert r.status_code == 201 and r.json()["km_done"] == 4.5
    client.post("/api/reports", json=report("2026-03-03", 4.5, 10.0, obstacles=[{"name": "Oued", "kp": 6.1}]))

    stats = client.get("/api/stats").json()
    assert stats["km_done"] == 10.0 and stats["pct_done"] == 50.0
    assert stats["days_worked"] == 2 and stats["total_obstacles"] == 1
    assert stats["days_remaining_estimated"] == 2   # 10 km left at 5 km/day

    assert client.post("/api/reports", json=report("2026-03-02", 10, 12)).status_code == 409
    rid = r.json()["id"]
    assert client.patch(f"/api/reports/{rid}", json={"eng_note": "ok"}).json()["eng_note"] == "ok"
    assert client.delete(f"/api/reports/{rid}").status_code == 204
    assert client.get(f"/api/reports/{rid}").status_code == 404


def test_kp_end_must_exceed_kp_start(client):
    assert client.post("/api/reports", json=report("2026-03-02", 5, 5)).status_code == 422


def test_legacy_string_obstacles_are_normalised(client):
    import database, models
    db = database.SessionLocal()
    from datetime import date
    db.add(models.DailyReport(date=date(2026, 3, 4), kp_start=0, kp_end=1, obstacles=["Route nationale"]))
    db.commit()
    obs = client.get("/api/reports").json()[0]["obstacles"]
    assert obs == [{"name": "Route nationale", "kp": None}]


def test_weeks_use_iso_numbering(client):
    # 2026-01-01 is a Thursday in ISO week 1 of 2026; SQLite's %W would call it week 0
    client.post("/api/reports", json=report("2026-01-01", 0, 3))
    client.post("/api/reports", json=report("2026-01-05", 3, 6))   # ISO week 2
    weeks = {w["key"]: w for w in client.get("/api/weeks").json()}
    assert set(weeks) == {"2026-W01", "2026-W02"}
    assert len(client.get("/api/reports", params={"year": 2026, "week": 1}).json()) == 1


def test_daily_and_weekly_pdfs(client):
    client.post("/api/reports", json=report("2026-03-02", 0, 4, kp_start_lat=18.0, kp_start_lon=-15.8,
                                            kp_end_lat=18.03, kp_end_lon=-15.77))
    rid = client.get("/api/reports").json()[0]["id"]
    daily = client.get(f"/api/reports/{rid}/pdf")
    assert daily.status_code == 200 and daily.content[:4] == b"%PDF"
    weekly = client.get("/api/weeks/2026/10/pdf")
    assert weekly.status_code == 200 and weekly.content[:4] == b"%PDF"
    assert client.get("/api/weeks/2026/30/pdf").status_code == 404


def test_kmz_import_and_bad_files(client):
    coords = [(18.0 + i * 0.001, -15.8 + i * 0.001) for i in range(100)]
    r = client.post("/api/routes/import", files={"file": ("../../evil name.kmz", _kmz(coords), "application/zip")})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "evil name" and 13 < body["length_km"] < 17
    assert [x["name"] for x in client.get("/api/routes").json()] == ["evil name"]

    kml = client.post("/api/routes/import", files={"file": ("plain.kml", _kml(coords[:10]).encode(), "text/xml")})
    assert kml.status_code == 200

    assert client.post("/api/routes/import", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 400
    empty = _kmz([])
    assert client.post("/api/routes/import", files={"file": ("empty.kmz", empty, "application/zip")}).status_code == 422


def test_logo_rejects_svg(client):
    assert client.post("/api/config/logo", files={"file": ("x.svg", b"<svg/>", "image/svg+xml")}).status_code == 400


def test_douglas_peucker_keeps_endpoints_and_simplifies():
    from route_parser import _douglas_peucker
    line = [(0.0, i * 0.0001) for i in range(500)]   # perfectly straight
    simplified = _douglas_peucker(line, 0.0002)
    assert simplified[0] == line[0] and simplified[-1] == line[-1] and len(simplified) == 2


def test_fmt_coord_uses_hemispheres():
    from pdf_gen import fmt_coord
    assert fmt_coord(16.5, -12.25) == "16.500000° N, 12.250000° W"
    assert fmt_coord(-1.0, 2.0) == "1.000000° S, 2.000000° E"


def test_multi_segment_kml_ignores_points_and_gaps(tmp_path, monkeypatch):
    """Two separate 10 km lines + pylons far away: length is 20 km, not the jumps between them."""
    monkeypatch.setenv("TOPO_DATA_DIR", str(tmp_path))
    import route_parser
    importlib.reload(route_parser)
    line_a = " ".join(f"{-15.0 + i * 0.001},18.0,0" for i in range(95))     # ≈ 10 km east
    line_b = " ".join(f"{-14.0 + i * 0.001},18.5,0" for i in range(95))     # another 10 km, ~110 km away
    kml = f"""<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
      <Placemark><LineString><coordinates>{line_a}</coordinates></LineString></Placemark>
      <Placemark><Point><coordinates>-10.0,20.0,0</coordinates></Point></Placemark>
      <Placemark><LineString><coordinates>{line_b}</coordinates></LineString></Placemark>
    </Document></kml>"""
    path = tmp_path / "corridor.kml"
    path.write_text(kml)
    data = route_parser.parse_kmz(str(path))
    assert data["segment_count"] == 2
    assert 19.5 < data["length_km"] < 20.5
    route_parser.import_kmz(str(path))
    assert len(route_parser.load_all_routes()) == 2


def test_douglas_peucker_handles_very_long_lines():
    from route_parser import _douglas_peucker
    import math
    # 50k-vertex gently curving line: deep enough to overflow a recursive implementation
    curve = [(i * 1e-5, 0.01 * math.sin(i / 2000)) for i in range(50_000)]
    simplified = _douglas_peucker(curve, 0.0002)
    assert simplified[0] == curve[0] and simplified[-1] == curve[-1]
    assert 2 < len(simplified) < 500
