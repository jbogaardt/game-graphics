# Prompt for the image generator (new sheet, or only the missing rows)

Fill every `{...}` before handing it over; leave no placeholder in. Put it in one fenced block so it copies in
one go. Ask for the result as a **PNG file path**, not a pasted image.

```
Sprite sheet of {subject: one line, e.g. "a pharaoh mummy: bandaged body, gold-and-lapis striped nemes
headdress, bare skull face with glowing red eyes"} for a top-down action RPG, in the style of the
Liberated Pixel Cup (LPC) sprites: 3/4 top-down camera, chunky proportions, light from the top left.

Layout (strict):
- One animation per row, one direction per row. Rows, top to bottom:
  {e.g.
  1. walk, facing the camera (down), 8 frames
  2. walk, facing away (up), 8 frames
  3. walk, facing right, 8 frames
  4. idle (breathing), facing down / up / right, 2 frames each
  5. melee attack facing down, 6 frames: wind-up, strike, follow-through, recover
  6. melee attack facing up, 6 frames
  7. melee attack facing right, 6 frames
  8. ranged attack facing down / up / right, 6 frames each
  9. hit reaction and collapse to the ground, facing down, 6 frames}
- Every frame in an equal square cell, the same size of character in every cell, feet on the same
  ground line, the whole character inside its cell (weapons included).
- Same character design, colours and proportions in every frame and row.

Rendering:
- Flat solid magenta background (#FF00FF) everywhere, no ground, no shadows on the floor, no dust, no
  scenery, no text, no labels, no grid lines, no borders, no watermark.
- Crisp pixel-art look: hard edges, flat shading in 3-4 tones per material, 1 px dark outline,
  no anti-aliasing, no blur, no gradients, no noise texture. At most {16} colours: {palette hex list
  with roles, from the spec, e.g. outline #1d1016, linen #3b2320 #5e3d2d #84623f #ab8c5c #d0b986,
  gold #7a4f22 #c8902f #f2cf6b, lapis #1c2246 #33508e, red #b0263a #f0585a}.
- Ideally a true pixel grid: draw the character about {46} px tall and upscale by exactly {4}x with
  nearest neighbour, so each art pixel is a {4}x{4} block.
Output: PNG.
```

When only some rows are missing, keep the subject and rendering paragraphs and list only those rows, plus "match
the attached reference exactly" with the current sheet attached, so the design stays the same.
