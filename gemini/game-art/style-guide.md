# Style guide: the game's look

The game is a top-down action RPG built on Liberated Pixel Cup (LPC) art. New art must sit next to LPC sprites
without standing out.

## Camera and light
- 3/4 top-down camera (you see the top of the head and the front of the body), as in LPC.
- Light from the top left. Shadows fall bottom right.

## Sizes (art pixels, before the 4x upscale)
| kind | cell | figure |
|---|---|---|
| char | 64x64 | about 46 px tall, about 28 px wide; feet near the bottom of the cell |
| creature | 64x64 (32x32 for rats, cats, birds) | fills about two thirds of the cell |
| prop | 32 px tiles: 1x1, 1x2, 2x2 | base on the bottom edge of the cell |
| tile | 32x32 | fills the cell edge to edge, repeats seamlessly |
| item | 32x32 | centred, about 24 px, slightly angled |
| fx | 64x64 | centred |

Draw at that size, then upscale **exactly 4x with nearest neighbour**, so every art pixel is a crisp 4x4 block.

## Palette
- At most 16 colours per asset, listed as hex with a role.
- A dark outline colour, close to #1d1016 (not pure black).
- One main material with 4-5 steps, accent materials with 2-3 steps each.
- Ramps hue-shift: shadows move towards purple or red, highlights towards yellow or warm. Never just the same hue
  darker.
- Keep it bright: LPC bodies sit mostly on their two lightest steps. Near-black only in the outline and thin
  internal lines.
- Cold subjects (ice, snow): white and pale blue body, shadows in lavender and violet, not grey.

## Rendering
- 1 px dark outline around the figure; thin internal lines where parts overlap.
- 3-4 flat tones per material, hard edges, no anti-aliasing, blur, gradients, dithering noise or texture grain.
- Big simple shapes. At 46 px the face is a few pixels: eyes and mouth must read, everything else is suggestion.
- Background flat magenta #FF00FF everywhere (no checkerboard, no shadow on the floor).
