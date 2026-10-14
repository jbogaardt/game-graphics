"""Designed side-view legs for the yeti's walk (the generated side walk barely moves its feet, so it slides).
Draws an 8-frame stride (contact, down, passing, up, for each leg) as patch templates and writes them, with
their apply rules on walk_right, into patches.json. Rerun after changing a pose, then rebuild.

Usage: uv run python -I assets/abominable-snowman/make_legs.py
"""
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
W, H = 33, 14            # template size; row 0 is sprite row 48, row 13 the baseline (61)
KEEP_ROWS = 3            # rows 48-50 merge into the belly: keep what is there
HAND_X = 24              # rows 51-52 right of this hold the hanging hand: keep them too
NEAR_HIP, FAR_HIP = (19, 2), (15, 2)

# per frame: near leg (ankle x, lift, knee), far leg (ankle x, lift, knee). lift raises the foot off the ground,
# knee pushes the knee forward (+) or back (-) from the hip-ankle line
POSES = [
    ((26, 0, 1), (8, 0, 1)),     # contact: near foot forward, far foot back (heel just touching)
    ((24, 0, 3), (10, 1, 3)),    # down: weight on the near leg, knee bends
    ((19, 0, 2), (16, 3, 5)),    # passing: far leg swings through, knee high
    ((14, 0, -1), (22, 2, 4)),    # up: near leg pushes off
    ((10, 0, 1), (24, 0, 1)),    # contact: far foot forward, near foot back
    ((12, 1, 3), (22, 0, 3)),    # down
    ((16, 3, 5), (16, 0, 2)),    # passing: near leg swings through
    ((22, 2, 4), (13, 0, -1)),    # up
]


def leg(hip, ankle_x, lift, knee):
    """Masks of a thick furred leg (hip to knee to ankle, thighs thicker) and a foot pointing right."""
    m = np.zeros((H, W), bool)
    ay = H - 3 - lift
    kx, ky = (hip[0] + ankle_x) / 2 + knee, (hip[1] + ay) / 2
    ys, xs = np.mgrid[0:H, 0:W]
    for (x0, y0, r0), (x1, y1, r1) in (((hip[0], hip[1], 3.9), (kx, ky, 3.3)), ((kx, ky, 3.3), (ankle_x, ay, 2.6))):
        for t in np.linspace(0, 1, 30):
            cx, cy, r = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t
            m |= (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
    # fur tufts: a pixel sticking out behind the calf and in front of the knee
    for dy, side in ((1, -1), (-1, 1)):
        y = int(round(ky)) + dy
        row = np.where(m[y])[0] if 0 <= y < H else []
        if len(row):
            x = row[0] - 1 if side < 0 else row[-1] + 1
            if 0 <= x < W:
                m[y, x] = True
    foot = np.zeros_like(m)
    foot[ay:ay + 3, max(0, ankle_x - 3):min(W, ankle_x + 6)] = True
    foot[ay, ankle_x + 4:] = False              # rounded toe
    return m & ~foot, foot


def shade_leg(grid, mask, foot, ramp, H_=None):
    """Light from the top left: across each row the leg runs light, mid, shadow (back edge darkest), and the
    shin is one step darker than the thigh. ramp is 4 glyphs, dark to light. Feet use the two darkest steps
    with a 1 px light top and a claw line."""
    rows = np.where(mask.any(1))[0]
    top, bot = (rows.min(), rows.max()) if len(rows) else (0, 0)
    for y in rows:
        xs = np.where(mask[y])[0]
        x0, x1 = xs.min(), xs.max()
        low = (y - top) / max(bot - top, 1) > 0.55
        for x in xs:
            t = (x - x0) / max(x1 - x0, 1)
            step = 3 if t < 0.34 else 2 if t < 0.75 else 1
            if low:
                step -= 1
            if x == x1:
                step = min(step, 1)
            grid[y, x] = ramp[max(step, 0)]
    for y, x in zip(*np.where(foot)):
        below = y + 1 >= H or not foot[y + 1, x]
        above = y == 0 or not foot[y - 1, x]
        grid[y, x] = ramp[0] if below else ramp[2] if above else ramp[1]
    fy = np.where(foot.any(1))[0]
    if len(fy):
        xs = np.where(foot[fy[-1] - 1])[0]
        if len(xs) > 2:
            grid[fy[-1] - 1, xs[-1]] = "O"           # claw tip


def draw(pose):
    (nx, nl, nk), (fx, fl, fk) = pose
    near, nfoot = leg(NEAR_HIP, nx, nl, nk)
    far, ffoot = leg(FAR_HIP, fx, fl, fk)
    grid = np.full((H, W), "_", object)
    grid[:KEEP_ROWS] = "."
    grid[KEEP_ROWS:KEEP_ROWS + 2, HAND_X:] = "."
    nearall = near | nfoot
    farall = (far | ffoot) & ~nearall
    shade_leg(grid, far & ~nearall, ffoot & ~nearall, ["1", "2", "2", "3"])
    shade_leg(grid, near, nfoot, ["2", "3", "4", "5"])
    # belly fur hangs over the tops of the legs: a ragged hem
    for x in range(W):
        if (nearall | farall)[KEEP_ROWS, x] and x % 3 != 1:
            grid[KEEP_ROWS, x] = "4" if x % 3 else "5"
    # outline: around the legs below the belly, and between the near leg and the far one
    union = nearall | farall
    P = np.pad(union, 1)
    ring = ~union & (P[:-2, 1:-1] | P[2:, 1:-1] | P[1:-1, :-2] | P[1:-1, 2:])
    Pn = np.pad(nearall, 1)
    split = farall & ~nearall & (Pn[:-2, 1:-1] | Pn[2:, 1:-1] | Pn[1:-1, :-2] | Pn[1:-1, 2:])
    for y, x in zip(*np.where(ring | split)):
        if y > KEEP_ROWS and grid[y, x] != ".":
            grid[y, x] = "O"
    return ["".join(r) for r in grid]


def main():
    p = HERE / "patches.json"
    d = json.loads(p.read_text())
    d["apply"] = [r for r in d["apply"] if not r["template"].startswith("legs_side")]
    for i, pose in enumerate(POSES):
        d["templates"][f"legs_side_{i}"] = {"rows": draw(pose)}
        # fixed position: the frames are registered, so the hips do not move, but the head bobs
        d["apply"].append({"clip": "walk_right", "template": f"legs_side_{i}", "frames": [i], "anchor": "abs", "x": 14, "y": 48})
    p.write_text(json.dumps(d, indent=2))
    for i in (0, 2):
        print(f"legs_side_{i}"); print("\n".join(d["templates"][f"legs_side_{i}"]["rows"]))


if __name__ == "__main__":
    main()
