# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Turn generated (AI) sprite sheets into game-ready pixel-art sprites for `../me_rpg`. There is no test suite.
Update this file as scripts, asset folders or tooling are added.

## Workflow: the `sprite-sheet` skill

**Follow `.claude/skills/sprite-sheet/SKILL.md` for any sprite job.** It defines the stages and their gates:
intake (is the sheet usable?) → spec → build preview → polish (patches) → review → export → report. Its
`prompt-template.md` is the prompt to hand the image generator when a sheet must be regenerated or rows are
missing. The lessons from the mummy job (sparkle, what failed, MCP gaps) are in the skill.

Hooks in `.claude/settings.json` (both `PostToolUse`, both only add a reminder):
- after a live Aseprite `draw`/`recolor`/`transform`: copy edits to a built sprite into `assets/<name>/patches.json`,
  or the next build loses them;
- after a `Bash`/`Write` that puts an image into `assets/<name>/src/` (`.claude/hooks/intake_reminder.py`): run the
  intake check and, if the sheet falls short, show the user `assess/regen_prompt.md` to steer the image generator.

For drawing a sprite from scratch (no source sheet) use the Aseprite MCP's own skills (`skill://brief`,
`skill://concept`, `skill://draw`, `skill://animate`, `skill://review`) and its rulebook (`rules://index`,
especially `rules://92-generated-art-tells` and `rules://32-heads-and-faces`).

## Tools (`tools/`, run from the repo root with `uv run python -I tools/<tool>.py`)

| Tool | Does |
|---|---|
| `sheet_assess.py <img> [--spec S] [--out D]` | Intake report: background, rows and figures, ground line, scale, pixel-grid test, dirt, coverage of the views the game needs; writes `contact.png` and, unless the verdict is GO, `regen_prompt.md` (a filled-in prompt for Gemini asking for exactly what is wrong or missing); verdict GO / GO WITH GAPS / REGENERATE |
| `spritekit.py` | Shared pipeline (key, dirt removal, luminance blur, form light, designed-ramp mapping, unfake on one atlas, register, stabilise, crumbs, wraps, head-anchored patches, metrics) |
| `build_sprite.py <spec> [--preview]` | Spec to `layout.png`, `preview.png`, `<name>.aseprite` (Character + selective Outline layer, tags, durations) and `dist/<name>_sheet.png/.json` via the aseprite CLI. Close the sprite in Aseprite first |
| `sprite_metrics.py <spec>` | Per-tag churn (sparkle), isolated pixels, feet rows, colours used, and the style check against the LPC reference characters (height, width, median brightness, near-black interior, outline thickness, colours); exits 3 if the style is off |
| `export_doll.py <spec>` | `dist/<name>_sheet.*` to the game's doll layout `dist/<name>_doll.png/.json` (832x1600, mirrors `ANIMS` in `../me_rpg/src/sprites/doll.ts`), listing fallbacks |
| `mummy_frames.py`, `unfake_test.py` | Legacy experiments on the old `mummy1/2.jpeg` sources; not part of the workflow |

Each sprite lives in `assets/<name>/`: `src/` (source images), `sprite.json` (the spec: rows, clips, tags,
designed palette, params, doll mapping, missing views), `patches.json` (hand-designed pixel templates and where
they are stamped), and generated `layout.*`, `preview.png`, `assess/`, `<name>.aseprite`.

Output guarantees: no anti-aliasing, no semi-transparent pixels, every colour from the spec palette (the build
asserts this), feet on the baseline row.

## Target game (`../me_rpg`)

Top-down, LPC paper-doll characters in **64x64 frames**, about **46 px tall**, feet on row **61**, rows
up/left/down/right, light from the top left. Mobs render with the same `Character` class as the player, from a
doll sheet: walk 9 cols, idle 2, cast 7, hurt 6 (one row), slash 6 in 128 px cells, shoot 13. Mobs use `cast` for
ranged attacks and `slash` for melee. LPC reference art: `../me_rpg/public/sprites/lpc/` (e.g. `body.zombie.0.png`).

## Mummy (`assets/mummy/`)

- Source `src/mummy3.jpeg`: pharaoh mummy, flat magenta, rows 7,7,6,6,6,6,6,6. Row 0 is the **back** walk, row 1 the
  side walk (right), rows 2-3 thrust, row 4 misc (frame 1 = front idle), row 5 slash (swings left), row 6 bow, row
  7 hurt (0-1) + death. No front walk and no up/down attacks: `walk_down` and the up/down attack rows of the doll
  sheet fall back to side views (listed in `dist/mummy_doll.json`). The user's own 16-colour unfake of the sheet,
  `src/mummy3_unfaked.png`, is not used by the pipeline.
- Palette (16 colours): outline, a hue-shifted 5-step linen ramp, gold 3, lapis 3, red 3, bone highlight. Linen
  value `shares` put half the body on the lightest step, as in LPC.
- Patches: `nemes_back`, `skull_front` (also used for the 3/4 attack poses) and `skull_profile` (with the false
  beard) heads, stamped on every frame of their clips.
- Params: `x_stretch` 1.32 (limited per clip for thrust, slash and shoot so weapons fit), `thin_darks` 4,
  `form_light` 45, `wraps` 4 (bandage lines), `stable_tol` 44.
- Style vs LPC zombie/skeleton walks: height 45 (46-47), width 28 (28), median brightness 144 (141-183), near-black
  interior 12% (4-10%, within tolerance), outline ring 5% (4-10%), 14 colours. Churn: walks ~29%, idles ~18%,
  attacks 32-47%. The first pass was ~58% churn and median brightness 36.
- Shoot frame 1's bow tip touches the top of the 64 px cell.
- Rebuild: `uv run python -I tools/build_sprite.py assets/mummy/sprite.json && uv run python -I tools/export_doll.py assets/mummy/sprite.json`.

## Sprite viewer (`viewer/`)

`cd viewer && npm start` serves http://localhost:5173/?sprite=<name>, a minimal PixiJS page that plays
`dist/<name>_doll.png` exactly as the game does (animation table, timings, feet anchor, shadow, walk speed, integer
zoom; constants copied from `../me_rpg`). WASD walk, `1` slash, `2` cast, `3` shoot, `H` hurt, `R` reload after a
rebuild. See `viewer/README.md`.

`dist/` is committed: it holds only the current exports (`<name>_sheet.png/.json` Aseprite atlas and
`<name>_doll.png/.json` game layout). Delete stale files when a sprite is renamed or dropped.

## Python tooling (uv)

uv project (`pyproject.toml`, `uv.lock`; `.venv/` ignored). Dependencies: `pillow`, `numpy`, `unfake` (pulls in
`opencv-python`; Python >= 3.12). Add dependencies with `uv add`. `aseprite` must be on PATH for builds.

unfake findings: auto scale detection fails on smooth AI art (no grid); `manual_scale` with `dominant` works as a
grid snapper on frames prepared at an exact integer multiple (the pipeline uses 4x), but it is a downscaler, not a
fix for texture grain.
