"""Compare unfake settings against the current mummy pipeline on a few frames.

Usage: uv run python tools/unfake_test.py
Writes assets/mummy/unfake_test/compare.png (every panel drawn at the same pixel zoom, so
differences in pixel size are visible) plus each unfake result as its own PNG.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import logging
import unfake

logging.disable(logging.CRITICAL)
import mummy_frames as mf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/mummy/unfake_test"
ZOOM = 5
MAGENTA = (255, 0, 255)

# label, sheet, row, frame index in that row, index of the same frame in dist/mummy_sheet.json
PICKS = [
    ("walk_down", "mummy1", 0, 0, 29),
    ("thrust", "mummy1", 2, 3, 57),
    ("shoot", "mummy1", 6, 1, 85),
    ("walk_right", "mummy1", 4, 1, 37),
]
CONFIGS = [
    ("auto", dict(max_colors=24)),                       # scale auto-detection (fails on non-grid art)
    ("x2 dominant", dict(max_colors=24, manual_scale=2)),
    ("x2 median", dict(max_colors=24, manual_scale=2, downscale_method="median")),
    ("x2 content-adaptive", dict(max_colors=24, manual_scale=2, downscale_method="content-adaptive")),
    ("x3 dominant", dict(max_colors=24, manual_scale=3)),
]


def source_crop(rgb, fg, box):
    x0, y0, x1, y1 = box
    m = fg[y0:y1, x0:x1]
    ys, xs = np.where(m)
    y0, y1, x0, x1 = y0 + ys.min(), y0 + ys.max() + 1, x0 + xs.min(), x0 + xs.max() + 1
    out = np.full((y1 - y0, x1 - x0, 3), MAGENTA, np.uint8)
    mm = fg[y0:y1, x0:x1]
    out[mm] = rgb[y0:y1, x0:x1][mm].clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def to_rgba(img):
    """unfake output -> RGBA with the magenta background keyed out."""
    a = np.array(img.convert("RGBA"))
    key = (np.abs(a[..., :3].astype(int) - MAGENTA).sum(-1) < 90)
    a[key, 3] = 0
    return Image.fromarray(a, "RGBA")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sheets = {n: mf.load(n) for n in ("mummy1", "mummy2")}
    boxes = {n: mf.frame_boxes(sheets[n][1]) for n in sheets}
    current = Image.open(ROOT / "dist/mummy_sheet.png").convert("RGBA")
    atlas = json.load(open(ROOT / "dist/mummy_sheet.json"))["frames"]

    panels = []   # per pick: [(label, RGBA image)]
    for label, sheet, row, idx, cur in PICKS:
        rgb, fg = sheets[sheet]
        src = source_crop(rgb, fg, boxes[sheet][row][idx])
        src.save(OUT / f"{label}_src.png")
        f = atlas[cur]["frame"]
        row_panels = [("source", src.convert("RGBA")), ("current", current.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"])))]
        for cname, kw in CONFIGS:
            res = unfake.process_image_sync(str(OUT / f"{label}_src.png"), transparent_background=False, **kw)
            img = res["image"] if isinstance(res, dict) else res
            img = to_rgba(img)
            fn = OUT / f"{label}_{cname.replace(' ', '_')}.png"
            img.save(fn)
            info = {k: v for k, v in res.items() if k != "image"} if isinstance(res, dict) else {}
            print(label, cname, img.size, {k: v for k, v in info.items() if k in ("manual_scale", "scale", "detected_scale", "palette_size")} or list(info)[:6])
            row_panels.append((cname, img))
        panels.append((label, row_panels))

    pad, lab = 8, 14
    w = max(sum(im.width * ZOOM + pad for _, im in rp) for _, rp in panels)
    h = sum(max(im.height for _, im in rp) * ZOOM + lab + pad for _, rp in panels)
    sheet_img = Image.new("RGBA", (w, h), (42, 45, 52, 255))
    d = ImageDraw.Draw(sheet_img)
    y = 0
    for label, rp in panels:
        rh = max(im.height for _, im in rp) * ZOOM
        x = 0
        for name, im in rp:
            d.text((x + 2, y + 1), f"{label}: {name} {im.width}x{im.height}", fill=(230, 230, 240, 255))
            big = im.resize((im.width * ZOOM, im.height * ZOOM), Image.NEAREST)
            sheet_img.alpha_composite(big, (x, y + lab + rh - big.height))
            x += big.width + pad
        y += rh + lab + pad
    sheet_img.save(OUT / "compare.png")
    print("wrote", OUT / "compare.png", sheet_img.size)


if __name__ == "__main__":
    main()
