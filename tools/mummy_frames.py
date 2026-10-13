"""Slice the generated mummy sheets into clean 64x64 pixel frames.

The source sheets are smooth AI art with a baked-in checkerboard, not true pixel art, so they are
downscaled by coverage-weighted area averaging (only sprite pixels contribute colour), alpha is
hard-thresholded, and every frame is snapped to ONE shared palette. Frames are anchored by feet
(bottom row) and torso centre so animations do not jitter.

Usage: python3 -I tools/mummy_frames.py <out_dir>
Writes <out_dir>/frames.png (grid of 64x64 cells, canonical facing) and <out_dir>/frames.json.
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets/mummy/src"
CELL = 64
BODY_H = 46          # standing height in px, matches the me_rpg LPC characters
SRC_BODY_H = 106     # standing height of a frame in the source sheets
SCALE = BODY_H / SRC_BODY_H
BASELINE = 61        # bottom row of the feet, as in the LPC sheets
COLORS = 24
EXPECT = [7, 7, 6, 6, 6, 6, 6, 6]

# name -> (sheet, [(row, frame-slice)])
CLIPS = {
    "walk_down": ("mummy1", [(0, None)]),
    "walk_up": ("mummy2", [(0, None)]),
    "walk_right": ("mummy1", [(4, None)]),   # the three-quarter walk; row 1 of the sheet turns mid-cycle
    "thrust_right": ("mummy1", [(2, None), (3, None)]),
    "slash_right": ("mummy1", [(5, None)]),
    "shoot_right": ("mummy1", [(6, None)]),
    "death_right": ("mummy1", [(7, None)]),
}


def load(name):
    rgb = np.array(Image.open(SRC / f"{name}.jpeg").convert("RGB")).astype(np.float32)
    mx, mn = rgb.max(2), rgb.min(2)
    bg = ((mx - mn) < 24) & (mn > 125) & (mx < 228)
    fg = ~bg
    # drop the checker-tinted fringe: erode one pixel
    er = fg.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        er &= np.roll(np.roll(fg, dy, 0), dx, 1)
    return rgb, er


def runs(v, minlen, gap=0):
    out, s = [], None
    for i, x in enumerate(v):
        if x and s is None:
            s = i
        if not x and s is not None:
            out.append([s, i - 1]); s = None
    if s is not None:
        out.append([s, len(v) - 1])
    merged = []
    for r in out:
        if merged and r[0] - merged[-1][1] <= gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [tuple(r) for r in merged if r[1] - r[0] + 1 >= minlen]


def frame_boxes(fg):
    rows = runs(fg.sum(1) > 10, 25, 3)
    assert len(rows) == len(EXPECT), rows
    boxes = []
    for (y0, y1), n in zip(rows, EXPECT):
        cs = fg[y0:y1 + 1].sum(0)
        W = cs.shape[0]
        cuts = [0]
        for k in range(1, n):                    # cut at the emptiest column near each cell boundary
            c = int(W / n * k)
            cuts.append(c - 30 + int(np.argmin(cs[c - 30:c + 30])))
        cuts.append(W)
        cols = [(cuts[i], cuts[i + 1] - 1) for i in range(n)]
        boxes.append([(x0, y0, x1 + 1, y1 + 1) for x0, x1 in cols])
    return boxes


def area_down(rgb, fg, box):
    x0, y0, x1, y1 = box
    m = fg[y0:y1, x0:x1].astype(np.float32)
    ys, xs = np.where(m > 0)
    y0, y1, x0, x1 = y0 + ys.min(), y0 + ys.max() + 1, x0 + xs.min(), x0 + xs.max() + 1
    m = fg[y0:y1, x0:x1].astype(np.float32)
    c = rgb[y0:y1, x0:x1]
    w, h = x1 - x0, y1 - y0
    nw, nh = max(1, round(w * SCALE)), max(1, round(h * SCALE))
    chans = [Image.fromarray((c[:, :, k] * m).astype(np.float32), "F").resize((nw, nh), Image.BOX) for k in range(3)]
    mm = Image.fromarray(m, "F").resize((nw, nh), Image.BOX)
    cov = np.array(mm)
    col = np.stack([np.array(ch) for ch in chans], -1) / np.maximum(cov[..., None], 1e-3)
    # torso-centre anchor: eroded mask (thin staffs/arrows vanish) in the middle band of the figure
    band = (m[int(h * .30):int(h * .65)] > 0)
    for _ in range(4):
        band = band & np.roll(band, 1, 1) & np.roll(band, -1, 1)
    cx = (np.where(band.any(0))[0].mean() if band.any() else w / 2) * SCALE
    return col, cov >= 0.5, cx


def majority(idx, alpha, need=5):
    """Replace a pixel by the dominant palette index of its 3x3 neighbourhood when that index
    covers at least `need` of the 9 cells: removes salt-and-pepper noise, keeps edges."""
    h, w = idx.shape
    pad = np.pad(np.where(alpha, idx.astype(np.int16), -1), 1, constant_values=-1)
    stack = np.stack([pad[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)])
    best, bestn = idx.copy(), np.zeros((h, w), np.int16)
    for k in np.unique(stack[stack >= 0]):
        n = (stack == k).sum(0)
        take = (n > bestn)
        best = np.where(take, k, best); bestn = np.where(take, n, bestn)
    return np.where(alpha & (bestn >= need), best, idx)


def main(out):
    sheets = {n: load(n) for n in ("mummy1", "mummy2")}
    boxes = {n: frame_boxes(sheets[n][1]) for n in sheets}
    cells, meta = [], {}
    for clip, (sheet, parts) in CLIPS.items():
        rgb, fg = sheets[sheet]
        idx = []
        for row, _ in parts:
            for box in boxes[sheet][row]:
                col, a, cx = area_down(rgb, fg, box)
                h, w = a.shape
                canvas = np.zeros((CELL, CELL, 3), np.float32); alpha = np.zeros((CELL, CELL), bool)
                ox = int(round(CELL / 2 - cx)); oy = BASELINE + 1 - h
                ox = max(0, min(CELL - w, ox)); oy = max(0, oy)
                canvas[oy:oy + h, ox:ox + w] = col[:CELL - oy, :CELL - ox][:min(h, CELL - oy), :min(w, CELL - ox)]
                alpha[oy:oy + h, ox:ox + w] = a[:CELL - oy, :CELL - ox][:min(h, CELL - oy), :min(w, CELL - ox)]
                idx.append(len(cells)); cells.append((canvas, alpha))
        meta[clip] = idx
    # area averaging flattens contrast: stretch levels once for the whole set, then lift saturation a little
    allpx = np.concatenate([c[a] for c, a in cells])
    lum = allpx @ np.array([0.299, 0.587, 0.114], np.float32)
    lo, hi = np.percentile(lum, 1), np.percentile(lum, 99)

    def enhance(img):
        l = (img @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
        l2 = np.clip((l - lo) / (hi - lo), 0, 1) * 255
        out = img + (l2 - l)                      # shift each pixel by its luminance change
        mean = out.mean(-1, keepdims=True)
        return np.clip(mean + (out - mean) * 1.2, 0, 255)

    cells = [(enhance(c), a) for c, a in cells]
    # one shared palette from every opaque pixel of every frame
    px = np.concatenate([c[a] for c, a in cells]).clip(0, 255).astype(np.uint8)
    strip = Image.fromarray(px.reshape(-1, 1, 3), "RGB")
    pal = strip.quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT, kmeans=3, dither=Image.Dither.NONE)
    pal_rgb = np.array(pal.getpalette()[:COLORS * 3], np.uint8).reshape(-1, 3)
    cols = int(np.ceil(np.sqrt(len(cells))))
    rows = (len(cells) + cols - 1) // cols
    sheet = np.zeros((rows * CELL, cols * CELL, 4), np.uint8)
    for i, (canvas, alpha) in enumerate(cells):
        qi = Image.fromarray(canvas.clip(0, 255).astype(np.uint8), "RGB").quantize(palette=pal, dither=Image.Dither.NONE)
        a = alpha.copy()
        q = majority(np.array(qi), a)
        q = np.array(pal_rgb)[q]
        # drop 1-2 px specks (8-connected)
        seen = np.zeros_like(a)
        for y in range(CELL):
            for x in range(CELL):
                if a[y, x] and not seen[y, x]:
                    st, comp = [(y, x)], [(y, x)]; seen[y, x] = 1
                    while st:
                        cy, cx_ = st.pop()
                        for dy in (-1, 0, 1):
                            for dx in (-1, 0, 1):
                                ny, nx = cy + dy, cx_ + dx
                                if 0 <= ny < CELL and 0 <= nx < CELL and a[ny, nx] and not seen[ny, nx]:
                                    seen[ny, nx] = 1; st.append((ny, nx)); comp.append((ny, nx))
                    if len(comp) <= 2:
                        for cy, cx_ in comp: a[cy, cx_] = False
        r, c = divmod(i, cols)
        sheet[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL, :3] = q
        sheet[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL, 3] = a * 255
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet, "RGBA").save(out / "frames.png")
    json.dump({"cell": CELL, "cols": cols, "clips": meta}, open(out / "frames.json", "w"))
    print(len(cells), "frames,", cols, "cols,", len({tuple(p[:3]) for p in sheet.reshape(-1, 4) if p[3]}), "colours")


if __name__ == "__main__":
    main(sys.argv[1])
