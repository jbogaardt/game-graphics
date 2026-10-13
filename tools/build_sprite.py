"""Build a game-ready sprite from a spec: frames -> patches -> tags -> .aseprite -> dist sheet.

Usage (repo root, close the sprite in Aseprite first):
  uv run python -I tools/build_sprite.py assets/<name>/sprite.json            full build + export
  uv run python -I tools/build_sprite.py assets/<name>/sprite.json --preview  layout.png + preview only

Writes assets/<name>/layout.png|json, assets/<name>/preview.png (3x, every tag on a grass-coloured
background), assets/<name>/<name>.aseprite (Character + an Outline layer that only fills in where the figure's edge is not already dark, palette in ramp order,
per-frame durations, tags) and dist/<name>_sheet.png|json (packed sheet, array JSON, tags) through
the aseprite CLI. Hand edits belong in assets/<name>/patches.json so a rebuild keeps them.
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script dir
import spritekit as sk


def deflicker(frames, cyclic):
    """Where the frames before and after agree on an interior pixel and this frame alone differs,
    take theirs (one-frame shading blips read as sparkle)."""
    n = len(frames)
    if n < 3:
        return frames
    out = [x.copy() for x in frames]
    for i in range(n):
        if not cyclic and i in (0, n - 1):
            continue
        p, c, q = frames[(i - 1) % n], frames[i], frames[(i + 1) % n]
        solid = (p[..., 3] > 0) & (c[..., 3] > 0) & (q[..., 3] > 0)
        inner = solid.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            inner &= np.roll(np.roll(solid, dy, 0), dx, 1)
        same = (p == q).all(-1) & (p != c).any(-1) & inner
        out[i][same] = p[same]
    return out


def breathe(a):
    """Idle from a neutral pose: everything above the waist up one pixel."""
    ys = np.where((a[..., 3] > 0).any(1))[0]
    top, bot = ys[0], ys[-1]
    waist = top + int((bot - top) * 0.55)
    out = a.copy()
    out[top - 1:waist] = a[top:waist + 1]
    out[waist] = a[waist + 1]
    return out


def layout(spec):
    small, cols, clips = sk.make_frames(spec)
    C = spec["target"]["cell"]
    patches = sk.load_patches(spec)
    frames = {k: [sk.cell_view(small, i, cols, C).copy() for i in v] for k, v in clips.items()}
    rows, meta = [], []
    for r, t in enumerate(spec["tags"]):
        src, clip = frames[t["clip"]], t["clip"]
        # patches go on after deflicker: deflicker must not mix a hand-drawn face with its neighbours
        if "idle" in t:
            n = sk.drop_crumbs(sk.patch_frame(src[t["idle"]], clip, t["idle"], patches))   # clearing can orphan pixels
            b = breathe(n)
            fr = [n, n, b, b]
        else:
            order = t.get("order", range(len(src)))
            fr = deflicker([src[i] for i in order], cyclic=not t.get("once") and t["name"].startswith(("walk", "idle")))
            fr = [sk.drop_crumbs(sk.patch_frame(f, clip, i, patches)) for f, i in zip(fr, order)]
        if t.get("mirror"):
            fr = [f[:, ::-1].copy() for f in fr]
        assert len(fr) == len(t["durations"]), (t["name"], len(fr), len(t["durations"]))
        rows.append(fr)
        meta.append({"name": t["name"], "row": r, "n": len(fr), "durations": t["durations"], "once": bool(t.get("once"))})
    img = np.zeros((len(rows) * C, max(len(r) for r in rows) * C, 4), np.uint8)
    for r, fr in enumerate(rows):
        for c, f in enumerate(fr):
            img[r * C:(r + 1) * C, c * C:(c + 1) * C] = f
    pal = set(sk.palette_of(spec))
    used = {"#%02x%02x%02x" % tuple(p) for p in np.unique(img[img[..., 3] > 0][:, :3], axis=0)}
    off = used - pal - set(patches["legend"].values())
    assert not off, f"colours outside the spec palette: {sorted(off)}"
    return img, meta, rows


def preview(img, meta, path, C, scale=3):
    bg = np.zeros_like(img); bg[..., :3] = (88, 110, 72); bg[..., 3] = 255
    a = img[..., 3:].astype(np.float32) / 255
    out = (img[..., :3] * a + bg[..., :3] * (1 - a)).astype(np.uint8)
    Image.fromarray(out).resize((out.shape[1] * scale, out.shape[0] * scale), Image.NEAREST).save(path)


LUA = r'''
local sheet = Image{ fromFile = "%(layout)s" }
local spec = {}
%(spec)s
local hexes = { %(palette)s }
local spr = Sprite(%(C)d, %(C)d, ColorMode.INDEXED)
local pal = Palette(#hexes + 1)
pal:setColor(0, Color{r=0,g=0,b=0,a=0})
local idx = {}
for i, h in ipairs(hexes) do
  local c = Color{r=tonumber(h:sub(2,3),16), g=tonumber(h:sub(4,5),16), b=tonumber(h:sub(6,7),16)}
  pal:setColor(i, c)
  idx[c.red..","..c.green..","..c.blue] = i
end
spr:setPalette(pal)
spr.transparentColor = 0
local outline = 1
local function key(v) return app.pixelColor.rgbaR(v)..","..app.pixelColor.rgbaG(v)..","..app.pixelColor.rgbaB(v) end
local outl = spr:newLayer() outl.name = "Outline"
local char = spr.layers[1] char.name = "Character"
outl.stackIndex = 1
local C = %(C)d
local fi = 0
app.transaction(function()
  for _, t in ipairs(spec) do
    for c = 0, t.n - 1 do
      fi = fi + 1
      if fi > 1 then spr:newEmptyFrame() end
      local img = Image(C, C, ColorMode.INDEXED)
      local o = Image(C, C, ColorMode.INDEXED)
      local solid = {}
      for y = 0, C-1 do for x = 0, C-1 do
        local v = sheet:getPixel(c*C + x, t.row*C + y)
        if app.pixelColor.rgbaA(v) > 0 then
          local k = idx[key(v)]
          assert(k, "colour not in palette: "..key(v))
          img:putPixel(x, y, k)
          -- only edges that are not already outline-coloured get an outline (no 2 px dark borders)
          if k ~= outline then solid[y*C+x] = true end
        end
      end end
      for y = 0, C-1 do for x = 0, C-1 do
        if not solid[y*C+x] and ((x>0 and solid[y*C+x-1]) or (x<C-1 and solid[y*C+x+1]) or (y>0 and solid[(y-1)*C+x]) or (y<C-1 and solid[(y+1)*C+x])) then o:putPixel(x, y, outline) end
      end end
      spr:newCel(char, spr.frames[fi], img, Point(0,0))
      spr:newCel(outl, spr.frames[fi], o, Point(0,0))
      spr.frames[fi].duration = t.d[c+1] / 1000
    end
  end
end)
fi = 0
for _, t in ipairs(spec) do
  local tag = spr:newTag(fi + 1, fi + t.n)
  tag.name = t.name
  if t.once then tag.repeats = 1 end
  fi = fi + t.n
end
spr:saveAs("%(out)s")
print(#spr.frames, #spr.palettes[1], #spr.tags)
'''


def main(spec_path, only_preview=False):
    spec = sk.load_spec(spec_path)
    d, name, C = spec["_dir"], spec["name"], spec["target"]["cell"]
    img, meta, _ = layout(spec)
    Image.fromarray(img, "RGBA").save(d / "layout.png")
    json.dump(meta, open(d / "layout.json", "w"), indent=1)
    preview(img, meta, d / "preview.png", C)
    print(f"layout: {len(meta)} tags, {sum(m['n'] for m in meta)} frames -> {d / 'preview.png'}")
    if only_preview:
        return
    pal = sk.palette_of(spec)
    pal += [c for c in sk.load_patches(spec)["legend"].values() if c not in pal]
    lua = LUA % {
        "layout": d.resolve() / "layout.png", "C": C, "out": d.resolve() / f"{name}.aseprite",
        "palette": ", ".join(f'"{h}"' for h in pal),
        "spec": "\n".join(f'spec[#spec+1]={{name="{t["name"]}",row={t["row"]},n={t["n"]},once={str(t["once"]).lower()},'
                          f'd={{{",".join(map(str, t["durations"]))}}}}}' for t in meta),
    }
    lf = Path(tempfile.mkdtemp()) / "build.lua"
    lf.write_text(lua)
    r = subprocess.run(["aseprite", "-b", "--script", str(lf)], capture_output=True, text=True)
    print("aseprite:", r.stdout.strip(), r.stderr.strip())
    assert r.returncode == 0 and "error" not in r.stderr.lower()
    dist = sk.ROOT / "dist"
    dist.mkdir(exist_ok=True)
    r = subprocess.run(["aseprite", "-b", str(d / f"{name}.aseprite"), "--sheet-pack", "--list-tags", "--format", "json-array",
                        "--sheet", str(dist / f"{name}_sheet.png"), "--data", str(dist / f"{name}_sheet.json")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    print(f"exported {dist / (name + '_sheet.png')} + .json")


if __name__ == "__main__":
    main(sys.argv[1], "--preview" in sys.argv)
