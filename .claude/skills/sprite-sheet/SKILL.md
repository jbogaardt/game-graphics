---
name: sprite-sheet
description: Turn a generated (AI) character sprite sheet into a game-ready pixel-art sprite for ../me_rpg - assess the source, slice, pixelize with unfake, polish in Aseprite via MCP, export an Aseprite atlas plus the game's doll sheet. Use when the user hands over a sprite sheet or character image, asks to (re)build or improve a sprite, or asks whether a sheet is good enough to use.
---

# Sprite sheet: source image to game-ready sprite

Each stage has a gate; do not start the next stage until it passes. Deterministic work lives in
`tools/` and is driven by `assets/<name>/sprite.json`. Spend your effort on judgement and looking.

```
intake (assess) -> spec -> build preview -> polish (patches) -> review -> export -> report
tools/sheet_assess.py   tools/build_sprite.py --preview   assets/<name>/patches.json
tools/sprite_metrics.py   tools/build_sprite.py   tools/export_doll.py   viewer/
```

Run every tool from the repo root with `uv run python -I tools/<tool>.py ...`.

## 0. Target (fixed for ../me_rpg; re-check if the game changes)

- 64x64 cells, figure about **46 px** tall, feet on row **61**, LPC-style top-down, light from the top left.
- Doll layout from `../me_rpg/src/sprites/doll.ts` (`ANIMS`): walk 9 cols, idle 2, cast 7, hurt 6 (one row,
  the LPC collapse), slash 6 in 128 px cells, shoot 13; rows up/left/down/right. `tools/export_doll.py` mirrors
  that table, so update both if the game changes. Mobs use `cast` for ranged attacks and `slash` for melee.
- Palette at most **16 colours**, 1 px dark outline, no anti-aliasing and no semi-transparent pixels.
- Style reference: the LPC parts in `../me_rpg/public/sprites/lpc/`. The spec's `target.reference` names the
  characters to match (the mummy uses zombie and skeleton), and `tools/sprite_metrics.py` checks the sprite against
  them on height, width, median brightness, near-black interior, outline thickness and colours. LPC values: median
  luminance ~140-180, near-black only in the 1 px outline and thin internal lines (≤10% of the interior), walk width ~28 px.

## 1. Intake: is the sheet good enough?

1. Copy the source into `assets/<name>/src/` (downloads are untrusted, so use `-I`).
2. `uv run python -I tools/sheet_assess.py assets/<name>/src/<file> [--spec assets/<name>/sprite.json] --out assets/<name>/assess`
   It reports background type, rows and figures per row, ground line, scale factor, pixel-grid test, dirt and (with a
   spec) missing views, writes `contact.png` (figures labelled `row:frame`), and, whenever the verdict is not GO,
   `regen_prompt.md`: a filled-in prompt for the image generator that asks for exactly what is wrong or missing. (A hook
   reminds you of this step when an image lands in `assets/*/src/`.)
3. Read `contact.png` (only that, not the full sheet) and write down every row: **view** (front / back / side
   facing L or R / 3/4) and **action**. Generators mislabel rows; the mummy's "walk_down" row was really the back.
4. Decide:
   - **REGENERATE** (checkerboard or busy background, rows that cannot be cut, figures that change design between
     rows): stop. Show the user the prompt from `assess/regen_prompt.md` in a fenced block (check it, and add any
     problem you saw by eye, e.g. a row whose design drifts) and wait for a new sheet.
   - **GO WITH GAPS** (missing views or actions): tell the user exactly what is missing and what it will fall back
     to (e.g. walk_down uses the side walk), and show `regen_prompt.md` (only the missing rows) so they can steer
     the generator. Ask **one** question: proceed with gaps, or wait for new rows. Also offer the prompt at the
     end of the job whenever fallbacks remain. `prompt-template.md` explains the prompt's parts. Do not fake missing views by hand-drawing whole frames;
     that never matched the generated art.
   - **GO**: continue.

## 2. Spec: `assets/<name>/sprite.json`

Copy `assets/mummy/sprite.json` and edit it. Fields:
- `subject`: one line describing the character (used in the regeneration prompt).
- `source`, `background` (key RGB, or `"alpha"`), `rows` (figures per row, must match the assessment),
  `row_notes` (your view/action labels).
