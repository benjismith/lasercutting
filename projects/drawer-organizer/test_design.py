import pytest

from config import CONFIG, LAYOUTS
from design import Design, OrganizerConfig, RowDivider


@pytest.fixture(scope="module")
def design():
    return Design(CONFIG)


def test_outer_size_and_grid(design):
    assert design.width == 29.625 and design.depth == 20.125
    xs = list(design.column_grid.values())
    assert xs == sorted(xs) and len(xs) == 13
    assert xs[0] + xs[-1] == pytest.approx(design.width)  # symmetric about the centre
    assert xs[0] - 0.125 >= 0.25 + 3.0                   # clear of the corner gusset
    assert xs[0] - 0.125 >= 0.25 + 1.5 + 2.0 + 0.5       # and of the corner plateau, shoulder and gap
    assert len(design.row_grid) == 5


def test_steps_make_wall_cells_match_divider_cells(design):
    assert design.column_pitch == pytest.approx((design.width - 0.25) / 18)
    assert design.row_pitch == pytest.approx((design.depth - 0.25) / 8)
    widths = [w for _, w, _ in design.cells()]
    for w in widths[:3]:
        assert w == pytest.approx(3 * design.column_pitch - 0.25)
    assert widths[3] == pytest.approx(4 * design.column_pitch - 0.25)
    assert widths[4] == pytest.approx(5 * design.column_pitch - 0.25)


def test_six_equal_columns_layout():
    d = Design(LAYOUTS["six-equal"])
    widths = [w for _, w, _ in d.cells()]
    assert len(widths) == 6
    assert all(w == pytest.approx(widths[0]) for w in widths)
    assert widths[0] == pytest.approx((d.width - 2 * 0.25 - 5 * 0.25) / 6)
    assert d.panels[4].kind == "column" and sum(p.kind == "column" for p in d.panels) == 5


def test_odd_step_counts_are_rejected():
    with pytest.raises(ValueError):
        Design(OrganizerConfig(column_steps=15))


def test_egg_crate_notches_are_complementary(design):
    assert design.level == 4.0 and design.back_level == 3.5
    assert design.slot_floor == 2.75 and design.back_slot_floor == 2.25
    assert design.wall_slot_depth == 1.75 and design.back_wall_slot_depth == 2.25
    assert design.divider_slot_depth == 1.25
    assert design.wall_slot_depth + design.bottom_notch_depth == design.height
    assert design.back_wall_slot_depth + design.back_bottom_notch_depth == design.height
    assert design.divider_slot_depth + design.bottom_notch_depth == design.level


def test_tops_front_corners_flat_interior_dropped_back(design):
    H, level, back = design.height, design.level, design.back_level
    walls = {p.name: p for p in design.panels if p.kind == "wall"}
    W, D = design.width, design.depth
    f = walls["wall_front"].outline.top_profile
    w = design.shoulder_width(0.5)                             # how long a step's shoulder is
    assert w == 2.0
    col_first = min(design.column_grid.values()) - 0.125
    plateau = col_first - 0.5 - w                              # step finishes one gap before the first slot
    assert design.front_wall_plateau == (pytest.approx(plateau), pytest.approx(plateau))
    assert plateau > 1.5
    for x in (0.0, 1.0, plateau, W - plateau, W - 1.0, W):
        assert f(x) == H                                       # raised bands full height
    assert f(plateau + w / 2) == pytest.approx(level + 0.25)   # middle of the S
    assert f(plateau + 0.1 * w) > H - 0.05 and f(plateau + 0.9 * w) < level + 0.05
    for x in (col_first - 0.5, col_first, W / 2, W - col_first):
        assert f(x) == pytest.approx(level)                    # flat across the slotted region
    b = walls["wall_back"].outline.top_profile
    for x in (0.0, 1.0, W / 2, W - 1.0, W):
        assert b(x) == back                                    # back wall flat at the back level
    last_slot_end = max(design.row_grid.values()) + 0.125
    step_start = last_slot_end + 0.5                           # the step begins one gap past the last slot
    assert design.back_plateau == pytest.approx(D - step_start - w)
    assert design.back_plateau > 2.0                           # the lowered band is most of the back quarter
    row_first = min(design.row_grid.values()) - 0.125
    front_plateau = row_first - 0.5 - w
    assert design.side_front_plateau == pytest.approx(front_plateau)
    for name in ("wall_left", "wall_right"):
        g = walls[name].outline.top_profile
        assert g(0) == H and g(front_plateau) == H             # front band raised up to the step
        assert g(front_plateau + w / 2) == pytest.approx(level + 0.25)
        assert g(row_first - 0.5) == pytest.approx(level) and g(D / 2) == level   # flat interior
        assert g(last_slot_end) == level and g(step_start) == pytest.approx(level)
        assert g(step_start + w / 2) == pytest.approx(level - 0.25)   # inverted S, middle
        assert g(step_start + 0.1 * w) > level - 0.05 and g(step_start + 0.9 * w) < back + 0.05
        for x in (step_start + w, D - 1.5, D - 1.0, D):
            assert g(x) == pytest.approx(back)                 # lowered band right to the back
        for n in walls[name].outline.top:
            assert g(n.start) == level and g(n.end) == level   # every slot on the flat
    for p in design.panels:
        if p.kind == "column":
            c = p.outline.top_profile
            assert c(0) == level and c(D / 2) == level and c(last_slot_end) == level
            assert c(step_start + w) == pytest.approx(back) and c(D) == back
            for n in p.outline.top:
                assert c(n.start) == level
        if p.kind == "row":
            assert p.outline.top_profile is None and p.outline.height == level


