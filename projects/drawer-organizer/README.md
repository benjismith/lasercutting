# Kitchen drawer organizer

A floorless, finger-jointed plywood box that fits a kitchen drawer, with a grid of
drop-in dividers. Column dividers split the drawer left to right; row dividers split
any column front to back. The box is glued; the dividers just drop in, so the layout
can change later.

![Assembled](renders/iso.png)

![Exploded, showing the joints](renders/iso-exploded.png)

![Corner gusset, dropped out of its slots](renders/corner.png)

![Left wall from outside](renders/left.png)

## The drawer

| | inches |
|---|---|
| interior width | 29.75 |
| interior depth | 20.25 |
| interior height | about 6 |

## How it goes together

- **Walls.** Four walls joined at the corners with finger joints. The long walls have
  fingers at the top and bottom corners; the short walls have the matching notches.
- **Notch grid.** Every wall has notches cut down from its top edge at a fixed pitch,
  symmetric about the middle of the wall. The front and back walls' notches are where
  column dividers can go; the side walls' notches are where row dividers can go.
- **Column dividers** run front to back. Each end has a notch cut up from the bottom
  edge that straddles the wall, while the remaining top part of the end drops into the
  wall's notch, passing right through the wall and ending flush with its outer face.
  This egg-crate joint holds the divider against sideways and front-to-back movement.
  Column dividers carry the same top-edge notch grid as the side walls.
- **Row dividers** run left to right and drop onto the side walls and column dividers
  with the same joint. A row divider can span several columns; it then crosses the
  column dividers in between with a bottom notch at each crossing.
- **Raised corners.** Each wall stands at full height over the outer inch at both
  ends, then drops half an inch through a quarter-round shoulder to the interior
  level, and runs flat at that level the rest of the way. Dividers are flat at the
  interior level. So every slot is the same depth, every divider ear is flush with the
  edge it passes through, and the box reads as four raised corner posts around a level
  interior. The shoulder can be a quarter circle or an S curve.
- **Corner gussets.** A flat right-angle triangle lies on the drawer floor in each
  corner, its two legs against the walls. Two tabs along each leg pass through the wall
  and end flush with its outer face, which sits against the drawer. The walls have
  matching notches up from their bottom edges. Glued in, the gussets keep the box
  square and hold it square during glue-up. Without glue they add nothing: the walls
  can lift straight off the tabs.

Assembly order: glue the walls and gussets together (the gussets set the corners
square), then drop in column dividers, then row dividers. To reconfigure, lift the row
dividers out and move things around.

## Parameters

All in `config.py`, all in inches.

| parameter | default | notes |
|---|---|---|
| `clearance` | 1/16 per side | box is the drawer size minus twice this |
| `height` | 4.5 | wall height at the raised corners |
| `thickness` | 0.25 | **measure your actual stock with calipers** and set this |
| `column_pitch` | 1.5 | target spacing of column-divider positions across the width; snapped, see below |
| `row_pitch` | 2.5 | target spacing of row-divider positions along the depth; snapped |
| `notch_depth` | 1.25 | how far a divider's ear engages its slot, measured from the interior level |
| `corner_rise` | 0.5 | how much higher the corners stand than the interior level; 0 for straight tops |
| `corner_plateau` | 1.0 | length of full-height edge at each corner before the shoulder |
| `corner_curve` | `round` | shoulder shape: `round` (quarter circle, radius = rise) or `ogee` (S of two quarter circles) |
| `finger_width` | 0.5 | target; the real width makes an odd finger count |
| `edge_margin` | 0.5 | solid wood kept between the outermost notch and a corner joint |
| `gusset_leg` | 3.0 | leg length of the corner gussets; 0 removes them |
| `gusset_tabs` | 2 | tabs along each gusset leg |
| `columns` | `[-7, -4, -1, 3]` | grid indices of column dividers, 0 at the centre |
| `rows` | six dividers | `(start boundary, end boundary, row index)` |

Grid indices count outward from the middle: column index 0 is the drawer's centre line,
negative is left, positive is right; row index 0 is the middle of the depth, negative
toward the front. Grid positions that would run into a gusset are dropped, so with the defaults there
are 15 column positions and 5 row positions (19 and 7 without gussets).

