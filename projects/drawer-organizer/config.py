"""The kitchen drawer this organizer is for, and the divider layouts it supports.

The box parameters are shared; each layout in LAYOUTS places column and row dividers
on the grid. `build.py --layout NAME` picks one; CONFIG is the default.

Grid indices count outward from the middle of the drawer: column index 0 is the
divider position at the drawer's centre line, -1 is one step to the left, +1 one step
to the right. Row indices work the same way front (negative) to back (positive).

The width is divided into 18 steps, so a cell n steps wide is always
n * pitch - thickness, whether it sits against a wall or between two dividers, and
the drawer splits evenly into 2, 3, 6 or 9 columns. The depth is divided into 8 steps.
"""
from dataclasses import replace

from design import OrganizerConfig, RowDivider

BOX = OrganizerConfig(
    drawer_width=29.75,
    drawer_depth=20.25,
    drawer_height=6.0,
    clearance=1 / 16,
    height=4.5,
    thickness=5.2 / 25.4,   # measured with calipers 2026-09-08: 5.1 to 5.2 mm; sized for the thick spots
    column_steps=18,
    row_steps=8,
    notch_depth=1.25,
    corner_rise=0.5,
    corner_curve="ease",
    step_run=2.0,
    back_level=3.5,
    step_gap=0.5,
    corner_plateau_min=1.5,
    gusset_leg=3.0,
    gusset_tabs=2,
)

LAYOUTS = {
    # Three equal columns of 3 steps on the left, then a 4-step and a 5-step column.
    # Boundaries for row dividers: 0 is the left wall, 1..4 the column dividers, 5 the
    # right wall.
    "three-plus-two": replace(
        BOX,
        columns=[-6, -3, 0, 4],
        rows=[
            RowDivider(0, 1, 0),    # column 1 split in half
            RowDivider(1, 3, -1),   # one long divider across columns 2 and 3, crossing divider 2
            RowDivider(2, 3, 2),    # column 3 gets a second split further back
            RowDivider(4, 5, -2),   # column 5 split into three
            RowDivider(4, 5, 2),
            RowDivider(3, 4, 0),    # column 4 split in half
        ],
    ),
    # Six equal columns of 3 steps each; the outer two split in half.
    "six-equal": replace(
        BOX,
        columns=[-6, -3, 0, 3, 6],
        rows=[
            RowDivider(0, 1, 0),
            RowDivider(5, 6, 0),
        ],
    ),
}

CONFIG = LAYOUTS["three-plus-two"]

# The plywood on hand: pre-cut sheets, fed long side first through the passthrough.
# Parts are kept edge_margin in from each long edge.
STOCK = {"width": 19.0, "length": 48.0, "edge_margin": 0.125}
