import pytest

from config import CONFIG
from design import Design, OrganizerConfig, RowDivider


@pytest.fixture(scope="module")
def design():
    return Design(CONFIG)


def test_outer_size_and_grid(design):
    assert design.width == 29.625 and design.depth == 20.125
    xs = list(design.column_grid.values())
    assert xs == sorted(xs) and len(xs) == 15
    assert xs[0] + xs[-1] == pytest.approx(design.width)  # symmetric about the centre
    assert xs[0] - 0.125 >= 0.25 + 3.0                   # clear of the corner gusset
    assert len(design.row_grid) == 5


def test_pitch_snaps_so_wall_cells_match_divider_cells(design):
    assert design.column_pitch == pytest.approx((design.width - 0.25) / 20)
    assert design.row_pitch == pytest.approx((design.depth - 0.25) / 8)
    widths = [w for _, w, _ in design.cells()]
    assert widths[0] == widths[1] == widths[2] == pytest.approx(3 * design.column_pitch - 0.25)
    assert widths[3] == pytest.approx(4 * design.column_pitch - 0.25)
    assert widths[4] == pytest.approx(7 * design.column_pitch - 0.25)


def test_egg_crate_notches_are_complementary(design):
    assert design.level == 4.0 and design.slot_floor == 2.75
    assert design.wall_slot_depth == 1.75 and design.divider_slot_depth == 1.25
    assert design.wall_slot_depth + design.bottom_notch_depth == design.height
    assert design.divider_slot_depth + design.bottom_notch_depth == design.level


def test_raised_corners_and_flat_interior(design):
    import math
    H, level = design.height, design.level
    for w in (p for p in design.panels if p.kind == "wall"):
        f = w.outline.top_profile
        L = w.outline.length
        for x in (0.0, 0.5, 1.0, L - 1.0, L - 0.5, L):
            assert f(x) == H                                  # full height over the outer inch
        assert f(1.25) == pytest.approx(level + 0.25)          # middle of the S, where the two arcs meet
        assert f(1.1) > H - 0.05 and f(1.4) < level + 0.05      # eases out of both levels
        assert f(1.5) == pytest.approx(level) and f(L - 1.5) == pytest.approx(level)
        for x in (2.0, L / 2, L - 2.0):
            assert f(x) == level                              # flat interior
        for n in w.outline.top:                               # every slot sits on the flat
            assert f(n.start) == level and f(n.end) == level
        pts = w.outline.points()
        assert max(y for _, y in pts) == H
        assert sum(1 for _, y in pts if abs(y - design.slot_floor) < 1e-9) == 2 * len(w.outline.top)
    for p in design.panels:
        if p.kind in ("column", "row"):
            assert p.outline.top_profile is None and p.outline.height == level


def test_ears_are_flush(design):
    """A column divider's top at the wall equals the wall's top there, and a row
    divider's top equals the column divider's top where it passes through."""
    level = design.level
    walls = {p.name: p for p in design.panels if p.kind == "wall"}
    for c in (p for p in design.panels if p.kind == "column"):
        x = c.placement.origin[0] + 0.125
        assert walls["wall_front"].outline.top_profile(x) == level == c.outline.height
    for r in (p for p in design.panels if p.kind == "row"):
        assert r.outline.height == level


def test_straight_tops_when_rise_is_zero():
    d = Design(OrganizerConfig(corner_rise=0, notch_depth=1.25))
    assert all(getattr(p.outline, "top_profile", None) is None for p in d.panels)
    assert d.level == 4.5 and d.slot_floor == 3.25


def test_first_slot_clears_the_shoulder_for_any_plateau():
    for plateau in (0.25, 1.0, 2.5, 4.0):
        d = Design(OrganizerConfig(corner_plateau=plateau, gusset_leg=0))
        for g in (d.column_grid, d.row_grid):
            assert min(g.values()) - 0.125 > plateau + 0.5


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
    # a row divider in one of the equal columns spans the cell plus two divider faces
    assert by_name["row_1"].outline.length == pytest.approx(4.15625 + 0.5)


def test_cut_list_needs_passthrough_for_walls(design):
    fits = {label: fit for label, _, _, _, _, fit in design.cut_list()}
    assert fits["wall"] == "passthrough"
    assert fits["column divider"] == "passthrough"
    assert fits["row divider"] == "fits bed"
    assert fits["corner gusset"] == "fits bed"


def test_gussets(design):
    gussets = [p for p in design.panels if p.kind == "gusset"]
    assert len(gussets) == 4
    leg, t = 3.0, 0.25
    tabs = design.gusset_tab_spans
    assert [v for span in tabs for v in span] == pytest.approx([0.6, 1.2, 1.8, 2.4])
    expected = leg * leg / 2 + 2 * sum((b - a) * t for a, b in tabs)
    assert gussets[0].outline.area() == pytest.approx(expected)
    # every wall has a pair of bottom notches at each end for the tabs
    for p in design.panels:
        if p.kind == "wall":
            assert len(p.outline.bottom) == 4
    # the front-left gusset's first tab sits inside the front wall, just past the corner
    fl = next(p for p in gussets if p.name == "gusset_front_left")
    assert fl.contains((t + 0.9, t / 2, t / 2))
    assert not fl.contains((t + 0.3, t / 2, t / 2))
    front = next(p for p in design.panels if p.name == "wall_front")
    assert not front.contains((t + 0.9, t / 2, t / 2))
    assert front.contains((t + 0.3, t / 2, t / 2))


def test_no_gussets_when_leg_is_zero():
    d = Design(OrganizerConfig(gusset_leg=0))
    assert not any(p.kind == "gusset" for p in d.panels)
    assert len(d.column_grid) == 17   # the corner shoulders, not the gussets, now set the clearance
    first = min(d.column_grid.values()) - 0.125
    assert first >= 1.0 + 0.5 + 0.5    # plateau + shoulder + edge margin


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
