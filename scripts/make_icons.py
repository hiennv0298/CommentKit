"""Draw CommentKit's icon set (needs Pillow and numpy).

    python scripts/make_icons.py [preview.png]

Writes into src/commentkit/webui/:
  commentkit.ico                           16-256 px: the .exe files, installer and shortcuts
  icon-32.png, icon-192.png, icon-512.png  the app window, taskbar and in-app logo

The icon is a comment: a dark speech bubble with three "typing" dots on a yellow tile (the app's accent,
and unlike PlaylistKit's red-orange or ClipKit's violet). Every size is drawn on its own grid
(8x supersampled), with the dots snapped to whole pixels, so 16-48 px icons stay crisp instead of being a
blurry shrink of the big one. Small sizes get a bigger bubble and bigger dots.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "src" / "commentkit" / "webui"
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
TOP_LEFT, BOTTOM_RIGHT = (255, 222, 40), (255, 160, 10)   # #ffd60a accent -> amber
BUBBLE = (23, 24, 29)                                      # the app's card colour
SS = 8


def _gradient(n: int) -> Image.Image:
    t = (np.arange(n)[:, None] + np.arange(n)[None, :]) / (2 * (n - 1))
    rgb = np.stack([a + (b - a) * t for a, b in zip(TOP_LEFT, BOTTOM_RIGHT)], axis=-1)
    return Image.fromarray(rgb.round().astype("uint8"), "RGB")


def draw_icon(size: int) -> Image.Image:
    n = size * SS
    small = size <= 32
    pad = 0 if small else round(size * 0.04) * SS          # transparent margin, whole pixels
    tile = (pad, pad, n - pad, n - pad)
    inner = n - 2 * pad
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle(tile, radius=inner * (0.24 if small else 0.235), fill=255)
    img.paste(_gradient(n), (0, 0), mask)

    # speech bubble: rounded rectangle + a tail at the bottom left
    d = ImageDraw.Draw(img)
    bw = inner * (0.74 if small else 0.66)
    bh = inner * (0.54 if small else 0.48)
    cx, cy = n / 2, n / 2 - inner * (0.04 if small else 0.035)
    x0, y0, x1, y1 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
    d.rounded_rectangle((x0, y0, x1, y1), radius=bh * 0.42, fill=BUBBLE)
    tail_w, tail_h = bw * 0.24, bh * (0.42 if small else 0.38)
    tx = x0 + bw * 0.20
    d.polygon([(tx, y1 - bh * 0.2), (tx + tail_w, y1 - bh * 0.05), (tx - tail_w * 0.25, y1 + tail_h)], fill=BUBBLE)

    # three dots, snapped to the pixel grid so they stay sharp at 16-32 px
    r_px = max(1.0, round(size * (0.055 if small else 0.052) * 2) / 2)   # radius in output pixels, half-pixel steps
    gap_px = max(r_px * 2 + 1.5, round(size * (0.19 if small else 0.15)))
    cy_px = round(cy / SS)
    cx_px = n / 2 / SS
    for k in (-1, 0, 1):
        x = round(cx_px + k * gap_px)
        d.ellipse(((x - r_px) * SS, (cy_px - r_px) * SS, (x + r_px) * SS, (cy_px + r_px) * SS), fill=TOP_LEFT + (255,))
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icons = {s: draw_icon(s) for s in ICO_SIZES + [192, 512]}
    icons[256].save(OUT / "commentkit.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES],
                    append_images=[icons[s] for s in ICO_SIZES if s != 256])
    for s in (32, 192, 512):
        icons[s].save(OUT / f"icon-{s}.png", optimize=True)
    print("wrote", OUT / "commentkit.ico", "and icon-32/192/512.png")

    if len(sys.argv) > 1:  # preview sheet: every size at 1:1 on light and dark
        shown = [16, 20, 24, 32, 48, 64, 128, 256]
        width = sum(shown) + 20 * (len(shown) + 1)
        sheet = Image.new("RGB", (width, 2 * 296), (243, 243, 243))
        ImageDraw.Draw(sheet).rectangle((0, 296, width, 592), fill=(32, 32, 36))
        for row in (0, 296):
            x = 20
            for s in shown:
                sheet.paste(icons[s], (x, row + 148 - s // 2), icons[s])
                x += s + 20
        sheet.save(sys.argv[1])
        print("preview", sys.argv[1])


if __name__ == "__main__":
    main()
