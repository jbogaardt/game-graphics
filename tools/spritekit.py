"""Shared steps of the sprite pipeline (see .claude/skills/sprite-sheet/SKILL.md).

Everything here is driven by a sprite spec (assets/<name>/sprite.json): source image, background,
expected frames per row, target size, designed palette ramps, clips (which source frames make which
animation) and tuning params. Smooth AI art is turned into frames that share one pixel grid and one
designed palette:

  key background -> remove ground dirt -> despill + mean-shift -> blur luminance (not accents / head)
  -> area-downscale to 4x target -> normalise luminance per frame -> form light from the silhouette
  -> map every pixel onto a designed ramp -> unfake (manual_scale=4, dominant) on ONE atlas
  -> despeckle -> register frames sideways -> reuse unchanged pixels -> drop crumbs
"""
import json, logging
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import unfake

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parent.parent
W3 = np.array([0.299, 0.587, 0.114], np.float32)
UP = 4  # frames are prepared at 4x the target size and reduced 4:1 by unfake

DEFAULTS = {
    "key_dist": 150,     # RGB L1 distance from the background colour that counts as foreground
    "dark_wall": 90,     # luminance of the outline that separates the figure from ground dirt
    "dark_keep": 55,     # source pixels darker than this are structure (gaps, sockets) and are not blurred
    "keep_top": 0.2,     # top fraction of a figure that is not blurred (head detail)
    "smooth": 0.8,       # luminance blur in target px: shading follows form, not per-frame AI texture
    "light": [-1, -1],   # light direction (dx, dy); top-left like the LPC sheets
    "form_light": 30,    # strength of the silhouette-derived light/shadow, in luminance units
    "stable_tol": 32,    # luminance difference below which a pixel reuses the previous frame's pixel
    "register_reach": 2, # max sideways shift when registering a frame to the previous one
    "x_stretch": 1.0,
    "seams": 0,          # darken the source's wrap/fold seams by this much luminance after the blur (0 = off)
    "seam_pct": 12,      # share of body pixels (strongest black-hat response) treated as seams    # widen figures (LPC bodies are chunkier than most generated figures)
}


def load_spec(path):
    path = Path(path)
    spec = json.loads(path.read_text())
    spec["_dir"] = path.parent
    spec["params"] = {**DEFAULTS, **spec.get("params", {})}
    return spec


def lum(a):
    return a[..., :3].astype(np.float32) @ W3


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------- source intake

def load_source(path, bg, key_dist=150):
    """RGB float array and a foreground mask. `bg` is an [r,g,b] key colour, or "alpha"."""
    im = Image.open(path)
    if bg == "alpha":
        a = np.array(im.convert("RGBA"))
        return a[..., :3].astype(np.float32), a[..., 3] > 127
    rgb = np.array(im.convert("RGB")).astype(np.float32)
    fg = np.abs(rgb - np.array(bg, np.float32)).sum(2) > key_dist
    fg = cv2.erode(fg.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)   # drop the key-colour fringe
    return rgb, fg


def runs(v, minlen):
    out, s = [], None
    for i, x in enumerate(list(v) + [False]):
        if x and s is None:
            s = i
        if not x and s is not None:
            if i - s >= minlen:
                out.append((s, i))
            s = None
    return out


def find_cells(fg, min_row=20, min_col=9):
    """Rows of figures, then figures within each row, as (x0, y0, x1, y1) boxes."""
    rows = runs(fg.sum(1) > 3, min_row)
    return [[(x0, y0, x1, y1) for x0, x1 in runs(fg[y0:y1].any(0), min_col)] for y0, y1 in rows]


def remove_dirt(rgb, fg, box, dark_wall=90):
    """The figure has a dark outline; ground dirt and dust sit outside it. Flood from the background
    through every non-outline pixel and drop what is reached, then keep only sizeable pieces."""
    x0, y0, x1, y1 = box
    f = fg[y0:y1, x0:x1]
    l = lum(rgb[y0:y1, x0:x1])
    wall = cv2.dilate(((l < dark_wall) & f).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & f
    _, lab = cv2.connectedComponents((~f | ~wall).astype(np.uint8), connectivity=4)
    keep = f & ~np.isin(lab, np.unique(lab[~f]))
    if keep.sum() < 0.75 * f.sum():
        # the flood leaked through gaps in a thin outline into the body (light figures such as white fur):
        # that is not dirt, so keep the figure and drop only small loose pieces
        keep = f
    n, lab, st, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8), connectivity=8)
    if n < 2:
        return f
    big = st[1:, 4].max()
    return np.isin(lab, [i for i in range(1, n) if st[i, 4] > max(300, 0.02 * big)])


