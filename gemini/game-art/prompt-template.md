# Image prompt template

Fill every `<...>` and pass the whole prompt to image generation. Do not shorten it or replace it with style words.

```
Pixel-art sprite sheet of <one-line look from the brief>, for a top-down action RPG in the exact style of the
Liberated Pixel Cup (LPC) sprites: 3/4 top-down camera, chunky readable proportions, light from the top left.

Layout, top to bottom, exactly these rows and frame counts and nothing else:
<the part's rows from layouts.md, one per line, e.g. "Row 1: walk facing the camera (down), 8 frames">
Frames side by side in a strict grid of equal square cells, evenly spaced. The same design, colours and size in
every frame. Feet on the same ground line in every cell of a row. The whole figure, weapon included, inside its
cell.

Palette, at most 16 colours: <hex list with roles from the brief>. Dark outline <outline hex>. Shadows hue-shift
towards <purple/red/violet>, highlights towards <yellow/warm>.

Background: flat solid magenta (#FF00FF) everywhere. No ground, no floor shadows, no dust, no scenery, no text, no
labels, no numbers, no grid lines, no borders, no checkerboard.

Rendering: crisp pixel art, hard pixel edges, 1 pixel dark outline, 3-4 flat tones per material, no anti-aliasing,
no blur, no gradients, no noise. Drawn at <cell> pixel cells (figure about <figure size> pixels) and upscaled 4x
with nearest neighbour, so each art pixel is a clean 4x4 block.
<for parts after the first: "Match the attached reference sheet exactly: same character, colours, proportions and
pixel size.">
<on a retry: "Fix: <what failed>.">
```
