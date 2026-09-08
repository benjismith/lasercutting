"""The kitchen drawer this organizer is for, and the current divider layout.

Grid indices count outward from the middle of the drawer: column index 0 is the
divider position at the drawer's centre line, -1 is one pitch to the left, +1 one
pitch to the right. Row indices work the same way front (negative) to back (positive).
"""
from design import OrganizerConfig, RowDivider

CONFIG = OrganizerConfig(
    drawer_width=29.75,
    drawer_depth=20.25,
    drawer_height=6.0,
    clearance=1 / 16,
    height=4.5,
    thickness=0.25,
    column_pitch=1.5,
    row_pitch=2.5,
    notch_depth=1.25,
    # Column dividers at these grid positions (left to right).
    columns=[-6, -3, 0, 4],
    # Row dividers: (start boundary, end boundary, row index). Boundary 0 is the left
    # wall, 1..4 the column dividers above, 5 the right wall.
    rows=[
        RowDivider(0, 1, 0),    # column 1 split in half
        RowDivider(1, 3, -1),   # one long divider across columns 2 and 3, crossing divider 2
        RowDivider(2, 3, 2),    # column 3 gets a second split further back
        RowDivider(4, 5, -2),   # column 5 split into three
        RowDivider(4, 5, 2),
    ],
)