# ---------------------------------------------------------------- colour

def hsv_deg(px):
    hsv = cv2.cvtColor(px.reshape(-1, 1, 3).clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV_FULL).reshape(-1, 3).astype(int)
    return hsv[:, 0] * 360 // 256, hsv[:, 1], hsv[:, 2]


def material_masks(px, materials):
    """Which designed ramp each pixel belongs to. `materials` maps a name to {"hue": [lo, hi]
    (wraps if lo > hi), "sat": min, "val": min, "ramp": [...]}; the one without "hue" is the default."""
    h, s, v = hsv_deg(px)
    out, taken = {}, np.zeros(len(px), bool)
    for name, m in materials.items():
        if "hue" not in m:
            continue
        lo, hi = m["hue"]
        hue = (h >= lo) & (h <= hi) if lo <= hi else (h >= lo) | (h <= hi)
        sel = hue & (s >= m.get("sat", 0)) & (v >= m.get("val", 0)) & ~taken
        out[name] = sel
        taken |= sel
    default = [n for n, m in materials.items() if "hue" not in m]
    assert len(default) == 1, "exactly one material without a hue rule (the body)"
    out[default[0]] = ~taken
    return out


def palette_of(spec):
    pal = [spec["palette"]["outline"]]
    for m in spec["palette"]["materials"].values():
        pal += [c for c in m["ramp"] if c not in pal]
    pal += [c for c in spec["palette"].get("extra", []) if c not in pal]
    return pal


def map_to_ramps(px, spec, thin=None):
    """Snap colours onto the designed ramps: material by hue, step by luminance, anything darker than
    `outline_below` to the outline colour. Step thresholds are global (the same for every frame, so
    frames agree). Per material either:
      "shares": cumulative share of the material's pixels up to each step, e.g. [0.04, 0.15, 0.4, 0.72, 1]
                (sets the value distribution directly: how much is lit, mid and shadow, as in a reference)
      or evenly spaced luminance bins over the "range" percentiles, bent by "gamma".
    `thin` marks thin parts (bows, staffs, fingers); their step is capped at the material's
    "thin_max_step" so they stay dark against a light body."""
    P = spec["palette"]
    mats = P["materials"]
    out = np.zeros_like(px)
    l = px @ W3
    for name, sel in material_masks(px, mats).items():
        m = mats[name]
        ramp = np.array([hexrgb(c) for c in m["ramp"]], np.float32)
        if not sel.any():
            continue
        ls = l[sel]
        if "shares" in m:
            cuts = np.percentile(ls, [100 * q for q in m["shares"][:-1]])
            step = np.searchsorted(cuts, ls, side="right")
        else:
            lo, hi = np.percentile(ls, m.get("range", [2, 99]))
            t = np.clip((ls - lo) / max(hi - lo, 1e-3), 0, 0.999) ** m.get("gamma", 1.0)
            step = (t * len(ramp)).astype(int)
        if thin is not None and "thin_max_step" in m:
            step = np.where(thin[sel], np.minimum(step, m["thin_max_step"]), step)
        out[sel] = ramp[np.clip(step, 0, len(ramp) - 1)]
    dark = l < P.get("outline_below", 0)
    out[dark] = hexrgb(P["outline"])
    return out


def thin_parts(alpha, px_per_target):
    """Pixels of parts at most ~2 target px thick (bows, staffs, strings), from the distance transform:
    nowhere nearby is deeper inside the figure than 1.25 target px."""
    a = alpha.astype(np.uint8)
    dist = cv2.distanceTransform(a, cv2.DIST_L2, 3)
    k = int(3 * px_per_target) | 1
    deep = cv2.dilate(dist, np.ones((k, k), np.uint8))
    return (a > 0) & (deep <= 1.25 * px_per_target)


# ---------------------------------------------------------------- per-frame preparation

