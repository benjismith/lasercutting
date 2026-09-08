import math
import re

import pytest

from lasercut.nest import Part, nest
from lasercut.panel import Notch, Panel, PanelOutline, Placement, SteppedEnds, offset_polygon, polygon_area
from lasercut.svg import Sheet, part_path, placement_transform


def test_offset_grows_the_part_and_shrinks_its_slots():
    p = PanelOutline(10, 4, top=[Notch(4.875, 5.125, 1.25)])
    pts = p.points()
    off = offset_polygon(pts, 0.004)
    xs = [q[0] for q in off]
    ys = [q[1] for q in off]
    assert min(xs) == pytest.approx(-0.004) and max(xs) == pytest.approx(10.004)
    assert min(ys) == pytest.approx(-0.004) and max(ys) == pytest.approx(4.004)
    slot = sorted(q[0] for q in off if abs(q[1] - (4 - 1.25 + 0.004)) < 1e-9)
    assert slot[1] - slot[0] == pytest.approx(0.25 - 0.008)       # slot narrower by the full kerf
    assert polygon_area(off) > polygon_area(pts)


def test_offset_handles_a_gusset_corner():
    from lasercut.panel import corner_gusset, even_tab_spans
    g = corner_gusset(3.0, 0.25, even_tab_spans(3.0, 2))
    off = offset_polygon(g.points(), 0.004)
    assert len(off) == len(g.points())
    assert polygon_area(off) > polygon_area(g.points())


def test_nest_keeps_parts_inside_and_apart():
    parts = [Part("a", 29.625, 4.5), Part("b", 20.125, 4.5), Part("c", 20.125, 4.0),
             Part("d", 5.0, 4.0), Part("e", 3.25, 3.25), Part("f", 10.0, 4.0)]
    result = nest(parts, 19.5, gap=0.1, tries=40)
    boxes = [(p.x, p.y, p.x + p.width, p.y + p.height) for p in result.placed]
    for x0, y0, x1, y1 in boxes:
        assert x0 >= 0.1 - 1e-9 and x1 <= 19.5 - 0.1 + 1e-9 and y0 >= 0.1 - 1e-9
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert a[2] + 0.1 <= b[0] + 1e-9 or b[2] + 0.1 <= a[0] + 1e-9 \
                or a[3] + 0.1 <= b[1] + 1e-9 or b[3] + 0.1 <= a[1] + 1e-9
    assert {p.name for p in result.placed} == {p.name for p in parts}
    long = next(p for p in result.placed if p.name == "a")
    assert long.rotated and long.height == 29.625                  # too long to lie across
    assert result.length <= 29.625 + 20.125 + 0.4                  # no worse than stacking the two longest


def test_nest_rejects_impossible_parts():
    with pytest.raises(ValueError):
        nest([Part("x", 25.0, 21.0)], 19.5)
    with pytest.raises(ValueError):
        nest([Part("x", 10.0, 10.0), Part("y", 10.0, 10.0)], 19.5, max_length=12.0)


def test_part_path_uses_beziers_for_ease_shoulders():
    prof = SteppedEnds(20.0, 4.0, 0.5, -0.5, 1.5, "ease", end_plateau=2.0, run=2.0)
    outline = PanelOutline(20.0, 4.5, top=[Notch.centered(10.0, 0.25, 1.75)], top_profile=prof)
    panel = Panel("p", outline, 0.25, Placement.upright_along_x((0, 0, 0)))
    d = part_path(panel, 0.008, lambda x, y: (x, 10 - y))
    assert d.startswith("M ") and d.endswith(" Z")
    assert d.count(" C ") == 2                                     # one Bezier per shoulder
    assert d.count(" L ") < 30                                     # no sampled points left in the curves
    # the top edge is walked right to left, so the back shoulder (x 16..18) comes first
    curves = re.findall(r"C ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)", d)
    ends = sorted(float(c[4]) for c in curves)
    assert ends == pytest.approx([1.5, 16.0], abs=2e-3)
    front = next(c for c in curves if abs(float(c[4]) - 1.5) < 2e-3)
    c1x, c1y, c2x, c2y, ex, ey = (float(v) for v in front)
    assert ey == pytest.approx(10 - 4.504, abs=1e-3)                 # lands on the raised plateau, offset up
    assert c2x == pytest.approx(1.5 + 2.0 / 3, abs=2e-3) and c1x == pytest.approx(3.5 - 2.0 / 3, abs=2e-3)


def test_sheet_document_is_in_inches():
    s = Sheet(20.0, 52.0)
    s.add("M 0 0 L 1 0 L 1 1 Z", "a")
    s.add_line((0, 0), (1, 1), "t")
    text = s.render()
    assert 'width="20in" height="52in" viewBox="0 0 20 52"' in text
    assert '<g id="cut"' in text and '<g id="score"' in text
    assert 'id="a"' in text and text.count("<path") == 2


def test_placement_transform_orientations():
    t = placement_transform(1.0, 2.0, 0.0, 0.0, 10.0, 4.0, rotated=False)
    assert t(0.0, 0.0) == (1.0, 6.0) and t(10.0, 4.0) == (11.0, 2.0)  # y up in the part, down on the sheet
    r = placement_transform(1.0, 2.0, 0.0, 0.0, 10.0, 4.0, rotated=True)
    assert r(0.0, 0.0) == (1.0, 2.0) and r(10.0, 4.0) == (5.0, 12.0)   # length runs down the sheet
