# Regeneration prompt

Why: background is busy: ask for a flat solid background (magenta #FF00FF)

Paste into Gemini (attach the current sheet when asking for extra rows), save the result as a PNG and put it in assets/<name>/src/.

```
Pixel-art sprite sheet of the same character as in the attached sheet, for a top-down action RPG in the style of the Liberated Pixel Cup
(LPC) sprites: 3/4 top-down camera, chunky proportions, light from the top left. Make a complete new sprite sheet.

Rows, top to bottom, one animation and one direction per row (facing left is mirrored in the game, do not draw it):
1. walk cycle facing the camera (front view), 8 frames
2. walk cycle facing away from the camera (back view), 8 frames
3. walk cycle facing right (side view), 8 frames
4. idle, breathing, facing the camera (front view), 2 frames
5. idle, breathing, facing away from the camera (back view), 2 frames
6. idle, breathing, facing right (side view), 2 frames
7. melee attack facing the camera (front view), 6 frames: wind-up, strike, follow-through, recover
8. melee attack facing away from the camera (back view), 6 frames: wind-up, strike, follow-through, recover
9. melee attack facing right (side view), 6 frames: wind-up, strike, follow-through, recover
10. hit reaction and collapse to the ground, facing the camera, 6 frames

Layout: every frame in an equal square cell, the same character size and design in every frame, feet on the same
ground line, the whole character (weapon included) inside its cell.
Rendering: crisp pixel art, hard edges, flat shading in 3-4 tones per material with light, mid and shadow clearly
separated, a 1 px dark outline only around the silhouette (no thick dark masses inside the body), no anti-aliasing,
no blur, no gradients, no noise texture. At most 16 colours. 
A flat solid magenta (#FF00FF) background everywhere: no checkerboard, no gradient, no scenery.
Deliver a PNG, not a JPEG.
No text, labels, grid lines, borders or watermark. Output: PNG.
```