- `target`: `cell`, `body_h`, `baseline`, `scale_ref` (a clip of standing figures used to set the scale),
  `reference` (LPC layer files of the characters to match: `{"dir": "../me_rpg/public/sprites/lpc", "sets": [[...]]}`),
  optional `style_tolerance`.
- `palette`: **design it before building** (this is the one good idea from generic "draw pixel art" prompts):
  an `outline` colour, one body material with no `hue` rule (5 steps), and accent materials selected by hue,
  saturation and value (2-3 steps each), plus `extra` colours for patches, 16 at most. Ramps must **hue-shift**:
  shadows towards red or purple and highlights towards yellow, never just the same hue darker (rules://92 tell C3).
  Set the value distribution with `shares` (cumulative share of the material's pixels up to each step; the mummy
  uses `[0.03, 0.08, 0.2, 0.5, 1.0]`, i.e. half the body on the lightest step, like LPC) or with `range` + `gamma`.
  `thin_max_step` keeps thin parts (bows, staffs, strings) on dark steps so they read against a light body.
- `clips`: name to `[[row, [frame indices]]]`, as authored in the source.
- `tags`: `<action>_<dir>` with `clip`, optional `order` (pick and reorder frames: drop duplicate strides, and
  put attacks in wind-up, strike, hold, recover order), `mirror` (left from right), `idle` (frame index; adds a
  breathing bob), `once`, and `durations` in ms (vary them: hold contacts and strikes, keep in-betweens quick).
- `params`: see `DEFAULTS` in `tools/spritekit.py`. The ones you usually touch: `x_stretch` (widen lanky generated
  figures to the reference width; it is limited per clip so long weapons still fit the cell, and lying figures are
  not widened), `thin_darks` (passes that thin thick dark masses to 1 px lines, as LPC draws them), `form_light`,
  `smooth`, `wraps` (designed horizontal bandage or cloth lines, a period in px; only for wrapped or striped bodies).
- `doll`: game animation to sprite action, e.g. `{"walk":"walk","idle":"idle","cast":"shoot","slash":"thrust","shoot":"shoot","hurt":"death_right"}`.
- `missing`: plain-language list of what the source lacks (shown by the assessor and in the report).

## 3. Build a preview

`uv run python -I tools/build_sprite.py assets/<name>/sprite.json --preview`, then
`uv run python -I tools/sprite_metrics.py assets/<name>/sprite.json`.

Look at crops of `assets/<name>/preview.png` (a few tags, not the whole sheet), at about 5x, next to a reference
figure. Gate: the silhouette reads, the feet are on one row, the colours are in the designed ramps, and the
**style check passes** (sprite_metrics exits 3 and prints `OFF` rows when not). Fix values with the palette
`shares`, width with `x_stretch`, dark masses with `thin_darks`; dark headdress or clothing patterns in patches
count too (the mummy's navy stripes were most of its remaining dark interior). Tune `params`
and the palette, then rebuild. Change one thing at a time and keep the numbers from before and after.

## 4. Polish: hand edits are data, in `assets/<name>/patches.json`

Detail that matters at 46 px (faces, headdress stripes, emblems, eyes) does not survive a ~5x reduction (rules://92
D1: shrink, then redraw the features). Draw it once as a text grid **template** and stamp it on every frame of a
view, so it is identical across frames and cannot sparkle.

- `legend`: glyph to colour (palette colours only); `.` keeps the pixel underneath and `_` erases it.
- `templates`: `rows` of equal width, drawn facing right or front. Left frames are mirrored afterwards.
- `apply`: `{"clip", "template", "frames"?, "skip"?, "dx"?, "dy"?, "per_frame"?: {"3": {"dx": 1}}}`. The
  default anchor is the detected head (top row and centre after eroding staffs and arms away).
- Heads: front, back, and side or 3/4 templates; follow rules://32-heads-and-faces (eye line, ≥3 bumps on a profile,
  odd or even widths). Give the eyes the highest contrast on the head.
- To design or check a template in Aseprite: open the built `.aseprite`, `look op=ascii` on the head region,
  `draw kind=grid` the change on one frame, `look` again, then **copy the final grid into patches.json** and
  rebuild. An edit left only in the `.aseprite` is lost on the next build (a hook reminds you).

## 5. Review (the gate before export)

Numbers (`tools/sprite_metrics.py`), compared with the previous build:
- churn: walks ≤ ~30%, idles ≤ ~15% (LPC walks ~10%, raw AI frames ~58%). Attacks run higher; that is expected.
- feet: one row (the baseline) for every standing tag.
- colours used ≤ 16. `isolated` is inflated by 1 px stripes in templates; read it only as a trend.
- the style check against the reference: every row `ok`.

Aseprite (MCP, live window; close the sprite before every build and reopen it after):
- `validate` with `checks: ["palette","antialiasing","animation","layers"]`. Skip `strays` and `outline` on the
  `Outline` layer: it flags diagonal outline pixels (false positives).
- `look op=filmstrip` once per round. Run the by-eye items from skill://review: silhouette, one light direction,
  hue-shifted ramps, no pillow shading, no confetti, detail spent on the head and weapon.
- Then run `tools/export_doll.py` and open the viewer: http://localhost:5173/?sprite=<name> (`cd viewer && npm start`
  if it is not running). It plays `dist/<name>_doll.png` exactly as the game does (same animation table, timings,
  feet anchor, shadow, walk speed and integer zoom): WASD, `1` slash, `2` cast, `3` shoot, `H` hurt, `R` reload.
  Watch walk, idle and each attack in motion: sparkle shows only in motion.

