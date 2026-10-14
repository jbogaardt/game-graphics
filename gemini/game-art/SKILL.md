---
name: game-art
description: Designs and generates pixel-art source sheets for a top-down LPC-style action RPG (characters, monsters, animals, props, terrain tiles, item icons, spell effects), one sheet per turn, shown in the chat. Use when the user asks for a sprite, sprite sheet, monster, NPC, prop, tile, icon or effect for their game, or asks to redo, fix or extend one generated earlier.
---

# Game art

You design and **generate the images yourself** with image generation (Nano Banana). The deliverable is images in
this chat, never a prompt or spec for another tool. The images are source art: the user cuts them into frames and
cleans them up afterwards, so what matters is a consistent design on an easy-to-slice grid with a magenta background.

**One image per turn.** You make exactly one sprite sheet each time the skill runs. A character needs three sheets
(`walk`, `action`, `extra`), so it takes three turns: the user types "next" (or names the sheet) to get the next one.

## Steps

1. **Read the request.** Work out the `kind`: `char` (anything that walks upright), `creature` (four-legged or
   non-humanoid), `prop`, `tile`, `item` or `fx`. For "again", "fix", "another try" or an attached earlier image,
   keep everything the user did not ask to change. Then pick **the one sheet** to make this turn:
   - a new `char` or `creature`: `walk`;
   - "next": the sheet after the last one made in this chat (`walk`, then `action`, then `extra`);
   - the user names one ("the action sheet", "redo extra"): that one;
   - `prop`, `tile`, `item`, `fx`: the single sheet for that kind.
2. **On the first sheet of an asset only, write a two-line brief** and show it (do not wait for approval); reuse
   it unchanged for the later sheets: the look in one line (silhouette, materials,
   face, attacks), and a palette of at most 16 hex colours (rules in `style-guide.md`).
3. **Generate that one sheet** with its prompt below (for `prop`, `tile`, `item`, `fx` use
   `prompt-template.md` with the rows from `layouts.md`). Send each prompt **in full, word for word**, with only
   the `<...>` filled in. For a redo, or for `action` and `extra`, use the `walk` sheet earlier in this chat (or the image the user
   attached) as the reference.
4. **Check the image** with the checklist. If it fails, regenerate it once with the failure added at the end of
   the prompt ("Fix: the background is a checkerboard; it must be flat magenta"). If it fails again, show it and
   say what is wrong.
5. **Reply** with the template.

## Prompts for `char` and `creature` (one per turn: walk, then action, then extra)

Common part, `<COMMON>` below, always included word for word:
> Background: flat solid magenta #FF00FF filling the whole image. Not transparent, not a checkerboard, no ground,
> no shadows, no text, no labels, no grid lines, no borders. Pixel art: drawn small (the character about 46 pixels
> tall in 64 pixel square cells) and enlarged 4x with nearest neighbour, so every pixel is a hard square block;
> 1 pixel dark outline <outline hex>; 3-4 flat tones per material, shadows shifted towards <purple/violet/red>; at
> most 16 colours: <palette>; no anti-aliasing, no soft shading, no fur strands, no gradients. LPC (Liberated Pixel
> Cup) style, 3/4 top-down camera, light from the top left. Every frame in an equal square cell, evenly spaced, the
> same size and design in every frame, feet on one ground line per row, nothing outside its cell.

Sheet `walk`:
> Pixel-art sprite sheet of <look>. Exactly 3 rows of 8 frames, nothing else. Row 1: walk cycle facing the camera
> (front view, walking towards the viewer), 8 frames. Row 2: walk cycle facing away from the camera (back view, we
> see its back), 8 frames. Row 3: walk cycle in side view facing right, 8 frames. <COMMON>

Sheet `action` (reference: the walk sheet):
> Pixel-art sprite sheet of the same character as the attached sheet, same design, colours and size. Exactly 4
> rows of 6 frames, nothing else. Row 1: idle breathing, 2 frames facing the camera, 2 frames back view, 2 frames
> side view facing right. Row 2: <melee attack> facing the camera, 6 frames: wind-up, wind-up, strike,
> follow-through, recover, recover. Row 3: the same attack in back view, 6 frames. Row 4: the same attack in side
> view facing right, 6 frames. <COMMON>

Sheet `extra` (reference: the walk sheet):
> Pixel-art sprite sheet of the same character as the attached sheet, same design, colours and size. Exactly 4
> rows of 6 frames, nothing else. Row 1: <ranged or spell attack> facing the camera, 6 frames: raise, charge,
> release, release, recover, recover. Row 2: the same attack in back view, 6 frames. Row 3: the same attack in side
> view facing right, 6 frames. Row 4: hit and death facing the camera, 6 frames: recoil, stagger, falling,
> falling, lying, lying. <COMMON>

A `creature` drops rows that make no sense for it (a wolf has no ranged attack) and says so.

## Checklist (every sheet)

- The background is flat magenta, not a grey checkerboard (the most common failure: regenerate).
- The exact rows and frame counts asked for, in order. Front, back and side views really differ: the back view
  shows the back, the side view a profile.
- Hard pixel blocks and flat tones, not a smooth cartoon with soft shading and fur strands.
- Same design and size in every frame and as the reference image; each figure whole inside its cell.

## Reply template

**Brief:** <look> · palette <hex list> (first sheet only)
**Sheet:** <walk / action / extra, or the kind> — then the image, then one line `Rows: ... · Problems: <none, or
what is wrong>`, then for characters one line `Next: type "next" for the <action / extra> sheet` (after `extra`:
`All three sheets done.`).

You cannot save, name, upload or store files; the images only appear in this chat. Do not mention filenames,
saving or folders.

## Missing information

Ask one short question only when the subject itself is unclear. Never ask about sizes, palette, layout or style.

## Common mistakes

- Writing a prompt for the user to run elsewhere instead of generating the image.
- Asking for "transparent background": the generator paints a fake grey checkerboard. Always magenta.
- Putting a whole character on one sheet, or more than one sheet in a turn, or a shortened prompt: the layout gets
  lost and every frame faces the same way.
- Using the usual LPC row order, or drawing facing left (left is mirrored later).
- A new design on the action or extra sheet: always use the walk sheet as the reference.
