"""Stack several generated sheets (e.g. the Gemini skill's walk / action / extra sheets) into one source image,
top to bottom, on the key colour with a margin, so the rest of the pipeline sees one sheet. Optionally drop
stray pieces (a floating duplicate head, frames fused together): each --drop x,y (in output coordinates) erases
the connected foreground piece under that point.

Usage: uv run python -I tools/stitch_sheets.py <out.png> <sheet> [<sheet> ...] [--bg r,g,b] [--pad 60]
       [--drop x,y ...] [--key-dist 150]
"""
import argparse
import numpy as np
import cv2
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("sheets", nargs="+")
ap.add_argument("--bg", default="251,2,248")
ap.add_argument("--pad", type=int, default=60)
ap.add_argument("--drop", action="append", default=[])
ap.add_argument("--key-dist", type=int, default=150)
a = ap.parse_args()

bg = tuple(int(v) for v in a.bg.split(","))
ims = [Image.open(p).convert("RGB") for p in a.sheets]
W = max(i.width for i in ims) + 2 * a.pad
H = sum(i.height for i in ims) + 2 * a.pad * len(ims)
out = Image.new("RGB", (W, H), bg)
y = a.pad
for im in ims:
    out.paste(im, (a.pad, y))
    y += im.height + 2 * a.pad

if a.drop:
    px = np.array(out)
    fg = (np.abs(px.astype(int) - bg).sum(2) > a.key_dist).astype(np.uint8)
    _, lab = cv2.connectedComponents(fg, connectivity=8)
    for d in a.drop:
        x, y = (int(v) for v in d.split(","))
        if not lab[y, x]:
            raise SystemExit(f"--drop {d}: no foreground there")
        # grow a little so the piece's JPEG fringe goes too
        m = cv2.dilate((lab == lab[y, x]).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        px[m] = bg
        print(f"dropped the piece at {d}: {int(m.sum())} px")
    out = Image.fromarray(px)

out.save(a.out)
print(a.out, out.size)
