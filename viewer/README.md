# Sprite viewer

Local PixiJS 8 page for watching an exported Aseprite sheet animate. Reusable for any sprite.

```bash
cd viewer
npm install        # once
npm start          # http://localhost:5173/   (PORT=8080 npm start to change)
```

It lists every `../dist/<name>_sheet.json` (+ `<name>_sheet.png`) and opens `?sprite=<name>`.
Export from Aseprite as a spritesheet with a JSON atlas in **array** format and frame tags; the viewer
builds its controls from the tag names. After re-exporting, press **Reload sheet**.

## Tag naming

`<action>_<direction>` with direction `up|down|left|right`, e.g. `walk_left`, `thrust_right`.

| Action | Used for |
|---|---|
| `idle`, `walk` (or `run`) | played automatically while you hold WASD / arrows |
| `hurt`, `death` | `H` and `X`; `death` plays once and holds its last frame |
| anything else (`thrust`, `slash`, `shoot`, ...) | numbered keys `1`-`9`, in tag order; plays once, then back to idle |

A tag without a direction suffix (`spin`) is shown as a single clip. If an action has no tag for up/down,
the last left/right facing is used. Frame durations come from the atlas.

## Controls

WASD / arrows move, `1`-`9` actions, `H` hurt, `X` die, `R` revive, `Space` pause then `,` `.` to step frames.
The side panel has zoom, animation and walk speed, backgrounds (check outlines on grass/sand/light),
a cell-box overlay, tag buttons that loop any tag, and a demo that cycles every tag.

Only `server.mjs` (no dependencies) and `pixi.js` are needed; it serves `../dist/` read-only.
