# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Workflows for managing graphical assets (pixel-art sprites and sprite sheets) for games. There is no build system or test suite. Update this file as scripts, asset folders, or tooling are added.

## Asset pipeline

```
[Google Photos] → [Gemini / image gen] → raw sprite sheet PNG
  → [Downscale & quantize] → snap to true pixel grid + fixed palette
  → [Aseprite] → slice frames, set layers & tags
  → [Claude Code + Aseprite MCP] → programmatic cleanup, outlines, animation tweaks
```

### Step 1: Pre-process in Aseprite (manual)
- Generated sheets are often high-res (e.g. 1024×1024). Determine the intended per-frame size (e.g. 32×32) and downscale with **Sprite > Sprite Size** using **Nearest Neighbor** only — never a smoothing filter.
- Convert to indexed color (**Sprite > Color Mode > Convert to Indexed**) with a fixed palette (typically 16 or 32 colors) to eliminate blurred in-between pixels.
- Split poses into sequential frames on the timeline.

### Step 2: Refinement via MCP (Claude's role)
With an Aseprite MCP server (e.g. `aseprite-mcp` / `aseprite-ai-artist`) connected, Claude inspects the canvas and runs Lua against the open Aseprite session. Expected tasks:

1. **Line cleanup ("de-jaggies")** — remove 2-pixel "doubles" on curved edges (hair, jawline) so curves are clean single-pixel lines.
2. **Palette harmonization** — merge near-identical shades into defined highlight/shadow ramps and remap the canvas to the reduced palette.
3. **Outlines** — add a layer named `Outline` *behind* the character on every frame with a 1px selective dark outline around the silhouette.
4. **Frame alignment & timing** — find the bottom-most opaque pixel per frame and align all frames to a common baseline (e.g. `y=28` for 32px sprites) to stop jitter/sliding; set frame durations (e.g. 120ms) and tag ranges (e.g. `walk`).

### Conventions when editing sprites
- Preserve the hard pixel grid: no anti-aliasing, no non-nearest-neighbor resampling, no colors outside the active palette.
- Apply edits across all frames of an animation consistently unless told otherwise.
- Check which MCP server/tools are actually available in the session before assuming Lua access to Aseprite.

## Mummy sprite sheet (`assets/mummy/`, `tools/`)

Target game is `../me_rpg`: top-down, LPC paper-doll characters in **64×64 frames**, about **46px tall**, feet on row **y=61**, rows ordered up/left/down/right. The mummy is a standalone sheet, not an LPC part.

- Sources: `assets/mummy/src/mummy1.jpeg` (front view + side/attack rows) and `mummy2.jpeg` (back view row). Both are smooth AI art with a baked-in checkerboard — **not** on a pixel grid (edge-periodicity test found none), so nearest-neighbour downscaling gives noise.
- `tools/mummy_frames.py` is the one exception to "nearest-neighbour only": it area-averages sprite pixels only (never the checkerboard), hard-thresholds alpha, stretches levels, snaps every frame to one shared 24-colour palette, majority-filters noise, and anchors by feet and torso centre. The output still has no anti-aliasing, no semi-transparent pixels and no off-palette colours. Keep that guarantee if you change it.
- `tools/mummy_build.py` assembles tags (left = mirrored right; idle = breathing bob on a neutral walk pose; hurt = first death frames), builds `assets/mummy/mummy.aseprite` (Character + Outline layers, per-frame durations, 18 tags). Run from the repo root: `uv run python tools/mummy_build.py` — needs `aseprite` on PATH.
- Export from the live window with the `export` MCP tool (packed sheet + JSON atlas) to `dist/mummy_sheet.png/.json`.
- Only walk and idle exist for up/down; thrust, slash, shoot, hurt and death are left/right only (the source has no vertical views of them).

## Sprite viewer (`viewer/`)

`cd viewer && npm start` serves a PixiJS 8 page at http://localhost:5173/ that plays any `dist/<name>_sheet.json` + `.png` (Aseprite array-format atlas with tags named `<action>_<direction>`). Walk with WASD, attacks on `1`-`9`, `H` hurt, `X` die. Re-export a sheet and press Reload. See `viewer/README.md` for the tag conventions.

