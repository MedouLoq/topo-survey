"""Capture README screenshots from a running demo instance (synthetic data only).

    # terminal 1: backend on the seeded demo database
    cd backend && TOPO_DATA_DIR=../demo-data uvicorn main:app --port 8000
    # terminal 2: frontend
    cd frontend && npm run dev
    # terminal 3
    python scripts/screenshots.py http://127.0.0.1:5173
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"


def pdf_page_png(pdf_bytes: bytes, out: Path, page: int = 1, dpi: int = 110):
    """Render one PDF page to PNG with poppler's pdftoppm."""
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "r.pdf"
        pdf.write_bytes(pdf_bytes)
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page),
                        "-singlefile", str(pdf), str(out.with_suffix(""))], check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2, locale="fr-FR")
        page.goto(URL)
        page.wait_for_selector(".recharts-surface", timeout=20000)
        page.wait_for_timeout(1500)  # let chart animations finish
        page.screenshot(path=OUT / "dashboard.png")

        for nav, name in (("Nouveau rapport", "new_report.png"), ("Rapports", "reports.png"), ("Paramètres", "settings.png")):
            page.get_by_role("button", name=nav).first.click()
            page.wait_for_timeout(1200)
            page.screenshot(path=OUT / name)

        # Mobile layout
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, locale="fr-FR")
        mobile.goto(URL)
        mobile.wait_for_selector(".recharts-surface", timeout=20000)
        mobile.wait_for_timeout(1500)
        mobile.screenshot(path=OUT / "mobile_dashboard.png")

        # Generated PDFs (daily + weekly), first page each
        reports = page.request.get(URL + "/api/reports").json()
        daily = page.request.get(f"{URL}/api/reports/{reports[0]['id']}/pdf").body()
        pdf_page_png(daily, OUT / "pdf_daily.png")
        pdf_page_png(daily, OUT / "pdf_daily_map.png", page=2)
        week = max(page.request.get(URL + "/api/weeks").json(), key=lambda w: w["days"])  # fullest week
        weekly = page.request.get(f"{URL}/api/weeks/{week['year']}/{week['week']}/pdf").body()
        pdf_page_png(weekly, OUT / "pdf_weekly.png")
        browser.close()
    print("Saved:", *sorted(x.name for x in OUT.iterdir()), sep="\n  ")


if __name__ == "__main__":
    main()
