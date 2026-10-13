"""Intake check for a generated sprite sheet: is it good enough to start work on?

Usage: uv run python -I tools/sheet_assess.py <image> [--spec assets/<name>/sprite.json] [--out DIR]

Measures what can be measured and writes DIR/contact.png (every detected figure, numbered row:frame,
on a neutral grey) so the views (front/back/side, which action) can be judged by eye. Prints a report
and a verdict:
  GO           flat background, consistent rows, every required view present
  GO WITH GAPS usable, but views or actions are missing (they fall back to other views)
  REGENERATE   the sheet cannot be cut reliably or is too inconsistent; ask for a new one
Exit code 0 / 1 / 2 for the three verdicts.
"""
import argparse, json, sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spritekit as sk

# what the target game (../me_rpg doll sheet) plays, per direction
REQUIRED = {"walk": "up left down right", "idle": "up left down right", "hurt": "any",
            "attack": "up left down right"}
ATTACKS = ("slash", "thrust", "shoot", "cast", "attack")


def background(rgb, alpha):
    """Classify the background from the border pixels."""
    if alpha is not None and (alpha < 10).mean() > 0.2:
        return "alpha", None, []
    b = np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3), rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)])
    q = (b // 16).astype(int)
    keys, counts = np.unique(q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2], return_counts=True)
    order = counts.argsort()[::-1]
    share = counts[order[:2]] / len(b)
    top = b[(q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]) == keys[order[0]]].mean(0)
    notes = []
    if len(order) > 1 and share[1] > 0.25:
        notes.append("two dominant border colours: probably a baked-in checkerboard (JPEG noise breaks the key)")
        return "checkerboard", top, notes
    spread = np.abs(b - top).sum(1)
    if np.percentile(spread, 90) > 60:
        notes.append("border is not one flat colour (gradient, texture or scenery)")
        return "busy", top, notes
    r, g, bl = top
    if not (r > 180 and bl > 180 and g < 120):
        notes.append(f"flat but not magenta ({'#%02x%02x%02x' % tuple(int(v) for v in top)}): fine if no sprite colour is near it")
    return "flat", top, notes


