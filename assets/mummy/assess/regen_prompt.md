# Regeneration prompt

Why: missing rows: attack up, walk down, attack down

Paste into Gemini (attach the current sheet when asking for extra rows), save the result as a PNG and put it in assets/<name>/src/.

```
Pixel-art sprite sheet of a pharaoh mummy: bandaged linen body, gold-and-lapis striped nemes headdress, bare skull face with glowing red eyes, a staff with a red orb and a bow, for a top-down action RPG in the style of the Liberated Pixel Cup
(LPC) sprites: 3/4 top-down camera, chunky proportions, light from the top left. Make ONLY these additional rows, matching the attached sheet exactly.

Rows, top to bottom, one animation and one direction per row (facing left is mirrored in the game, do not draw it):
1. melee attack facing away from the camera (back view), 6 frames: wind-up, strike, follow-through, recover
2. ranged attack facing away from the camera (back view), 6 frames: draw, aim, release, recover
3. walk cycle facing the camera (front view), 8 frames
4. melee attack facing the camera (front view), 6 frames: wind-up, strike, follow-through, recover
5. ranged attack facing the camera (front view), 6 frames: draw, aim, release, recover

Layout: every frame in an equal square cell, the same character size and design in every frame, feet on the same
ground line, the whole character (weapon included) inside its cell.
Rendering: crisp pixel art, hard edges, flat shading in 3-4 tones per material with light, mid and shadow clearly
separated, a 1 px dark outline only around the silhouette (no thick dark masses inside the body), no anti-aliasing,
no blur, no gradients, no noise texture. At most 16 colours. Use only these colours: outline #1d1016; linen #3b2320 #5e3d2d #84623f #ab8c5c #d0b986; gold #7a4f22 #c8902f #f2cf6b; lapis #1c2246 #33508e #5b7fc4; red #5a1422 #b0263a #f0585a.
Nothing under the feet: no ground, no dust, no debris, no floor shadow.
Deliver a PNG, not a JPEG.
A true pixel grid: draw the character about 46 px tall and upscale by exactly 4x with nearest neighbour, so every art pixel is a 4x4 block.
Identical character size in every frame and row, feet on one ground line.
No text, labels, grid lines, borders or watermark. Output: PNG.
```
