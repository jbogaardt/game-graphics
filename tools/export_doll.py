"""Repack an exported sheet (dist/<name>_sheet.png|json, Aseprite array atlas with <action>_<dir> tags)
into the me_rpg "doll sheet" layout (../me_rpg/src/sprites/doll.ts), so the game's Character class can
play it like any LPC character or mob.

Usage: uv run python -I tools/export_doll.py assets/<name>/sprite.json
Writes dist/<name>_doll.png (832x1600) and dist/<name>_doll.json (which tag and frame filled every
cell, and every fallback used). The spec's "doll" maps game animations to sprite actions, e.g.
{"walk": "walk", "idle": "idle", "cast": "shoot", "slash": "thrust", "shoot": "shoot", "hurt": "death_right"}
("hurt" is one row shared by all directions, and LPC's hurt is the collapse, so a death tag fits).
Frames are resampled by time to the doll's column count; a missing direction falls back to the
nearest side view and is reported.
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spritekit as sk

# mirrors ANIMS in ../me_rpg/src/sprites/doll.ts
ANIMS = {
    "walk": {"y": 0, "size": 64, "cols": 9, "rows": 4},
    "idle": {"y": 256, "size": 64, "cols": 2, "rows": 4},
    "cast": {"y": 512, "size": 64, "cols": 7, "rows": 4},
    "hurt": {"y": 768, "size": 64, "cols": 6, "rows": 1},
    "slash": {"y": 832, "size": 128, "cols": 6, "rows": 4},
    "shoot": {"y": 1344, "size": 64, "cols": 13, "rows": 4},
}
DIRS = ["up", "left", "down", "right"]
FALLBACK = {"up": ["left", "right"], "down": ["right", "left"], "left": ["right"], "right": ["left"]}
WIDTH, HEIGHT = 832, 1600


def load_sheet(name):
    dist = sk.ROOT / "dist"
    j = json.load(open(dist / f"{name}_sheet.json"))
    img = np.array(Image.open(dist / f"{name}_sheet.png").convert("RGBA"))
    frames = []
    for f in j["frames"]:
        r, s, src = f["frame"], f["spriteSourceSize"], f["sourceSize"]
        cell = np.zeros((src["h"], src["w"], 4), np.uint8)
        cell[s["y"]:s["y"] + s["h"], s["x"]:s["x"] + s["w"]] = img[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
        frames.append((cell, f["duration"]))
    tags = {t["name"]: list(range(t["from"], t["to"] + 1)) for t in j["meta"]["frameTags"]}
    return frames, tags


def resample(idx, frames, n):
    """n frames evenly spaced in time over the tag (holds stay long, quick in-betweens may drop)."""
    d = np.array([frames[i][1] for i in idx], float)
    ends = np.cumsum(d)
    return [idx[int(np.searchsorted(ends, (k + 0.5) * ends[-1] / n, side="right").clip(0, len(idx) - 1))] for k in range(n)]


def main(spec_path):
    spec = sk.load_spec(spec_path)
    name, mapping = spec["name"], spec["doll"]
    frames, tags = load_sheet(name)
    sheet = np.zeros((HEIGHT, WIDTH, 4), np.uint8)
    report = {"cells": {}, "fallbacks": []}

    def find(action, d):
        if action in tags:                       # a fixed tag shared by every direction
            return action, False
        for dd in [d] + FALLBACK[d]:
            if f"{action}_{dd}" in tags:
                return f"{action}_{dd}", dd != d
        return None, True

    for anim, a in ANIMS.items():
        action = mapping.get(anim)
        for row, d in enumerate(DIRS[:a["rows"]] if a["rows"] == 4 else ["any"]):
            tag, fell = find(action, "right" if d == "any" else d) if action else (None, True)
            if tag is None:
                report["fallbacks"].append(f"{anim} {d}: no tag for '{action}', left empty")
                continue
            if fell:
                report["fallbacks"].append(f"{anim} {d}: uses {tag}")
            idx = tags[tag]
            if anim == "walk":
                idle = find(mapping.get("idle", "idle"), tag.rsplit("_", 1)[-1] if tag.count("_") else d)[0]
                cols = [tags[idle][0] if idle else idx[0]] + resample(idx, frames, 8)   # col 0 is the neutral pose
            elif anim == "idle":
                cols = [idx[0], idx[len(idx) // 2]]                                      # rest, breath
            elif anim == "shoot":
                # the game plays columns 5-12 and lets go at 9; 0-4 are the start of the draw
                cols = [idx[0]] * 5 + resample(idx, frames, 8)
            else:
                cols = resample(idx, frames, a["cols"])
            report["cells"][f"{anim}.{d}"] = {"tag": tag, "frames": cols}
            S = a["size"]
            for c, fi in enumerate(cols):
                f = frames[fi][0]
                h, w = f.shape[:2]
                y0 = a["y"] + row * S + (S - h) // 2
                x0 = c * S + (S - w) // 2
                sheet[y0:y0 + h, x0:x0 + w] = f
    dist = sk.ROOT / "dist"
    Image.fromarray(sheet, "RGBA").save(dist / f"{name}_doll.png")
    json.dump(report, open(dist / f"{name}_doll.json", "w"), indent=1)
    print(f"wrote {dist / (name + '_doll.png')} ({WIDTH}x{HEIGHT})")
    for f in report["fallbacks"]:
        print("  fallback:", f)


if __name__ == "__main__":
    main(sys.argv[1])