def grid_ratio(rgb, fg):
    """Edge-energy periodicity over periods 2-8 inside the figures; ~1.0 means no pixel grid."""
    l = sk.lum(rgb)
    dx = np.abs(np.diff(l, axis=1)) * (fg[:, 1:] & fg[:, :-1])
    prof = dx.sum(0)
    best = (1.0, 0)
    for p in range(2, 9):
        phase = [prof[k::p].mean() for k in range(p)]
        r = max(phase) / max(np.mean(phase), 1e-6)
        if r > best[0]:
            best = (r, p)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--spec")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    path = Path(a.image)
    im = Image.open(path)
    spec = sk.load_spec(a.spec) if a.spec else None
    out = Path(a.out) if a.out else (spec["_dir"] / "assess" if spec else Path("assess"))
    out.mkdir(parents=True, exist_ok=True)
    rgba = np.array(im.convert("RGBA"))
    rgb = rgba[..., :3].astype(np.float32)
    alpha = rgba[..., 3] if im.mode in ("RGBA", "LA", "P") else None
    problems, gaps, notes, missing = [], [], [], []

    print(f"# Intake: {path.name}  {im.size[0]}x{im.size[1]} {im.format}")
    if im.format == "JPEG":
        notes.append("JPEG: compression noise around edges; keying needs a tolerance and a despill (handled)")
    kind, bg, bnotes = background(rgb, alpha)
    notes += bnotes
    print(f"background: {kind}" + (f" {'#%02x%02x%02x' % tuple(int(v) for v in bg)}" if bg is not None else ""))
    if kind in ("checkerboard", "busy"):
        problems.append(f"background is {kind}: ask for a flat solid background (magenta #FF00FF)")
        key = None
    else:
        key = "alpha" if kind == "alpha" else [int(v) for v in bg]
    if key is None:
        write_prompt(out, spec, problems, missing, notes)
        verdict(problems, gaps, notes)
        return
    _, fg = sk.load_source(path, key)
    cells = sk.find_cells(fg)
    counts = [len(r) for r in cells]
    print(f"rows: {len(cells)}, figures per row: {counts}")
    if spec and counts != spec["rows"]:
        problems.append(f"figures per row {counts} differ from spec rows {spec['rows']}")
    # per-row scale and ground line, with dirt removed
    heights, grounds, dirt = [], [], []
    for row in cells:
        hs, gs = [], []
        for b in row:
            m = sk.remove_dirt(rgb, fg, b)
            ys = np.where(m.any(1))[0]
            if not len(ys):
                continue
            hs.append(ys[-1] - ys[0] + 1)
            gs.append(b[1] + ys[-1])
            f = fg[b[1]:b[3], b[0]:b[2]]
            dirt.append(1 - m.sum() / max(f.sum(), 1))
        heights.append(hs); grounds.append(gs)
    for r, (hs, gs) in enumerate(zip(heights, grounds)):
        if not hs:
            continue
        ptp = int(np.ptp(gs))
        print(f"  row {r}: {len(hs)} figures, height {min(hs)}-{max(hs)} px (median {int(np.median(hs))}), ground line spread {ptp} px")
        if ptp > 0.08 * np.median(hs):
            gaps.append(f"row {r}: feet are not on one ground line (spread {ptp} px); frames will be re-anchored")
    med = [np.median(h) for h in heights if h]
    standing = np.median(med)
    if np.ptp([m for m in med if m > 0.75 * standing]) > 0.15 * standing:
        notes.append("figure heights differ by >15% between rows (weapons, crouches or a scale change): check the contact sheet; scale comes from target.scale_ref")
    if np.mean(dirt) > 0.03:
        notes.append(f"ground dirt/dust under the feet: {np.mean(dirt):.0%} of figure pixels removed by the dirt step")
    if spec:
        target = spec["target"]["body_h"]
        factor = standing / target
        print(f"scale: standing figure ~{int(standing)} px -> {target} px target = {factor:.1f}x reduction")
        if factor > 2:
            notes.append(f"{factor:.1f}x reduction: fine texture and faces will not survive; plan hand patches for the head")
    ratio, period = grid_ratio(rgb, fg)
    print(f"pixel grid: ratio {ratio:.2f}" + (f" at period {period}" if period else ""))
    if ratio < 1.3:
        notes.append("no pixel grid (smooth AI art): unfake cannot snap it; the pipeline downsamples instead")
    ncol = len(np.unique((rgb[fg] // 4).astype(int), axis=0))
    print(f"colours in figures: ~{ncol} (after 6-bit binning)")

    # coverage against the target game, from the spec's tags
    if spec:
        tags = {t["name"] for t in spec["tags"]}
        def has(action, d):
            return any(t == f"{action}_{d}" for t in tags)
        for d in "up left down right".split():
            if not has("walk", d):
                gaps.append(f"no walk_{d}"); missing.append(("walk", d))
            if not has("idle", d):
                gaps.append(f"no idle_{d}"); missing.append(("idle", d))
            if not any(has(x, d) for x in ATTACKS):
                gaps.append(f"no attack facing {d}"); missing.append(("attack", d))
        if not any(t.startswith(("hurt", "death")) for t in tags):
            gaps.append("no hurt/death"); missing.append(("hurt", "down"))
        for m in spec.get("missing", []):
            notes.append("spec: " + m)

    # contact sheet for judging views by eye
    tile = 120
    cols = max(counts)
    sheet = Image.new("RGB", (cols * tile, len(cells) * (tile + 14)), (128, 128, 128))
    dr = ImageDraw.Draw(sheet)
    for r, row in enumerate(cells):
        for i, (x0, y0, x1, y1) in enumerate(row):
            crop = Image.fromarray(rgba[y0:y1, x0:x1])
            m = Image.fromarray((fg[y0:y1, x0:x1] * 255).astype(np.uint8))
            crop.thumbnail((tile - 8, tile - 8))
            m = m.resize(crop.size)
            sheet.paste(crop.convert("RGB"), (i * tile + 4, r * (tile + 14) + 14), m)
            dr.text((i * tile + 4, r * (tile + 14)), f"{r}:{i}", fill=(255, 255, 255))
    sheet.save(out / "contact.png")
    print(f"contact sheet: {out / 'contact.png'} (label every row's view and action from this)")
    write_prompt(out, spec, problems, missing, notes)
    verdict(problems, gaps, notes)


VIEW = {"down": "facing the camera (front view)", "up": "facing away from the camera (back view)",
        "right": "facing right (side view)", "left": "facing left (side view)"}


def write_prompt(out, spec, problems, missing, notes):
    """When the sheet is not good enough, write a ready-to-paste prompt for the image generator
    (Gemini etc.) that asks for exactly what is wrong or missing: the whole sheet for a REGENERATE
    verdict, only the missing rows for GO WITH GAPS. Hand it to the user; see prompt-template.md."""
    if not problems and not missing:
        return None
    t = spec["target"] if spec else {"cell": 64, "body_h": 46}
    subject = (spec or {}).get("subject", "the same character as in the attached sheet")
    ranged = bool(spec) and any(x["name"].startswith(("shoot", "cast")) for x in spec["tags"])
    if problems or not spec:
        rows = [("walk", d) for d in ("down", "up", "right")] + [("idle", d) for d in ("down", "up", "right")]
        rows += [("attack", d) for d in ("down", "up", "right")] + [("hurt", "down")]
    else:
        rows = [(a, d) for a, d in missing if d != "left"]     # left is mirrored from right
        order = {"walk": 0, "idle": 1, "attack": 2, "hurt": 3}
        rows = sorted(dict.fromkeys(rows), key=lambda r: (order[r[0]], ["down", "up", "right"].index(r[1])))
    lines = []
    for a, d in rows:
        if a == "walk":
            lines.append(f"walk cycle {VIEW[d]}, 8 frames")
        elif a == "idle":
            lines.append(f"idle, breathing, {VIEW[d]}, 2 frames")
        elif a == "attack":
            lines.append(f"melee attack {VIEW[d]}, 6 frames: wind-up, strike, follow-through, recover")
            if ranged:
                lines.append(f"ranged attack {VIEW[d]}, 6 frames: draw, aim, release, recover")
        elif a == "hurt":
            lines.append("hit reaction and collapse to the ground, facing the camera, 6 frames")
    fixes = []
    joined = " ".join(problems + notes)
    if "checkerboard" in joined or "busy" in joined or "not one flat colour" in joined:
        fixes.append("A flat solid magenta (#FF00FF) background everywhere: no checkerboard, no gradient, no scenery.")
    if "dirt" in joined:
        fixes.append("Nothing under the feet: no ground, no dust, no debris, no floor shadow.")
    if "JPEG" in joined:
        fixes.append("Deliver a PNG, not a JPEG.")
    if "no pixel grid" in joined:
        fixes.append(f"A true pixel grid: draw the character about {t['body_h']} px tall and upscale by exactly 4x with "
                     "nearest neighbour, so every art pixel is a 4x4 block.")
    if "heights differ" in joined or "ground line" in joined:
        fixes.append("Identical character size in every frame and row, feet on one ground line.")
    pal = ""
    if spec:
        P = spec["palette"]
        ramps = "; ".join(f"{n} {' '.join(m['ramp'])}" for n, m in P["materials"].items())
        pal = f"Use only these colours: outline {P['outline']}; {ramps}."
    which = "a complete new sprite sheet" if problems or not spec else "ONLY these additional rows, matching the attached sheet exactly"
    body = "\n".join(f"{i}. {l}" for i, l in enumerate(lines, 1))
    prompt = f"""Pixel-art sprite sheet of {subject}, for a top-down action RPG in the style of the Liberated Pixel Cup
(LPC) sprites: 3/4 top-down camera, chunky proportions, light from the top left. Make {which}.

Rows, top to bottom, one animation and one direction per row (facing left is mirrored in the game, do not draw it):
{body}

Layout: every frame in an equal square cell, the same character size and design in every frame, feet on the same
ground line, the whole character (weapon included) inside its cell.
Rendering: crisp pixel art, hard edges, flat shading in 3-4 tones per material with light, mid and shadow clearly
separated, a 1 px dark outline only around the silhouette (no thick dark masses inside the body), no anti-aliasing,
no blur, no gradients, no noise texture. At most 16 colours. {pal}
{chr(10).join(fixes)}
No text, labels, grid lines, borders or watermark. Output: PNG."""
    md = (f"# Regeneration prompt\n\nWhy: {'; '.join(problems) if problems else 'missing rows: ' + ', '.join(f'{a} {d}' for a, d in missing)}\n\n"
          f"Paste into Gemini (attach the current sheet when asking for extra rows), save the result as a PNG and "
          f"put it in assets/<name>/src/.\n\n```\n{prompt}\n```\n")
    (out / "regen_prompt.md").write_text(md)
    print(f"regeneration prompt: {out / 'regen_prompt.md'} (offer it to the user)")
    return md


def verdict(problems, gaps, notes):
    for title, items in (("PROBLEMS", problems), ("GAPS", gaps), ("NOTES", notes)):
        if items:
            print(f"{title}:")
            for x in items:
                print(f"  - {x}")
    v = "REGENERATE" if problems else "GO WITH GAPS" if gaps else "GO"
    print(f"VERDICT: {v}")
    sys.exit({"GO": 0, "GO WITH GAPS": 1, "REGENERATE": 2}[v])


if __name__ == "__main__":
    main()