**Slot depths.** The interior level is `height - corner_rise` (4.0). Slot floors are
`notch_depth` below that (2.75 above the drawer bottom), so every slot in a wall or
column divider is 1.25 in deep and every divider's bottom notch is 2.75 in tall.

**Pitch snapping.** A cell against a wall is bounded by one wall face and one divider
face; a cell between dividers by two divider faces. For the same number of grid steps
those differ by half a stock thickness, unless an even number of pitches spans the wall
length minus one thickness. So the pitch is nudged to the nearest value that does: here
1.46875 in across (20 steps) and 2.484 in front to back (8 steps). Then any cell is
simply steps x pitch minus thickness, wherever it sits, and columns given the same
number of steps come out identical.

## Current layout

Running `build.py` prints this. Three equal columns on the left (3 grid steps each),
then a 4-step and a 7-step column:

| column | clear width | cells front to back |
|---|---|---|
| 1 | 4.15625 | 9.6875 / 9.6875 |
| 2 | 4.15625 | 7.203 / 12.172 |
| 3 | 4.15625 | 7.203 / 7.203 / 4.719 |
| 4 | 5.625 | 9.6875 / 9.6875 |
| 5 | 10.03125 | 4.719 / 9.6875 / 4.719 |

The row dividers are still the demonstration set that exercises every joint type; their
lengths follow the columns automatically.

## Cutting

| part | count | size (in) | on the Glowforge |
|---|---|---|---|
| long wall | 2 | 29.625 x 4.5 | passthrough |
| short wall | 2 | 20.125 x 4.5 | passthrough |
| column divider | 4 | 20.125 x 4.0 | passthrough |
| row dividers | 6 | 4.66 to 10.53 x 4.0 | fit on the bed |
| corner gusset | 4 | 3.25 x 3.25 | fit on the bed |

Every part that runs the full depth of the drawer is just over the 19.5 in bed, so the
walls and column dividers all need the passthrough. Shrinking the box to 19.5 in deep
would avoid that for everything except the two long walls, at the cost of about 3/4 in
of slop front to back.

Cut files are not generated yet. When they are, kerf compensation and the measured
stock thickness get applied at that stage; the geometry here is nominal.

## Decisions and open questions

1. **Wall height 4.5 in** in a drawer about 6 in tall, leaving generous clearance above.
2. **Notch depth 1.25 in.** Shallow top-edge notches keep the wall tops mostly clean;
   the dividers' 2.75 in bottom notches do the holding. The trade-off is that a divider
   is held sideways only by its 1.25 in ear in the wall slot, so a loose fit lets it
   rock; kerf compensation at export should aim for a snug fit.
3. **Pitch about 1.5 in across, 2.5 in front to back,** snapped as described above.
   Column positions stay fine-grained; row positions are deliberately few.
4. **Corner gussets, 3 in legs.** They triangulate the corners of a box that otherwise
   has nothing keeping it square once it leaves the drawer. The cost is a triangle of
   floor in each corner cell and the divider positions nearest the corners, which only
   ever made cells under 2.5 in wide. A 2 in leg keeps one more column position per
   side. The box is glued, so they earn their keep.
5. **Stock thickness.** Nominal 1/4 in plywood is usually 0.2 to 0.23 in. The design
   scales with `thickness`, so measure before cutting.
6. **Raised corners instead of waves.** An earlier version gave every panel a random
   undulating top. Because a wall's height then differed at each slot, divider ears had
   to be recessed to stay interchangeable, and the panels stopped being identical parts.
   Raised corners with a flat interior keep a shaped top edge while restoring flush
   ears, uniform slots, and identical dividers. The wave generator remains in the
   shared library for other projects.
7. **Grain and faces.** Plywood cuts the same either side up, and the walls' outer faces
   sit against the drawer, so only the top edges and the divider faces show.

## Files

- `design.py` – turns an `OrganizerConfig` into panels with 3D placements, and
  reports the cut list and cell sizes.
- `config.py` – this drawer's numbers and the current layout.
- `build.py` – builds the Blender scene, saves a `.blend`, renders previews.
- `test_design.py` – checks the grid, the cut list, the config validation, and that no
  two panels occupy the same space at any joint.
- `renders/` – previews from the current config.