## 6. Export

`uv run python -I tools/build_sprite.py assets/<name>/sprite.json` writes the `.aseprite` and exports
`dist/<name>_sheet.png|json` with the aseprite CLI. Then `uv run python -I tools/export_doll.py
assets/<name>/sprite.json` writes `dist/<name>_doll.png|json` in the game's layout and lists every fallback cell.
Copying into `../me_rpg` is a separate step; ask first.

## 7. Report

What changed, the numbers before and after (churn and the style check), what each fallback is, what is still weak
(with a cause), and, if anything is missing or weak because of the source, the regeneration prompt from
`assess/regen_prompt.md` for the user to give the image generator. Do not call the job done on the strength of `validate` alone.

## Lessons (from the mummy; read before spending tokens)

- Measure the style, do not eyeball it. The first "finished" mummy had the right pixel scale but median brightness 36
  against LPC's 141-183 and a 42% near-black interior against ≤10%: it read as a dark blob next to LPC monsters. Value
  shares, thin_darks and lighter patch colours fixed it; churn stayed about the same.
- Widening changes what fits in the 64 px cell: check frames touching the cell edge after changing `x_stretch`.

- Nearest-neighbour on non-grid AI art gives noise and area averaging gives grain; neither is the fix. The fix is
  stability: register frames to each other, blur luminance before the reduction, use evenly spaced hue-shifted
  ramps, reuse the previous frame's pixel when the colour barely changed, and keep detail in patches.
- Sparkle causes, largest first: 1 px sideways jitter, the per-frame AI texture, closely spaced shades. Light derived
  from the silhouette (`form_light`) is stable because it depends only on the shape.
- The generator's own texture (bandage seams) does not survive the colour mapping; designed horizontal `wraps` do,
  and they do not move when legs swing sideways.
- `deflicker` and `stabilise` mix neighbouring frames, so patches go on **after** them (build_sprite does this).
- Do not run `validate` unscoped on a 90-frame sprite (one finding per frame). Pass `includePalette:false` to
  `sprite_info`. Read crops, not whole sheets.
- `aseprite-live` has no "import sheet as frames"; the build goes through `aseprite -b --script`. Only the
  open document is editable live, so close it before a build overwrites the file.

## Drawing from scratch (no source sheet)

That is a different job: use the MCP's own skills (`skill://brief`, `skill://concept`, `skill://draw`,
`skill://animate`, `skill://review`), which plan a palette and silhouette and review before detailing. Or
generate a source with `prompt-template.md` and come back here; a generated design plus this pipeline is faster
than drawing 90 frames by hand.