def prep(c, m):
    """Despill the key-colour rim, then mean-shift so fine AI texture becomes flat shapes instead of
    grain once it is reduced ~5:1."""
    rim = m & ~cv2.erode(m.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    c = c.copy()
    spill = np.clip(np.minimum(c[..., 0], c[..., 2]) - c[..., 1], 0, None) * rim
    c[..., 0] -= spill; c[..., 2] -= spill
    return cv2.pyrMeanShiftFiltering(c.clip(0, 255).astype(np.uint8), 6, 28).astype(np.float32)


def smooth_shading(c, m, sigma, spec):
    """Blur luminance only, inside the mask, keeping chroma. The AI texture is re-invented in every
    frame and turns into shade patches that jump around in motion; broad light is stable. Accent
    materials, the head (top `keep_top` of the figure) and dark structure are left sharp."""
    p = spec["params"]
    if sigma <= 0:
        return c
    ycc = cv2.cvtColor(c.clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2YCrCb).astype(np.float32)
    mf = m.astype(np.float32)
    blur = cv2.GaussianBlur(ycc[..., 0] * mf, (0, 0), sigma) / np.maximum(cv2.GaussianBlur(mf, (0, 0), sigma), 1e-3)
    sel = material_masks(c.reshape(-1, 3), spec["palette"]["materials"])
    accent = np.zeros(m.size, bool)
    for name, s in sel.items():
        if "hue" in spec["palette"]["materials"][name]:
            accent |= s
    accent = cv2.dilate(accent.reshape(m.shape).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    ys = np.where(m.any(1))[0]
    accent[:ys[0] + int((ys[-1] - ys[0]) * p["keep_top"])] = True
    y = ycc[..., 0]
    ycc[..., 0] = np.where(accent, y, np.where(m & (y > p["dark_keep"]), blur, np.minimum(y, blur)))
    return cv2.cvtColor(ycc.clip(0, 255).astype(np.uint8), cv2.COLOR_YCrCb2RGB).astype(np.float32)


def form_light(cell, strength, light, reach):
    """Light and shadow from the silhouette alone: a pixel whose neighbour towards the light is
    outside the figure is lit, one whose neighbour away from it is outside is shaded. It depends only
    on the shape, so it is the same from frame to frame (no sparkle) and gives one light direction."""
    if not strength:
        return cell
    a = (cell[..., 3] > 0).astype(np.float32)
    b = cv2.GaussianBlur(a, (0, 0), reach / 2)
    dx, dy = np.sign(light[0]) * reach, np.sign(light[1]) * reach
    toward = np.roll(np.roll(b, int(-dy), 0), int(-dx), 1)   # value at the pixel `reach` px towards the light
    away = np.roll(np.roll(b, int(dy), 0), int(dx), 1)
    term = strength * ((1 - toward) - (1 - away))
    out = cell.astype(np.float32)
    out[..., :3] += term[..., None] * a[..., None]
    return out.clip(0, 255).astype(np.uint8)


def torso_cx(m):
    ys = np.where(m.any(1))[0]
    h = ys[-1] - ys[0] + 1
    band = cv2.erode(m[ys[0] + int(h * .30):ys[0] + int(h * .65)].astype(np.uint8), np.ones((1, 9), np.uint8))
    xs = np.where(band.any(0))[0]
    return xs.mean() if len(xs) else m.shape[1] / 2


# ---------------------------------------------------------------- after the grid snap

def despeckle(img, passes=2):
    """A pixel whose colour matches none of its four neighbours reads as a sparkle in motion: give it
    the most common colour of its 8 neighbours. Silhouette pixels keep their shape."""
    key = img[..., 0].astype(np.int32) << 16 | img[..., 1].astype(np.int32) << 8 | img[..., 2]
    a = img[..., 3] > 0
    H, W = a.shape
    for _ in range(passes):
        P = np.pad(np.where(a, key, -1), 1, constant_values=-1)
        nb = [P[1 + dy:1 + dy + H, 1 + dx:1 + dx + W] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
        four = [nb[1], nb[3], nb[4], nb[6]]
        lonely = a & np.all([n >= 0 for n in four], 0) & np.all([n != key for n in four], 0)
        st = np.stack(nb)
        best, bestn = key.copy(), np.zeros(key.shape, np.int32)
        for k in np.unique(st[:, lonely]):
            if k < 0:
                continue
            n = (st == k).sum(0)
            take = lonely & (n > bestn)
            best, bestn = np.where(take, k, best), np.where(take, n, bestn)
        if not (key != best).any():
            break
        key = best
    out = img.copy()
    out[..., 0], out[..., 1], out[..., 2] = key >> 16 & 255, key >> 8 & 255, key & 255
    out[~a] = 0
    return out


def cell_view(a, i, cols, cell):
    r, c = divmod(i, cols)
    return a[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell]


def register(small, smooth, seqs, cols, cell, reach):
    """Shift each frame sideways (feet stay on the baseline) to best match the previous frame's head
    and torso; 1 px of jitter moves every shaded pixel and is the biggest cause of sparkle."""
    done = set()
    for seq in seqs:
        for prev, cur in zip(seq, seq[1:]):
            if cur in done or cur == prev:
                continue
            done.add(cur)
            p, c = cell_view(small, prev, cols, cell), cell_view(small, cur, cols, cell)
            pl, cl = lum(cell_view(smooth, prev, cols, cell)), lum(cell_view(smooth, cur, cols, cell))
            ys = np.where((c[..., 3] > 0).any(1))[0]
            top = slice(ys[0], ys[0] + int((ys[-1] - ys[0]) * 0.6))
            def cost(dx):
                sa = np.roll(c[..., 3] > 0, dx, 1)[top]; pa = (p[..., 3] > 0)[top]
                both = sa & pa
                d = np.abs(np.roll(cl, dx, 1)[top] - pl[top])[both].mean() if both.any() else 99
                return d + 40 * (sa ^ pa).sum() / max(both.sum(), 1)
            dx = min(range(-reach, reach + 1), key=lambda d: (cost(d), abs(d)))
            if dx:
                c[:] = np.roll(c.copy(), dx, 1)
                sm = cell_view(smooth, cur, cols, cell)
                sm[:] = np.roll(sm.copy(), dx, 1)


def stabilise(small, smooth, seqs, cols, cell, tol):
    """Hand-made cycles reuse the torso pixels and move only the limbs (~10% of pixels change per
    frame in LPC walks); AI frames redraw everything. Wherever this frame's unquantised colour is
    within `tol` of the previous frame's (best +-1 px shift), reuse the previous output pixel."""
    done = set()
    for seq in seqs:
        for prev, cur in zip(seq, seq[1:]):
            if cur in done or cur == prev:
                continue
            done.add(cur)
            po, co = cell_view(small, prev, cols, cell), cell_view(small, cur, cols, cell)
            pl, cl = lum(cell_view(smooth, prev, cols, cell)), lum(cell_view(smooth, cur, cols, cell))
            pa, ca = po[..., 3] > 0, co[..., 3] > 0
            inner = ca.copy()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                inner &= np.roll(np.roll(ca, dy, 0), dx, 1)
            best = None
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    sl, sa = np.roll(np.roll(pl, dy, 0), dx, 1), np.roll(np.roll(pa, dy, 0), dx, 1)
                    ok = inner & sa & (np.abs(sl - cl) < tol)
                    if best is None or ok.sum() > best[0]:
                        best = (ok.sum(), dy, dx, ok)
            _, dy, dx, ok = best
            src = np.roll(np.roll(po, dy, 0), dx, 1)
            co[ok] = src[ok]


def thin_darks(cell, spec, passes=3):
    """LPC keeps near-black to a 1 px outline and thin 1 px internal lines (~4-10% of the interior);
    generated art has thick dark masses (gaps between limbs, cast shadows). Thin every interior dark
    mass to 1 px from the lit side: a dark pixel whose neighbour towards the light is lit body and whose
    neighbour away from it is also dark takes the lit neighbour's colour one ramp step down."""
    mat = next(m for m in spec["palette"]["materials"].values() if "hue" not in m)
    ramp = [hexrgb(c) for c in mat["ramp"]]
    dark_cols = {hexrgb(spec["palette"]["outline"]), ramp[0]}
    key = lambda a: a[..., 0].astype(np.int32) << 16 | a[..., 1].astype(np.int32) << 8 | a[..., 2]
    kd = {c[0] << 16 | c[1] << 8 | c[2] for c in dark_cols}
    step = {(c[0] << 16 | c[1] << 8 | c[2]): i for i, c in enumerate(ramp)}
    out = cell.copy()
    lx, ly = spec["params"]["light"]
    dirs = [(0, int(np.sign(lx)) or -1), (int(np.sign(ly)) or -1, 0)]
    dirs += [(-dy, -dx) for dy, dx in dirs]          # lit side first, then the shadow side
    for _ in range(passes):
        for dy, dx in dirs:
            k = key(out)
            a = out[..., 3] > 0
            inner = a.copy()
            for ddy, ddx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                inner &= np.roll(np.roll(a, ddy, 0), ddx, 1)
            dark = inner & np.isin(k, list(kd))
            toward = np.roll(np.roll(k, -dy, 0), -dx, 1)          # neighbour at p + d
            anydark = a & np.isin(k, list(kd))                    # edge pixels count too: a 2 px outline thins to 1
            away = np.roll(np.roll(anydark, dy, 0), dx, 1)        # p - d is dark
            lit = np.vectorize(lambda v: v in step and step[v] >= 1, otypes=[bool])(toward)
            go = dark & away & lit
            for y, x in zip(*np.where(go)):
                v = int(toward[y, x])
                c = ramp[max(1, step[v] - 1)]
                out[y, x, :3] = c
    return out


def style_stats(frames):
    """Numbers that say whether a sprite sits with LPC art: figure height and width, median
    luminance, share of the interior that is near-black, share of the ring just inside the edge that is
    near-black (an effectively 2 px outline), colours."""
    h, w, med, inner, ring, cols = [], [], [], [], [], set()
    for f in frames:
        a = (f[..., 3] > 0).astype(np.uint8)
        if not a.any():
            continue
        ys, xs = np.where(a)
        h.append(np.ptp(ys) + 1); w.append(np.ptp(xs) + 1)
        l = lum(f)
        med.append(np.median(l[a > 0]))
        e1 = cv2.erode(a, np.ones((3, 3), np.uint8))
        e2 = cv2.erode(e1, np.ones((3, 3), np.uint8))
        r2 = (e1 > 0) & (e2 == 0)
        core = cv2.erode(a, np.ones((5, 5), np.uint8)) > 0
        ring.append((l[r2] < 60).mean() if r2.any() else 0)
        inner.append((l[core] < 60).mean() if core.any() else 0)
        cols |= {tuple(p) for p in f[a > 0][:, :3]}
    return {"height": float(np.median(h)), "width": float(np.median(w)), "median_lum": float(np.median(med)),
            "interior_dark": float(np.mean(inner)), "ring_dark": float(np.mean(ring)), "colours": len(cols)}


def reference_frames(spec):
    """Walk frames (rows up/left/down/right, columns 1-8) of the reference characters named in
    spec target.reference: {"dir": "../me_rpg/public/sprites/lpc", "sets": [[layer files...], ...]}."""
    ref = spec["target"].get("reference")
    if not ref:
        return {}
    d = (ROOT / ref["dir"]).resolve()
    out = {}
    for files in ref["sets"]:
        ims = [Image.open(d / f).convert("RGBA") for f in files]
        fr = []
        for r in range(4):
            for c in range(1, 9):
                im = Image.new("RGBA", (64, 64))
                for layer in ims:
                    im.alpha_composite(layer.crop((c * 64, r * 64, c * 64 + 64, r * 64 + 64)))
                fr.append(np.array(im))
        out[files[0].split(".")[1]] = fr
    return out


def drop_crumbs(small):
    """Components of <=2 px, and pixels with no side neighbour and <2 diagonal ones (a diagonal staff
    or bowstring pixel has two diagonal neighbours and stays)."""
    alpha = small[..., 3] > 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(alpha.astype(np.uint8), connectivity=8)
    alpha &= np.isin(lab, [j for j in range(1, n) if st[j, 4] > 2])
    P = np.pad(alpha, 1)
    side = P[:-2, 1:-1] | P[2:, 1:-1] | P[1:-1, :-2] | P[1:-1, 2:]
    diag = P[:-2, :-2].astype(int) + P[:-2, 2:] + P[2:, :-2] + P[2:, 2:]
    alpha &= side | (diag >= 2)
    small[~alpha] = 0
    return small


def add_wraps(cell, spec, period):
    """Designed wrap lines for bandaged figures: on every `period`-th frame row below the head, interior
    body-ramp pixels drop one ramp step. Rows are fixed in the frame (anchoring them to the bobbing head
    made the back-view walk sparkle), and horizontal lines do not move when a limb swings sideways, so
    unlike the generator's per-frame texture they do not sparkle.
    The row shifts by one every 4 px across, so it reads as wraps and not as banding."""
    hd = head_anchor(cell)
    if hd is None or not period:
        return cell
    top = hd[0]
    mat = next(m for m in spec["palette"]["materials"].values() if "hue" not in m)
    ramp = [hexrgb(c) for c in mat["ramp"]]
    key = {c: i for i, c in enumerate(ramp)}
    H, W = cell.shape[:2]
    out = cell.copy()
    for y in range(top + 12, H - 1):          # below the head
        for x in range(1, W - 1):
            if (y + (x // 4) % 2) % period:
                continue
            k = key.get(tuple(int(v) for v in cell[y, x, :3]))
            if not k or k < 3 or cell[y, x, 3] == 0:          # only on lit cloth: on shadow steps the lines read as specks
                continue
            if all(cell[yy, xx, 3] and tuple(int(v) for v in cell[yy, xx, :3]) in key
                   for yy, xx in ((y - 1, x), (y + 1, x))):
                out[y, x, :3] = ramp[k - 1]
    return out


# ---------------------------------------------------------------- the whole frame stage

def make_frames(spec, log=print):
    """Returns (atlas RGBA uint8 of cell x cell frames, cols, clips {name: [atlas index...]})."""
    p, t = spec["params"], spec["target"]
    CELL, BODY_H, BASE = t["cell"], t["body_h"], t["baseline"]
    rgb, fg = load_source(ROOT / spec["source"], spec["background"], p["key_dist"])
    boxes = find_cells(fg)
    got = [len(r) for r in boxes]
    assert got == spec["rows"], f"frames per row {got} != spec rows {spec['rows']} (run sheet_assess.py)"
    masks = {(r, i): remove_dirt(rgb, fg, b, p["dark_wall"]) for r, row in enumerate(boxes) for i, b in enumerate(row)}
    clips = {k: [(r, i) for r, idx in v for i in idx] for k, v in spec["clips"].items()}
    ref = clips[t["scale_ref"]]
    heights = [np.ptp(np.where(masks[k].any(1))[0]) + 1 for k in ref]
    s = s0 = BODY_H * UP / float(np.median(heights))             # source px -> 4x-target px
    # row_scale {"<source row>": factor}: generators often draw some views bigger than others
    uniq = list(dict.fromkeys(k for v in clips.values() for k in v))
    cols = int(np.ceil(np.sqrt(len(uniq))))
    rows = (len(uniq) + cols - 1) // cols
    big = CELL * UP
    atlas = np.zeros((rows * big, cols * big, 4), np.uint8)
    # horizontal stretch per frame: none for lying figures (their body width is vertical), and per clip
    # no more than lets every frame of the clip fit the cell around its torso centre, so long weapons
    # are not clipped and the body keeps one width through an animation
    def reach(k):
        m = masks[k]
        ys, xs = np.where(m)
        mm = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        cx = torso_cx(mm)
        return max(cx, mm.shape[1] - cx) * s, mm.shape[1] > 1.3 * mm.shape[0]
    info = {k: reach(k) for k in uniq}
    stretch = {k: 1.0 if info[k][1] else p["x_stretch"] for k in uniq}
    for v in clips.values():
        fit = min((big / 2 - UP) / info[k][0] for k in v if not info[k][1]) if any(not info[k][1] for k in v) else 9
        for k in v:
            stretch[k] = max(1.0, min(stretch[k], fit))
    squeezed = sorted({n for n, v in clips.items() if any(stretch[k] < p["x_stretch"] and not info[k][1] for k in v)})
    if squeezed:
        log(f"x_stretch limited to fit the cell in: {', '.join(squeezed)}")
    for k, (r, i) in enumerate(uniq):
        x0, y0, _, _ = boxes[r][i]
        xs_ = stretch[(r, i)]
        s = s0 * p.get("row_scale", {}).get(str(r), 1.0)
        m = masks[(r, i)]
        c = prep(rgb[y0:y0 + m.shape[0], x0:x0 + m.shape[1]], m)
        c = smooth_shading(c, m, p["smooth"] / (s / UP), spec)
        ys, xs = np.where(m)
        m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        c = c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        h, w = m.shape
        nw, nh = max(1, round(w * s * xs_)), max(1, round(h * s))
        mf = m.astype(np.float32)
        cov = cv2.resize(mf, (nw, nh), interpolation=cv2.INTER_AREA)
        col = cv2.resize(c * mf[..., None], (nw, nh), interpolation=cv2.INTER_AREA) / np.maximum(cov[..., None], 1e-3)
        a = cov >= 0.5
        ox = int(round((big / 2 - torso_cx(m) * s * xs_) / UP)) * UP
        oy = (BASE + 1) * UP - nh
        cell = np.zeros((big, big, 4), np.float32)
        ty0, tx0, ty1, tx1 = max(0, oy), max(0, ox), min(big, oy + nh), min(big, ox + nw)
        cell[ty0:ty1, tx0:tx1, :3] = col[ty0 - oy:ty1 - oy, tx0 - ox:tx1 - ox]
        cell[ty0:ty1, tx0:tx1, 3] = a[ty0 - oy:ty1 - oy, tx0 - ox:tx1 - ox] * 255
        rr, cc = divmod(k, cols)
        atlas[rr * big:(rr + 1) * big, cc * big:(cc + 1) * big] = cell.clip(0, 255).astype(np.uint8)
    cells = [cell_view(atlas, k, cols, big) for k in range(len(uniq))]
    # rows are often lit differently by the generator: same luminance mean and spread everywhere
    stats = [(lum(c[c[..., 3] > 0]).mean(), lum(c[c[..., 3] > 0]).std()) for c in cells]
    tm, ts = np.median(stats, 0)
    for c, (mu, sd) in zip(cells, stats):
        o = c[..., 3] > 0
        v = c[o][:, :3].astype(np.float32)
        l = (v @ W3)[:, None]
        c[o, :3] = np.clip(v + ((l - mu) * (ts / max(sd, 1e-3)) + tm - l), 0, 255).astype(np.uint8)
        c[:] = form_light(c, p["form_light"], p["light"], 2 * UP)
    op = atlas[..., 3] > 0
    # unquantised colour per target pixel, to judge which pixels really changed between frames
    small_shape = (rows * CELL, cols * CELL)
    a4 = op.astype(np.float32)
    cov = cv2.resize(a4, small_shape[::-1], interpolation=cv2.INTER_AREA)
    smooth = np.zeros(small_shape + (4,), np.float32)
    for k in range(3):
        smooth[..., k] = cv2.resize(atlas[..., k] * a4, small_shape[::-1], interpolation=cv2.INTER_AREA) / np.maximum(cov, 1e-3)
    thin = thin_parts(op, UP)
    atlas[op, :3] = map_to_ramps(atlas[op][:, :3].astype(np.float32), spec, thin[op]).astype(np.uint8)
    pal = palette_of(spec)
    res = unfake.process_image_sync(atlas, max_colors=len(pal), fixed_palette=pal, manual_scale=UP, snap_grid=False,
                                    downscale_method="dominant")
    small = np.array(res["image"].convert("RGBA")) if isinstance(res["image"], Image.Image) else np.array(res["image"])
    assert small.shape[:2] == small_shape, small.shape
    alpha = small[..., 3] > 127
    small[..., 3] = alpha * 255
    small[~alpha] = 0
    small = despeckle(small)
    seqs = [[uniq.index(k) for k in v] for v in clips.values()]
    register(small, smooth, seqs, cols, CELL, p["register_reach"])
    if p["stable_tol"]:
        stabilise(small, smooth, seqs, cols, CELL, p["stable_tol"])
    small = drop_crumbs(small)
    if p["thin_darks"]:
        for k in range(len(uniq)):
            c = cell_view(small, k, cols, CELL)
            c[:] = thin_darks(c, spec, p["thin_darks"])
    if p["wraps"]:
        for k in range(len(uniq)):
            c = cell_view(small, k, cols, CELL)
            c[:] = add_wraps(c, spec, p["wraps"])
    ncol = len(np.unique(small[small[..., 3] > 0][:, :3], axis=0))
    log(f"{len(uniq)} frames, scale {s0 / UP:.3f}, {ncol} colours")
    return small, cols, {k: [uniq.index(x) for x in v] for k, v in clips.items()}


# ---------------------------------------------------------------- hand edits as data

def head_anchor(a):
    """(top row, centre x) of the head: erode away thin parts (staffs, bows, arms), take the
    largest blob, and measure its top few rows."""
    m = (a[..., 3] > 0).astype(np.uint8)
    e = cv2.erode(m, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(e, connectivity=4)
    if n < 2:
        return None
    body = cv2.dilate((lab == 1 + st[1:, 4].argmax()).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & (m > 0)
    ys = np.where(body.any(1))[0]
    top = ys[0]
    xs = np.where(body[top:top + 5].any(0))[0]
    return int(top), (xs[0] + xs[-1]) / 2


def apply_patch(a, patch, legend):
    """Stamp a text grid onto a frame. Glyphs map to colours; '.' keeps the pixel underneath and '_'
    erases it. Placed relative to the head (anchor "head") or at absolute frame coordinates."""
    rows = patch["rows"]
    h, w = len(rows), len(rows[0])
    if patch.get("anchor", "head") == "head":
        hd = head_anchor(a)
        if hd is None:
            return a
        top, cx = hd
        x, y = int(round(cx - (w - 1) / 2)) + patch.get("dx", 0), top + patch.get("dy", 0)
    else:
        x, y = patch.get("x", 0), patch.get("y", 0)
    out = a.copy()
    # "clear": [rows, margin] erases the old pixels beside the template's top `rows` rows (the generated
    # head is often wider than the designed one and would leave a dark hood around it)
    if "clear" in patch:
        cr, mg = patch["clear"]
        for j in range(min(cr, h)):
            yy = y + j
            if not 0 <= yy < out.shape[0]:
                continue
            xs = [i for i, ch in enumerate(rows[j]) if ch not in "._"]
            if not xs:
                continue
            for xx in list(range(x + xs[0] - mg, x + xs[0])) + list(range(x + xs[-1] + 1, x + xs[-1] + 1 + mg)):
                if 0 <= xx < out.shape[1]:
                    out[yy, xx] = 0
        if y - 1 >= 0:   # and the row above the head
            out[max(0, y - mg):y, max(0, x - mg):x + w + mg] = 0
    for j, row in enumerate(rows):
        assert len(row) == w, f"ragged patch row {j}: {row!r}"
        for i, ch in enumerate(row):
            yy, xx = y + j, x + i
            if ch == "." or not (0 <= yy < out.shape[0] and 0 <= xx < out.shape[1]):
                continue
            out[yy, xx] = (0, 0, 0, 0) if ch == "_" else (*hexrgb(legend[ch]), 255)
    return out


def load_patches(spec):
    f = spec["_dir"] / "patches.json"
    return json.loads(f.read_text()) if f.exists() else {"legend": {}, "templates": {}, "apply": []}


def patch_frame(a, clip, i, patches):
    """Apply every patch rule that names this clip and frame index (in the clip, as authored).
    A rule: {"clip", "template", "frames": [..] (omit for all), "skip": [..], "dx", "dy",
    "per_frame": {"<i>": {"dx": .., "dy": ..}}}."""
    for rule in patches["apply"]:
        if rule["clip"] != clip or i in rule.get("skip", []) or ("frames" in rule and i not in rule["frames"]):
            continue
        t = {**patches["templates"][rule["template"]], **{k: rule[k] for k in ("dx", "dy", "anchor", "x", "y", "clear") if k in rule}}
        for k, v in rule.get("per_frame", {}).get(str(i), {}).items():
            t[k] = t.get(k, 0) + v if k in ("dx", "dy") else v
        a = apply_patch(a, t, patches["legend"])
    return a


# ---------------------------------------------------------------- review numbers

def churn(frames):
    """Share of body pixels (opaque in both) that change colour between consecutive frames."""
    vals = []
    for p, c in zip(frames, frames[1:] + frames[:1]):
        both = (p[..., 3] > 0) & (c[..., 3] > 0)
        if both.sum():
            vals.append(((p[..., :3] != c[..., :3]).any(-1) & both).sum() / both.sum())
    return float(np.mean(vals)) if vals else 0.0


def isolated(frame):
    """Opaque pixels whose colour matches none of their 4 neighbours (confetti)."""
    a = frame[..., 3] > 0
    key = frame[..., 0].astype(np.int32) << 16 | frame[..., 1].astype(np.int32) << 8 | frame[..., 2]
    key = np.where(a, key, -1)
    P = np.pad(key, 1, constant_values=-2)
    same = (P[:-2, 1:-1] == key) | (P[2:, 1:-1] == key) | (P[1:-1, :-2] == key) | (P[1:-1, 2:] == key)
    return int((a & ~same).sum())
