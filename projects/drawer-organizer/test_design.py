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
    assert design.ear_top == 3.5 and design.slot_floor == 2.25
    assert design.top_notch_depth == 2.25
    assert design.top_notch_depth + design.bottom_notch_depth == design.height


def test_wavy_tops_follow_the_joint_rule(design):
    H, low, t = design.height, design.ear_top, 0.25
    by_kind = {}
    for p in design.panels:
        by_kind.setdefault(p.kind, []).append(p)
    walls = {w.name: w.outline.top_profile for w in by_kind["wall"]}
    W, D = design.width, design.depth
    # the two walls meeting at each corner agree on its height
    assert walls["wall_front"](0) == walls["wall_left"](0)
    assert walls["wall_front"](W) == walls["wall_right"](0)
    assert walls["wall_back"](0) == walls["wall_left"](D)
    assert walls["wall_back"](W) == walls["wall_right"](D)
    assert len({round(walls["wall_front"](0), 6), round(walls["wall_front"](W), 6),
                round(walls["wall_back"](0), 6), round(walls["wall_back"](W), 6)}) == 4
    for w in by_kind["wall"]:
        f = w.outline.top_profile
        swing = design.cfg.wave_swing
        assert low + 0.4 * swing <= f(0) <= H and low + 0.4 * swing <= f(w.outline.length) <= H
        assert low <= min(f(x / 8) for x in range(int(w.outline.length * 8))) <= H
        for n in w.outline.top:                                   # ears never stand proud
            assert f((n.start + n.end) / 2) >= low - 1e-9
    for c in by_kind["column"]:
        f = c.outline.top_profile
        assert f(0) == low and f(c.outline.length) == low         # ends dip to the ear level
        assert max(f(x / 8) for x in range(int(c.outline.length * 8))) > low + 0.3
    for r in by_kind["row"]:
        f = r.outline.top_profile
        assert f(0) == low and f(r.outline.length) == low         # ends dip to the ear level
        for n in r.outline.bottom[1:-1]:                          # and so does every crossing
            assert f((n.start + n.end) / 2) == pytest.approx(low, abs=1e-9)
    # nothing steeper than about 30 degrees anywhere, even with a 1 in swing
    for p in design.panels:
        f = getattr(p.outline, "top_profile", None)
        if f is None:
            continue
        ys = [f(x / 16) for x in range(int(p.outline.length * 16) + 1)]
        assert max(abs(b - a) for a, b in zip(ys, ys[1:])) <= (1 / 16) * 0.60
    # no two column dividers share a shape, and they differ in how many crests they have
    shapes = {tuple(c.outline.points()) for c in by_kind["column"]}
    assert len(shapes) == len(by_kind["column"])
    crests = {len([h for h in c.outline.top_profile.hs if h > low + 0.25]) for c in by_kind["column"]}
    assert len(crests) > 1


def test_straight_tops_when_swing_is_zero():
    d = Design(OrganizerConfig(height=4.5, wave_swing=0, notch_depth=1.25))
    assert all(p.outline.top_profile is None for p in d.panels if p.kind != "gusset")
    assert d.slot_floor == 3.25


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
    assert len(d.column_grid) == 19


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
