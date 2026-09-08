import pytest

from config import CONFIG
from design import Design, OrganizerConfig, RowDivider


@pytest.fixture(scope="module")
def design():
    return Design(CONFIG)


def test_outer_size_and_grid(design):
    assert design.width == 29.625 and design.depth == 20.125
    xs = list(design.column_grid.values())
    assert xs == sorted(xs) and len(xs) == 19
    assert xs[0] + xs[-1] == pytest.approx(design.width)  # symmetric about the centre
    assert xs[0] - 0.125 >= 0.25 + 0.5                   # clear of the corner joint plus margin
    assert len(design.row_grid) == 7


def test_egg_crate_notches_are_complementary(design):
    assert design.top_notch_depth == 1.25
    assert design.top_notch_depth + design.bottom_notch_depth == design.height


def test_panel_sizes(design):
    by_name = {p.name: p for p in design.panels}
    assert by_name["wall_front"].outline.length == design.width
    assert by_name["wall_left"].outline.length == design.depth
    assert by_name["column_1"].outline.length == design.depth
    row = by_name["row_2"]  # spans two columns, crossing one divider
    assert len(row.outline.bottom) == 3
    x1 = design.column_grid[CONFIG.columns[0]] - 0.125
    x3 = design.column_grid[CONFIG.columns[2]] + 0.125
    assert row.outline.length == pytest.approx(x3 - x1)


def test_cut_list_needs_passthrough_for_walls(design):
    fits = {label: fit for label, _, _, _, fit in design.cut_list()}
    assert fits["wall"] == "passthrough"
    assert fits["column divider"] == "passthrough"
    assert fits["row divider"] == "fits bed"


def test_cells_add_up(design):
    for _, width, depths in design.cells():
        assert width > 1
        # cells plus divider thicknesses plus the two walls span the full depth
        assert sum(depths) + 0.25 * (len(depths) - 1) + 0.5 == pytest.approx(design.depth)


def test_row_conflict_is_rejected():
    cfg = OrganizerConfig(columns=[0], rows=[RowDivider(0, 1, 0), RowDivider(1, 2, 0)])
    with pytest.raises(ValueError, match="one divider spanning"):
        Design(cfg)


def test_bad_indices_are_rejected():
    with pytest.raises(ValueError):
        Design(OrganizerConfig(columns=[40]))
    with pytest.raises(ValueError):
        Design(OrganizerConfig(columns=[0], rows=[RowDivider(0, 3, 0)]))
    with pytest.raises(ValueError):
        Design(OrganizerConfig(columns=[2, 1]))


def test_no_two_panels_share_material(design):
    """Sample the boxes where panels overlap and check at most one panel claims
    each point. Exercises the finger joints and every egg-crate joint."""
    step = 1 / 16
    panels = design.panels
    for i, a in enumerate(panels):
        lo_a, hi_a = a.bounds()
        for b in panels[i + 1:]:
            lo_b, hi_b = b.bounds()
            lo = [max(lo_a[k], lo_b[k]) for k in range(3)]
            hi = [min(hi_a[k], hi_b[k]) for k in range(3)]
            if any(hi[k] - lo[k] <= 0 for k in range(3)):
                continue
            samples = [[lo[k] + step / 2 + j * step for j in range(int((hi[k] - lo[k]) / step) + 1)
                        if lo[k] + step / 2 + j * step < hi[k]] for k in range(3)]
            for x in samples[0]:
                for y in samples[1]:
                    for z in samples[2]:
                        assert not (a.contains((x, y, z)) and b.contains((x, y, z))), \
                            f"{a.name} and {b.name} both occupy ({x}, {y}, {z})"