## Lessons and known issues (read before starting a sprite job)

Written after the mummy job, where the first pass was thrown away. Check these before spending tokens.

**Before touching pixels**
- Look at the target game first and write down frame size, character height, feet row, direction order and palette cap (see the mummy section for `../me_rpg`). Do not guess 32×32 from the generic pipeline above.
- Test whether the source is on a pixel grid (edge-energy periodicity over periods 2-8; a ratio near 1.0 means no grid). AI "pixel art" almost never is. If it is not, say so up front: detail will not survive a ~2× or greater downscale and the result will be grainy.
- Inspect the sheet rows for consistency before slicing: equal frame counts, same scale and ground line, a real walk cycle (one profile row turned mid-cycle), a baked-in checkerboard (JPEG noise breaks colour keys), missing idle or up/down attacks.

**Mistakes to avoid**
- Nearest-neighbour on non-grid AI art gives noise; area averaging gives grain. Neither fixes the source. Neither the majority filter, the palette cap nor the contrast stretch removed the grain.
- Hand-drawing parts in Aseprite to fill missing views produced art that did not match the generated art. Prefer asking for the missing views from the image source.
- Do not run `validate` unscoped on a many-frame sprite: it returns one finding per frame (about 140 results, almost all the `Outline` layer). Pass `checks` explicitly and skip `strays` for outline layers.
- Pass `includePalette:false` to `sprite_info`; the palette dump is 256 entries.
- Read crops of images, not the whole sheet, and do not re-view an unchanged sheet.

**MCP gaps (`aseprite-live`)**
- No "import sheet as N frames" op, so slicing needs `aseprite -b --script` Lua plus a file round-trip. The scripts in `tools/` already do this.
- `validate` counts diagonal-only outline pixels as isolated: 2,837 flagged vs 118 when diagonals count as connected. Treat `Outline`-layer stray errors as false positives and say so.
- Only the open document is editable live; scripts write files that must be reopened. Close the stale sprite first.

**Token efficiency**
- Put deterministic steps in scripts (`tools/mummy_frames.py`, `tools/mummy_build.py`) and rerun them; spend tokens on judgement and looking.
- One batched call per layer or per task, one filmstrip per review round.

**What to ask the image supplier for**
- Exact target spec (cell size, character height, directions, palette size, flat shading, 1px dark outline, no anti-aliasing) plus a screenshot of the target game's sprites as a style reference.
- PNG, a flat solid background (for example magenta), equal cells, same ground line, same frame count per row, one direction per row, an idle row, and attack rows for every direction wanted.
- Ideally a generator that outputs a true pixel grid, or large blocks (each art pixel exactly 4×4) so downscaling is an exact integer. Or reuse LPC parts (`../me_rpg/public/sprites/lpc/`) and recolour them.

## Python tooling (uv)

The repo is a uv project (`pyproject.toml`, `uv.lock`; `.venv/` is ignored). Run scripts with `uv run python tools/<script>.py`; add dependencies with `uv add`. Dependencies: `pillow`, `numpy`, `unfake` (which pulls in `opencv-python`; Python >= 3.12).

### unfake test on the mummy (`tools/unfake_test.py`, output in `assets/mummy/unfake_test/`)

`unfake` (https://pypi.org/project/unfake/) snaps AI pixel art to a true grid. On these sheets:
- **Auto scale detection fails.** It collapsed 60×104 figures to 11×20 or smaller because the art has no grid.
- **Manual `manual_scale=2`** gives a ~52px figure; `dominant` (picks real source colours instead of averaging) is slightly crisper than our area-average and keeps a bit more detail, but it is just another downscaler: the grain comes from the source texture, so it is not a fix. `median` and `content-adaptive` left magenta fringe when the key colour was used as background.
- It adds no outline and has no notion of frames, so anchoring, mirroring and the shared palette still come from `tools/`.
- Conclusion: unfake helps only when the source is already close to a pixel grid. For non-grid art, regenerate the source or reuse LPC parts.
