"""Review numbers for a built sprite, per tag: churn (share of body pixels that change colour between
consecutive frames; LPC walks ~10%, raw AI frames ~58%), confetti (isolated pixels per frame),
colours used, and the feet row. Then a style check: the walk frames against the reference characters in
spec target.reference (LPC walks from ../me_rpg), on height, width, median brightness, near-black interior,
near-black second ring (outline thickness) and colours. Reads assets/<name>/layout.png|json and adds the
Outline layer the way the build does, so it works on --preview builds.

Usage: uv run python -I tools/sprite_metrics.py assets/<name>/sprite.json [--json]
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spritekit as sk


def measure(spec):
    d, C = spec["_dir"], spec["target"]["cell"]
    img = np.array(Image.open(d / "layout.png").convert("RGBA"))
    out = {}
    for t in json.load(open(d / "layout.json")):
        fr = [img[t["row"] * C:(t["row"] + 1) * C, c * C:(c + 1) * C] for c in range(t["n"])]
        feet = {int(np.where((f[..., 3] > 0).any(1))[0][-1]) for f in fr}
        out[t["name"]] = {
            "churn": round(sk.churn(fr) if t["n"] > 1 else 0.0, 3),
            "isolated": round(float(np.mean([sk.isolated(f) for f in fr])), 1),
            "feet": sorted(feet),
        }
    used = np.unique(img[img[..., 3] > 0][:, :3], axis=0)
    return out, len(used)


def with_outline(f, outline):
    """The build's Outline layer: a 1 px outline behind every edge that is not already outline-coloured."""
    o = sk.hexrgb(outline)
    a = f[..., 3] > 0
    solid = a & ~(f[..., :3] == o).all(-1)
    P = np.pad(solid, 1)
    ring = ~a & (P[:-2, 1:-1] | P[2:, 1:-1] | P[1:-1, :-2] | P[1:-1, 2:])
    out = f.copy()
    out[ring] = (*o, 255)
    return out


def sheet_frames(spec):
    """Frames per tag as the game sees them: layout.png with the Outline layer composited."""
    d, C = spec["_dir"], spec["target"]["cell"]
    img = np.array(Image.open(d / "layout.png").convert("RGBA"))
    o = spec["palette"]["outline"]
    return {t["name"]: [with_outline(img[t["row"] * C:(t["row"] + 1) * C, c * C:(c + 1) * C], o) for c in range(t["n"])]
            for t in json.load(open(d / "layout.json"))}


def style(spec, tags=None):
    """[(metric, ours, reference range, ok)] for the walk frames against the reference characters."""
    refs = sk.reference_frames(spec)
    if not refs:
        return []
    tags = tags or sheet_frames(spec)
    ours = sk.style_stats([f for k, v in tags.items() if k.startswith("walk") for f in v])
    rs = [sk.style_stats(fr) for fr in refs.values()]
    lo = {k: min(r[k] for r in rs) for k in ours}
    hi = {k: max(r[k] for r in rs) for k in ours}
    tol = spec["target"].get("style_tolerance", {})
    rows = []
    for k, fmt in (("height", "{:.0f}"), ("width", "{:.0f}"), ("median_lum", "{:.0f}"),
                   ("interior_dark", "{:.0%}"), ("ring_dark", "{:.0%}"), ("colours", "{:.0f}")):
        t = tol.get(k, {"height": 2, "width": 2, "median_lum": 25, "interior_dark": 0.05, "ring_dark": 0.05, "colours": 0}[k])
        if k in ("interior_dark", "ring_dark"):
            ok = ours[k] <= hi[k] + t
        elif k == "colours":
            ok = ours[k] <= max(16, hi[k])
        else:
            ok = lo[k] - t <= ours[k] <= hi[k] + t
        rows.append((k, fmt.format(ours[k]), f"{fmt.format(lo[k])}-{fmt.format(hi[k])}", ok))
    return rows


def print_style(spec, tags=None):
    rows = style(spec, tags)
    if not rows:
        return True
    names = ", ".join(sk.reference_frames(spec))
    print(f"style vs reference walks ({names}):")
    for k, o, r, ok in rows:
        print(f"  {k:14} {o:>6}   reference {r:>10}   {'ok' if ok else 'OFF'}")
    return all(r[3] for r in rows)


if __name__ == "__main__":
    spec = sk.load_spec(sys.argv[1])
    per, ncol = measure(spec)
    if "--json" in sys.argv:
        print(json.dumps({"tags": per, "colours": ncol}))
        sys.exit()
    print(f"{'tag':14} churn  isolated/frame  feet rows")
    for k, v in per.items():
        print(f"{k:14} {v['churn']:5.0%}  {v['isolated']:8.1f}        {v['feet']}")
    groups = {}
    for k, v in per.items():
        groups.setdefault(k.split("_")[0], []).append(v["churn"])
    print("mean churn by action:", {k: f"{np.mean(v):.0%}" for k, v in groups.items()}, f"| colours used: {ncol}")
    sys.exit(0 if print_style(spec) else 3)
