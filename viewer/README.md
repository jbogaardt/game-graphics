# Sprite viewer

Plays a sprite exactly the way `../me_rpg` does, so what you see here is what the game shows. It reads
`../dist/<name>_doll.png` (written by `tools/export_doll.py`) and uses the game's animation table, cycles and
timings (`src/sprites/doll.ts`), feet anchor and shadow (`src/entities/Character.ts`), walk speed (120 px/s) and
integer camera zoom (`src/core/camera.ts`, designed for 640x440). Those constants are copied at the top of
`index.html`; keep them in step if the game changes.

```bash
cd viewer
npm install        # once
npm start          # http://localhost:5173/?sprite=<name>   (PORT=8080 npm start to change)
```

| Key | Does |
|---|---|
| WASD / arrows | walk (idle when released) |
| `1` / `2` / `3` | slash / cast / shoot (what mobs use for melee and ranged attacks) |
| `H` | hurt (the LPC collapse) |
| `R` | reload the sheet after a rebuild |
| `N` | next sprite in `dist/` |

Only `server.mjs` (no dependencies) and `pixi.js` are needed; it serves `../dist/` read-only.
