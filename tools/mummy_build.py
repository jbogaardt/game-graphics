"""Build assets/mummy/mummy.aseprite from the generated sheets.

Usage: python3 -I tools/mummy_build.py        (needs `aseprite` on PATH)
Stages: mummy_frames.main -> canonical frames -> per-tag layout (left = mirrored right) -> Aseprite
file with a Character layer, an Outline layer behind it, per-frame durations and tags.
"""
import json, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
import mummy_frames as mf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/mummy"
C = mf.CELL

# tag -> (clip, direction handling, durations in ms)
# direction: "as" = use clip as authored; "mirror" = flip the right-facing clip for left
TAGS = [
    ("idle_up", "idle:walk_up", "as", [200, 200, 200, 200]),
    ("idle_left", "idle:walk_right", "mirror", [200, 200, 200, 200]),
    ("idle_down", "idle:walk_down", "as", [200, 200, 200, 200]),
    ("idle_right", "idle:walk_right", "as", [200, 200, 200, 200]),
    ("walk_up", "walk_up", "as", [100] * 7),
    ("walk_left", "walk_right", "mirror", [110] * 6),
    ("walk_down", "walk_down", "as", [100] * 7),
    ("walk_right", "walk_right", "as", [110] * 6),
    ("thrust_left", "thrust_right", "mirror", [100, 80, 60, 60, 60, 60, 80, 80, 80, 80, 90, 100]),
    ("thrust_right", "thrust_right", "as", [100, 80, 60, 60, 60, 60, 80, 80, 80, 80, 90, 100]),
    ("slash_left", "slash_right", "mirror", [110, 90, 70, 70, 90, 120]),
    ("slash_right", "slash_right", "as", [110, 90, 70, 70, 90, 120]),
    ("shoot_left", "shoot_right", "mirror", [140, 80, 80, 140, 80, 120]),
    ("shoot_right", "shoot_right", "as", [140, 80, 80, 140, 80, 120]),
    ("hurt_left", "hurt:death_right", "mirror", [80, 120, 120, 80]),
    ("hurt_right", "hurt:death_right", "as", [80, 120, 120, 80]),
    ("death_left", "death_right", "mirror", [120, 120, 140, 160, 200, 500]),
    ("death_right", "death_right", "as", [120, 120, 140, 160, 200, 500]),
]


def breathe(frame):
    """Idle from a neutral pose: lift everything above the waist by one pixel on alternate frames."""
    a = np.array(frame)
    ys = np.where((a[..., 3] > 0).any(1))[0]
    top, bot = ys[0], ys[-1]
    waist = top + int((bot - top) * 0.55)
    out = a.copy()
    out[top - 1:waist] = a[top:waist + 1]      # upper body moves up one row
    out[waist] = a[waist + 1]                  # close the seam
    return Image.fromarray(out, "RGBA")


def neutral(frames):
    """The frame whose feet are closest together."""
    def spread(f):
        a = np.array(f)[..., 3] > 0
        ys = np.where(a.any(1))[0]
        band = a[ys[-1] - 9:ys[-1] - 2]
        w = [np.where(r)[0] for r in band if r.any()]
        return np.mean([x[-1] - x[0] for x in w])
    return min(frames, key=spread)


def main():
    tmp = Path(tempfile.mkdtemp())
    mf.main(tmp)
    sheet = Image.open(tmp / "frames.png").convert("RGBA")
    meta = json.load(open(tmp / "frames.json"))
    cols = meta["cols"]

    def frame(i):
        r, c = divmod(i, cols)
        return sheet.crop((c * C, r * C, (c + 1) * C, (r + 1) * C))

    clips = {k: [frame(i) for i in v] for k, v in meta["clips"].items()}
    layout, spec = [], []
    for row, (tag, src, how, durs) in enumerate(TAGS):
        if src.startswith("idle:"):
            n = neutral(clips[src[5:]])
            b = breathe(n)
            fr = [n, n, b, b]
        elif src.startswith("hurt:"):
            d = clips[src[5:]]
            fr = [d[0], d[1], d[1], d[0]]
        else:
            fr = clips[src]
        if how == "mirror":
            fr = [ImageOps.mirror(f) for f in fr]
        assert len(fr) == len(durs), (tag, len(fr), len(durs))
        layout.append(fr)
        spec.append({"name": tag, "row": row, "n": len(fr), "durations": durs})
    width = max(len(r) for r in layout) * C
    img = Image.new("RGBA", (width, len(layout) * C), (0, 0, 0, 0))
    for r, fr in enumerate(layout):
        for c, f in enumerate(fr):
            img.paste(f, (c * C, r * C))
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / "layout.png")
    json.dump(spec, open(OUT / "layout.json", "w"), indent=1)

    lua = f'''
local sheet = Image{{ fromFile = "{OUT / 'layout.png'}" }}
local spec = {{}}
{chr(10).join(f'spec[#spec+1]={{name="{t["name"]}",row={t["row"]},n={t["n"]},d={{{",".join(map(str, t["durations"]))}}}}}' for t in spec)}
local spr = Sprite({C}, {C}, ColorMode.INDEXED)
local function key(v) return app.pixelColor.rgbaR(v)..","..app.pixelColor.rgbaG(v)..","..app.pixelColor.rgbaB(v) end
local idx, list = {{}}, {{}}
for p in sheet:pixels() do
  local v = p()
  if app.pixelColor.rgbaA(v) > 0 then
    local k = key(v)
    if not idx[k] then
      list[#list+1] = Color{{r=app.pixelColor.rgbaR(v), g=app.pixelColor.rgbaG(v), b=app.pixelColor.rgbaB(v)}}
      idx[k] = #list
    end
  end
end
local darkest, dl = 1, 1e9
for i, c in ipairs(list) do local l = c.red*3 + c.green*6 + c.blue if l < dl then dl = l darkest = i end end
local pal = Palette(#list + 1)
pal:setColor(0, Color{{r=0,g=0,b=0,a=0}})
for i, c in ipairs(list) do pal:setColor(i, c) end
spr:setPalette(pal)
local outl = spr:newLayer() outl.name = "Outline"
local char = spr.layers[1] char.name = "Character"
outl.stackIndex = 1
local fi = 0
app.transaction(function()
  for _, t in ipairs(spec) do
    for c = 0, t.n - 1 do
      fi = fi + 1
      if fi > 1 then spr:newEmptyFrame() end
      local img = Image({C}, {C}, ColorMode.INDEXED)
      local o = Image({C}, {C}, ColorMode.INDEXED)
      local solid = {{}}
      for y = 0, {C-1} do for x = 0, {C-1} do
        local v = sheet:getPixel(c*{C} + x, t.row*{C} + y)
        if app.pixelColor.rgbaA(v) > 0 then img:putPixel(x, y, idx[key(v)]) solid[y*{C}+x] = true end
      end end
      for y = 0, {C-1} do for x = 0, {C-1} do
        if not solid[y*{C}+x] and ((x>0 and solid[y*{C}+x-1]) or (x<{C-1} and solid[y*{C}+x+1]) or (y>0 and solid[(y-1)*{C}+x]) or (y<{C-1} and solid[(y+1)*{C}+x])) then o:putPixel(x, y, darkest) end
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
  if t.name:find("death") then tag.repeats = 1 end
  fi = fi + t.n
end
spr:saveAs("{OUT / 'mummy.aseprite'}")
print(#spr.frames, #spr.palettes[1], #spr.tags)
'''
    lf = tmp / "build.lua"
    lf.write_text(lua)
    r = subprocess.run(["aseprite", "-b", "--script", str(lf)], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip())


if __name__ == "__main__":
    main()
