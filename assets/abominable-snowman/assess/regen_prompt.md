# Regeneration prompt

Why: missing rows: attack up, attack left, attack down, attack right

Paste into Gemini (attach the current sheet when asking for extra rows), save the result as a PNG and put it in assets/<name>/src/.

```
Pixel-art sprite sheet of an abominable snowman (yeti): hulking white-and-pale-blue furred body, slate-blue hands, feet and face, curled tan ram horns, glowing cyan eyes, fanged mouth, for a top-down action RPG in the style of the Liberated Pixel Cup
(LPC) sprites: 3/4 top-down camera, chunky proportions, light from the top left. Make ONLY these additional rows, matching the attached sheet exactly.

Rows, top to bottom, one animation and one direction per row (facing left is mirrored in the game, do not draw it):
1. melee attack facing the camera (front view), 6 frames: wind-up, strike, follow-through, recover
2. melee attack facing away from the camera (back view), 6 frames: wind-up, strike, follow-through, recover
3. melee attack facing right (side view), 6 frames: wind-up, strike, follow-through, recover

Layout: every frame in an equal square cell, the same character size and design in every frame, feet on the same
ground line, the whole character (weapon included) inside its cell.
Rendering: crisp pixel art, hard edges, flat shading in 3-4 tones per material with light, mid and shadow clearly
separated, a 1 px dark outline only around the silhouette (no thick dark masses inside the body), no anti-aliasing,
no blur, no gradients, no noise texture. At most 16 colours. Use only these colours: outline #1a1c3f; fur #3a3570 #56609a #7f93c6 #b4cbec #eef6ff; horn #5e4636 #93785e #c9b28e; glow #3fd6ef #c9fbff.
A true pixel grid: draw the character about 46 px tall and upscale by exactly 4x with nearest neighbour, so every art pixel is a 4x4 block.
No text, labels, grid lines, borders or watermark. Output: PNG.
```
