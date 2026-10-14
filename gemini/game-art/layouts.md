# Layouts: which images, which rows

Directions: **down** = facing the camera, **up** = back to the camera, **right** = facing screen right. Left is
made later by mirroring, so never draw it.

## char and creature: three parts, in this order

**Part `walk`** (generate first; it is the reference for the others)
1. walk facing down, 8 frames
2. walk facing up, 8 frames
3. walk facing right, 8 frames

**Part `action`**
1. idle breathing: facing down 2 frames, facing up 2 frames, facing right 2 frames (6 cells in one row)
2. melee attack facing down, 6 frames: wind-up, wind-up, strike, follow-through, recover, recover
3. the same attack facing up, 6 frames
4. the same attack facing right, 6 frames

**Part `extra`**
1. ranged or spell attack facing down, 6 frames: raise, charge, release, release, recover, recover
2. the same attack facing up, 6 frames
3. the same attack facing right, 6 frames
4. hit and death facing down, 6 frames: recoil, stagger, falling, falling, lying, lying

A creature skips rows that make no sense for it (a wolf has no ranged attack: leave out the whole `extra` part
except the death row) and says so in the Rows line.

## prop: one image
One row. One cell per state (closed, opening, open; intact, broken) or 4-6 frames for an animation (torch flame,
spinning crystal).

## tile: one image
4x4 grid of 32x32 tiles: row 1 four plain variants of the fill; rows 2-4 edges and corners against magenta (top,
bottom, left, right, four outer corners, four inner corners). Water or lava: one row of 4 animation frames per tile.

## item: one image
4x4 grid, one item per cell, up to 16 items of the requested set.

## fx: one image
1. projectile flying right, 4 frames
2. impact burst, 6 frames
3. looping effect (aura, ground ice, flames), 6 frames
