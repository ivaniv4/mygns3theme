#!/usr/bin/env python3
"""
Generates the repository banner: docs/social-preview.svg and, when a Chromium
based browser (Edge, Chrome) is installed, docs/social-preview.png (1280x640,
the size GitHub expects for a repository social preview).

The mark is docs/assets/gns3-mark.svg (the GNS3 chameleon without its outline).

Usage: python scripts/make_logo.py
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import mygns3theme  # noqa: E402

DOCS = ROOT / "docs"
WIDTH, HEIGHT = 1280, 640

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def mark_inner():
    """Gradient and shapes of the mark, without the outer <svg> element."""
    svg = (DOCS / "assets" / "gns3-mark.svg").read_text(encoding="utf-8")
    return re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1).replace("<title>GNS3</title>", "")


def swatches(x, y):
    tiles = []
    size, gap = 64, 18
    for i, (_, data) in enumerate(mygns3theme.load_themes()):
        c = data["colors"]
        left = x + i * (size + gap)
        tiles.append(
            f'<rect x="{left}" y="{y}" width="{size}" height="{size}" rx="18" fill="{c["surface"]}" '
            f'stroke="{c["outline_variant"]}" stroke-width="2"/>'
            f'<circle cx="{left + size / 2}" cy="{y + size / 2}" r="17" fill="{c["primary"]}"/>')
    return "\n  ".join(tiles)


def banner():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif">
  <title>mygns3theme</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#FEF8FC"/>
      <stop offset="1" stop-color="#ECDCFF"/>
    </linearGradient>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
  <circle cx="250" cy="320" r="270" fill="#FFFFFF" fill-opacity="0.65"/>
  <svg x="95" y="105" width="310" height="310" viewBox="0 0 256 256">{mark_inner()}</svg>
  <text x="560" y="262" font-size="92" font-weight="700" fill="#1D1B1E" letter-spacing="-2">mygns3theme</text>
  <text x="562" y="322" font-size="36" fill="#49454E">Material 3 themes for the</text>
  <text x="562" y="368" font-size="36" fill="#49454E">GNS3 desktop GUI</text>
  {swatches(562, 420)}
  <text x="562" y="548" font-size="26" fill="#7B757F" letter-spacing="1">Windows  ·  Linux  ·  macOS</text>
</svg>
"""


def find_browser():
    for candidate in BROWSERS:
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    return None


def main():
    svg_path = DOCS / "social-preview.svg"
    svg_path.write_text(banner(), encoding="utf-8", newline="\n")
    print(svg_path.relative_to(ROOT))

    browser = find_browser()
    if not browser:
        print("no Chromium based browser found: docs/social-preview.png not generated")
        return
    png_path = DOCS / "social-preview.png"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={tmp}", f"--window-size={WIDTH},{HEIGHT}",
                        f"--screenshot={png_path}", svg_path.as_uri()],
                       capture_output=True, timeout=120)
    print(png_path.relative_to(ROOT) if png_path.exists() else "PNG rendering failed")


if __name__ == "__main__":
    main()
