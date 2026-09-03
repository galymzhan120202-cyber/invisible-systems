#!/usr/bin/env python3
"""
make_branding.py - render the YouTube profile picture and channel banner as PNGs,
in the channel's own visual language (black canvas, white line art, 3 accents).
No AI image API (those need billing); pure SVG -> Chromium screenshot.

    python scripts/lib/make_branding.py            # -> assets/branding/*.png
"""
from __future__ import annotations

import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "branding"

WHITE = "#FFFFFF"
DIM = "#8A93A6"
BLUE = "#4C86F0"   # system / rule
AMBER = "#F2A93B"  # you / what you want
CORAL = "#FF5B5B"  # friction / naive model
BG = "#000000"


def _figure(cx: float, feet_y: float, h: float, col: str, sw: float) -> str:
    """A simple standing stick figure, `h` px tall, feet at feet_y."""
    head_r = h * 0.13
    head_cy = feet_y - h + head_r
    neck = head_cy + head_r
    hip = feet_y - h * 0.42
    arm_y = neck + h * 0.16
    return (
        f'<g stroke="{col}" stroke-width="{sw}" stroke-linecap="round" fill="none">'
        f'<circle cx="{cx}" cy="{head_cy}" r="{head_r}" fill="{col}"/>'
        f'<line x1="{cx}" y1="{neck:.1f}" x2="{cx}" y2="{hip:.1f}"/>'
        f'<line x1="{cx}" y1="{arm_y:.1f}" x2="{cx - h*0.22:.1f}" y2="{arm_y + h*0.10:.1f}"/>'
        f'<line x1="{cx}" y1="{arm_y:.1f}" x2="{cx + h*0.24:.1f}" y2="{arm_y - h*0.06:.1f}"/>'
        f'<line x1="{cx}" y1="{hip:.1f}" x2="{cx - h*0.16:.1f}" y2="{feet_y:.1f}"/>'
        f'<line x1="{cx}" y1="{hip:.1f}" x2="{cx + h*0.17:.1f}" y2="{feet_y:.1f}"/>'
        f'</g>'
    )


def profile_svg() -> str:
    """800x800, reads well cropped to a circle."""
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">']
    s.append(f'<rect width="800" height="800" fill="{BG}"/>')
    # faint guide circle (safe area YouTube crops to)
    s.append(f'<circle cx="400" cy="400" r="392" fill="none" stroke="{DIM}" stroke-width="2" opacity="0.15"/>')
    # three faint "system" dots behind (a tiny queue)
    for i, c in enumerate((BLUE, AMBER, CORAL)):
        s.append(f'<circle cx="{250 + i*150}" cy="250" r="26" fill="{c}" opacity="0.9"/>')
    s.append(f'<line x1="250" y1="300" x2="550" y2="300" stroke="{DIM}" stroke-width="6" opacity="0.5"/>')
    # hero figure, centred, stepping forward
    s.append(_figure(410, 640, 300, WHITE, 20))
    # amber "want" arrow ahead of it
    s.append(f'<path d="M 560 470 l 46 34 l -46 34" fill="none" stroke="{AMBER}" '
             f'stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>')
    s.append('</svg>')
    return "".join(s)


def banner_svg() -> str:
    """2048x1152. Everything meaningful stays inside the 1235x338 all-device safe box
    (centred: x 406..1641, y 407..745)."""
    W, H = 2048, 1152
    cx, cy = W / 2, H / 2
    sx0, sy0, sx1, sy1 = 406, 407, 1641, 745
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    s.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

    # wide faint scaffolding across the whole banner (visible on desktop)
    for gx in range(120, W, 190):
        s.append(f'<line x1="{gx}" y1="120" x2="{gx}" y2="{H-120}" stroke="{DIM}" '
                 f'stroke-width="2" opacity="0.08"/>')
    # a feedback-loop arc (system motif), fully inside the desktop-visible band,
    # curving back on itself - both ends stay well away from the edges
    s.append(f'<path d="M 360 {cy+60} C 660 {cy-210}, 1390 {cy-210}, 1690 {cy+60}" '
             f'fill="none" stroke="{BLUE}" stroke-width="6" opacity="0.30"/>')
    s.append(f'<path d="M 1690 {cy+60} l -34 -46 m 34 46 l -52 -6" fill="none" '
             f'stroke="{BLUE}" stroke-width="6" opacity="0.30" stroke-linecap="round"/>')

    # ---- safe area content (x 406..1641) ----
    # queue of dots feeding in from the left, colours = the semantic accents
    for i in range(6):
        c = (DIM, DIM, DIM, BLUE, AMBER, CORAL)[i]
        s.append(f'<circle cx="{sx0 + 30 + i*44}" cy="{cy+38}" r="15" fill="{c}" '
                 f'opacity="{0.35 + i*0.12:.2f}"/>')
    # hero figure
    s.append(_figure(sx0 + 320, sy1 - 8, 300, WHITE, 18))
    # amber want-arrow ahead
    s.append(f'<path d="M {sx0+452} {cy+6} l 36 28 l -36 28" fill="none" stroke="{AMBER}" '
             f'stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>')

    # wordmark (banner text is fine - not a video frame). Fits inside x=966..1610.
    tx = sx0 + 560
    s.append(f'<text x="{tx}" y="{cy - 12}" font-family="Arial, Helvetica, sans-serif" '
             f'font-size="104" font-weight="700" letter-spacing="1" fill="{WHITE}">INVISIBLE</text>')
    s.append(f'<text x="{tx + 2}" y="{cy + 96}" font-family="Arial, Helvetica, sans-serif" '
             f'font-size="104" font-weight="300" letter-spacing="7" fill="{WHITE}">SYSTEMS</text>')
    s.append(f'<text x="{tx + 4}" y="{cy + 160}" font-family="Arial, Helvetica, sans-serif" '
             f'font-size="30" letter-spacing="5" fill="{DIM}">ONE HIDDEN RULE AT A TIME</text>')

    s.append('</svg>')
    return "".join(s)


async def _render(svg: str, w: int, h: int, out: Path) -> None:
    from playwright.async_api import async_playwright
    html = f'<!doctype html><html><head><meta charset="utf-8">' \
           f'<style>*{{margin:0;padding:0}}html,body{{background:#000}}</style></head>' \
           f'<body>{svg}</body></html>'
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await (await b.new_context(viewport={"width": w, "height": h},
                                        device_scale_factor=1)).new_page()
        await pg.set_content(html, wait_until="load")
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": w, "height": h})
        await b.close()
    print(f"  {out.relative_to(ROOT)}  ({out.stat().st_size // 1024} KB)")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    await _render(profile_svg(), 800, 800, OUT / "profile-800.png")
    await _render(banner_svg(), 2048, 1152, OUT / "banner-2048x1152.png")


if __name__ == "__main__":
    asyncio.run(main())
