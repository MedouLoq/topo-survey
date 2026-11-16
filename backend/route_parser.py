"""
KMZ/KML route parser.

A survey corridor usually arrives as a KMZ exported from Google Earth or a
GIS: several LineStrings (route sections) plus Point placemarks (pylons,
crossings, markers). Each LineString is kept as its own segment, so:
  - the route length is the sum of the segments (no fake jumps between them),
  - maps draw the sections separately,
  - simplification runs per segment (Douglas-Peucker, iterative).
Files without any LineString fall back to their points, in file order.
"""
import json
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import List, Optional, Tuple

from database import DATA_DIR

ROUTES_DIR = os.getenv("TOPO_ROUTES_DIR", os.path.join(DATA_DIR, "routes"))
os.makedirs(ROUTES_DIR, exist_ok=True)

LatLon = Tuple[float, float]
SIMPLIFY_EPSILON_DEG = 0.0002   # ≈ 20 m


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _route_length_km(coords: List[LatLon]) -> float:
    return sum(_haversine_km(*coords[i - 1], *coords[i]) for i in range(1, len(coords)))


def _douglas_peucker(points: List[LatLon], epsilon: float) -> List[LatLon]:
    """Simplify a polyline, keeping its shape within `epsilon` (degrees). Iterative."""
    n = len(points)
    if n < 3:
        return list(points)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i0, i1 = stack.pop()
        (x1, y1), (x2, y2) = points[i0], points[i1]
        denom = math.hypot(x2 - x1, y2 - y1)
        max_dist, max_idx = 0.0, -1
        for i in range(i0 + 1, i1):
            x0, y0 = points[i]
            if denom == 0:
                d = math.hypot(x0 - x1, y0 - y1)
            else:
                d = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1) / denom
            if d > max_dist:
                max_dist, max_idx = d, i
        if max_dist > epsilon:
            keep[max_idx] = True
            stack.append((i0, max_idx))
            stack.append((max_idx, i1))
    return [p for p, k in zip(points, keep) if k]


def _parse_coordinates(text: str) -> List[LatLon]:
    out = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                out.append((lat, lon))
    return out


def _read_kml(filepath: str) -> Optional[str]:
    if zipfile.is_zipfile(filepath):
        with zipfile.ZipFile(filepath) as z:
            kml_name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
            if not kml_name:
                return None
            raw = z.read(kml_name)
    else:
        with open(filepath, "rb") as fh:
            raw = fh.read()
    text = raw.decode("utf-8", errors="ignore")
    # Drop namespaces and prefixes so plain tag names work (kml:, gx:, …)
    text = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', "", text)
    text = re.sub(r"<(/?)\w+:", r"<\1", text)
    return text


def _empty(name):
    return {"name": name, "segments": [], "coords": [], "length_km": 0, "bbox": None,
            "raw_points": 0, "simplified_points": 0, "point_count": 0, "segment_count": 0}


def parse_kmz(filepath: str, max_points: int = 800, name: Optional[str] = None) -> dict:
    """Parse a KMZ (zipped KML) or plain KML file into simplified route segments."""
    name = name or os.path.splitext(os.path.basename(filepath))[0]
    text = _read_kml(filepath)
    if text is None:
        return _empty(name)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return _empty(name)

    segments = []
    for line in root.iter("LineString"):
        for coords_el in line.iter("coordinates"):
            pts = _parse_coordinates(coords_el.text)
            if len(pts) >= 2:
                segments.append(pts)
    if not segments:  # no lines: use every coordinate in file order
        pts = [p for el in root.iter("coordinates") for p in _parse_coordinates(el.text)]
        if pts:
            segments = [pts]
    if not segments:
        return _empty(name)

    raw_points = sum(len(s) for s in segments)
    length_km = sum(_route_length_km(s) for s in segments)   # measured on full-resolution lines
    simplified = [_douglas_peucker(s, SIMPLIFY_EPSILON_DEG) for s in segments]

    # Keep the stored geometry light: thin long segments, always keeping endpoints
    total = sum(len(s) for s in simplified)
    if total > max_points:
        ratio = max_points / total
        thinned = []
        for s in simplified:
            keep = max(2, int(len(s) * ratio))
            step = (len(s) - 1) / (keep - 1)
            thinned.append([s[round(i * step)] for i in range(keep)])
        simplified = thinned

    flat = [p for s in simplified for p in s]
    lats, lons = [p[0] for p in flat], [p[1] for p in flat]
    return {
        "name": name,
        "segments": simplified,
        "coords": flat,
        "length_km": round(length_km, 2),
        "bbox": {"min_lat": min(lats), "max_lat": max(lats), "min_lon": min(lons), "max_lon": max(lons)},
        "raw_points": raw_points,
        "simplified_points": len(flat),
        "point_count": len(flat),
        "segment_count": len(simplified),
    }


def import_kmz(filepath: str, name: Optional[str] = None) -> dict:
    """Parse KMZ/KML and save it as JSON in the routes dir. Returns metadata."""
    data = parse_kmz(filepath, name=name)
    out_name = re.sub(r"[^\w\-]", "_", data["name"]) + ".json"
    with open(os.path.join(ROUTES_DIR, out_name), "w") as f:
        json.dump(data, f)
    return {
        "name": data["name"],
        "file": out_name,
        "length_km": data["length_km"],
        "points": data["simplified_points"],
        "segments": data["segment_count"],
        "bbox": data["bbox"],
    }


def list_routes() -> List[dict]:
    """All imported routes with metadata (no geometry)."""
    results = []
    for fn in sorted(os.listdir(ROUTES_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(ROUTES_DIR, fn)) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        results.append({
            "name": d.get("name", fn),
            "file": fn,
            "length_km": d.get("length_km", 0),
            "points": d.get("simplified_points", len(d.get("coords", []))),
            "segments": d.get("segment_count", 1),
            "bbox": d.get("bbox"),
        })
    return results


def load_route_segments(filename: str) -> Optional[List[List[LatLon]]]:
    """Segments of one stored route (older files without segments → one segment)."""
    path = os.path.join(ROUTES_DIR, os.path.basename(filename))
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        data = json.load(f)
    segments = data.get("segments") or ([data["coords"]] if data.get("coords") else [])
    return [[tuple(p) for p in s] for s in segments]


def load_all_routes() -> List[List[LatLon]]:
    """Every segment of every imported route, as separate polylines for maps."""
    out = []
    for fn in sorted(os.listdir(ROUTES_DIR)):
        if fn.endswith(".json"):
            out.extend(s for s in (load_route_segments(fn) or []) if len(s) > 1)
    return out