def test_ears_are_flush_front_and_back(design):
    level, back = design.level, design.back_level
    walls = {p.name: p for p in design.panels if p.kind == "wall"}
    for c in (p for p in design.panels if p.kind == "column"):
        x = c.placement.origin[0] + 0.125
        f = c.outline.top_profile
        assert walls["wall_front"].outline.top_profile(x) == level == f(0.125)
        assert walls["wall_back"].outline.top_profile(x) == back == f(c.outline.length - 0.125)
        assert c.outline.bottom[0].depth == design.slot_floor
        assert c.outline.bottom[-1].depth == design.back_slot_floor
    for r in (p for p in design.panels if p.kind == "row"):
        assert r.outline.height == level
        assert all(n.depth == design.slot_floor for n in r.outline.bottom)


def test_slot_floors_meet_the_ears(design):
    """The back wall's slots reach down exactly as far as the column dividers' back
    notches reach up, and likewise at the front."""
    by_name = {p.name: p for p in design.panels}
    front_floor = design.height - by_name["wall_front"].outline.top[0].depth
    back_floor = design.height - by_name["wall_back"].outline.top[0].depth
    col = by_name["column_1"].outline
    assert front_floor == col.bottom[0].depth == 2.75
    assert back_floor == col.bottom[-1].depth == 2.25


def test_straight_tops_when_rise_is_zero():
    d = Design(OrganizerConfig(corner_rise=0, notch_depth=1.25))
    assert all(getattr(p.outline, "top_profile", None) is None for p in d.panels)
    assert d.level == 4.5 and d.slot_floor == 3.25 and d.back_level == 4.5


def test_symmetric_box_when_back_level_is_none():
    d = Design(OrganizerConfig(notch_depth=1.25, columns=[0]))
    by_name = {p.name: p for p in d.panels}
    assert by_name["wall_front"].outline is by_name["wall_back"].outline
    g = by_name["wall_left"].outline.top_profile
    assert g(0) == g(d.depth) == d.height
    assert by_name["column_1"].outline.top_profile is None


def test_steps_finish_one_gap_before_the_slots_for_any_gap():
    for gap in (0.25, 0.5, 1.5):
        d = Design(OrganizerConfig(step_gap=gap, gusset_leg=0, back_level=3.5, columns=[0]))
        t, w = 0.125, d.shoulder_width(0.5)
        assert d.front_wall_plateau[0] + w + gap == pytest.approx(min(d.column_grid.values()) - t)
        assert d.side_front_plateau + w + gap == pytest.approx(min(d.row_grid.values()) - t)
        assert d.depth - d.back_plateau - w - gap == pytest.approx(max(d.row_grid.values()) + t)
        assert min(d.front_wall_plateau[0], d.side_front_plateau, d.back_plateau) >= 0.25


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
    assert by_name["row_1"].outline.length == pytest.approx(3 * design.column_pitch - 0.25 + 0.5)


def test_cut_list_needs_passthrough_for_walls(design):
    fits = {label: fit for label, _, _, _, _, fit in design.cut_list()}
    assert fits["wall"] == "passthrough"
    sizes = sorted((L, H) for label, L, H, _, _, _ in design.cut_list() if label == "wall")
    assert sizes == [(20.125, 4.5), (29.625, 3.5), (29.625, 4.5)]   # back wall is a shorter part
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
    w = d.shoulder_width(0.5)
    import math
    k = math.floor((d.width / 2 - 0.25 - (1.5 + w + 0.5) - 0.125) / d.column_pitch + 1e-9)
    assert len(d.column_grid) == 2 * k + 1
    first = min(d.column_grid.values()) - 0.125
    assert first >= 0.25 + 1.5 + w + 0.5   # room for the corner plateau, a shoulder and a gap before the first slot
    assert d.front_wall_plateau[0] >= 1.5


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
