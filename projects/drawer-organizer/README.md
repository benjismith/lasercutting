# Kitchen drawer organizer

A floorless, finger-jointed plywood box that fits a kitchen drawer, with a grid of
drop-in dividers. Column dividers split the drawer left to right; row dividers split
any column front to back. Nothing is glued, so the layout can change later.

![Assembled](renders/iso.png)

![Exploded, showing the joints](renders/iso-exploded.png)

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

Assembly order: walls first, then column dividers, then row dividers. To reconfigure,
lift the row dividers out and move things around.

## Parameters

All in `config.py`, all in inches.

| parameter | default | notes |
|---|---|---|
| `clearance` | 1/16 per side | box is the drawer size minus twice this |
| `height` | 4.5 | wall and divider height |
| `thickness` | 0.25 | **measure your actual stock with calipers** and set this |
| `column_pitch` | 1.5 | spacing of column-divider positions across the width |
| `row_pitch` | 2.5 | spacing of row-divider positions along the depth |
| `notch_depth` | 1.25 | depth of the top-edge notches; dividers' bottom notches get the rest (3.25) |
| `finger_width` | 0.5 | target; the real width makes an odd finger count |
| `edge_margin` | 0.5 | solid wood kept between the outermost notch and a corner joint |
| `columns` | `[-6, -3, 0, 4]` | grid indices of column dividers, 0 at the centre |
| `rows` | five dividers | `(start boundary, end boundary, row index)` |

Grid indices count outward from the middle: column index 0 is the drawer's centre line,
negative is left, positive is right; row index 0 is the middle of the depth, negative
toward the front. With the defaults there are 19 column positions and 7 row positions.

## Current layout

Running `build.py` prints this. Five columns, left to right:

| column | clear width | cells front to back |
|---|---|---|
| 1 | 5.4375 | 9.6875 / 9.6875 |
| 2 | 4.25 | 7.1875 / 12.1875 |
| 3 | 4.25 | 7.1875 / 7.25 / 4.6875 |
| 4 | 5.75 | 19.625 |
| 5 | 8.4375 | 4.6875 / 9.75 / 4.6875 |

This is a demonstration layout that exercises every joint type, not a proposal for
what belongs in the drawer.

## Cutting

| part | count | size (in) | on the Glowforge |
|---|---|---|---|
| long wall | 2 | 29.625 x 4.5 | passthrough |
| short wall | 2 | 20.125 x 4.5 | passthrough |
| column divider | 4 | 20.125 x 4.5 | passthrough |
| row dividers | 5 | 4.75 to 9.25 x 4.5 | fit on the bed |

Every part that runs the full depth of the drawer is just over the 19.5 in bed, so the
walls and column dividers all need the passthrough. Shrinking the box to 19.5 in deep
would avoid that for everything except the two long walls, at the cost of about 3/4 in
of slop front to back.

Cut files are not generated yet. When they are, kerf compensation and the measured
stock thickness get applied at that stage; the geometry here is nominal.

## Decisions and open questions

1. **Wall height 4.5 in** in a drawer about 6 in tall, leaving generous clearance above.
2. **Notch depth 1.25 in.** Shallow top-edge notches keep the wall tops mostly clean;
   the dividers' 3.25 in bottom notches do the holding. The trade-off is that a divider
   is held sideways only by its 1.25 in ear in the wall slot, so a loose fit lets it
   rock; kerf compensation at export should aim for a snug fit.
3. **Pitch 1.5 in across, 2.5 in front to back.** Column positions stay fine-grained;
   row positions are deliberately few (7).
4. **Stock thickness.** Nominal 1/4 in plywood is usually 0.2 to 0.23 in. The design
   scales with `thickness`, so measure before cutting.
5. **Grain and faces.** Plywood cuts the same either side up, and the walls' outer faces
   sit against the drawer, so only the top edges and the divider faces show.

## Files

- `design.py` – turns an `OrganizerConfig` into panels with 3D placements, and
  reports the cut list and cell sizes.
- `config.py` – this drawer's numbers and the current layout.
- `build.py` – builds the Blender scene, saves a `.blend`, renders previews.
- `test_design.py` – checks the grid, the cut list, the config validation, and that no
  two panels occupy the same space at any joint.
- `renders/` – previews from the current config.
