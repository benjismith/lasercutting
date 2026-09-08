import pytest

from lasercut.glowforge import bed_fit
from lasercut.panel import Notch, PanelOutline, Placement, finger_notches, odd_finger_count, polygon_area


def axis_aligned(pts):
    n = len(pts)
    return all(pts[i][0] == pts[(i + 1) % n][0] or pts[i][1] == pts[(i + 1) % n][1] for i in range(n))


def test_plain_rectangle():
    p = PanelOutline(10, 4)
    assert p.points() == [(0, 0), (10, 0), (10, 4), (0, 4)]
    assert p.area() == 40


def test_top_notch_in_the_middle():
    p = PanelOutline(10, 4, top=[Notch(4, 5, 2)])
    pts = p.points()
    assert len(pts) == 8
    assert p.area() == 40 - 2
    assert axis_aligned(pts)


def same_cycle(a, b):
    return len(a) == len(b) and any(a[i:] + a[:i] == b for i in range(len(a)))


def test_corner_notch_removes_the_corner_cleanly():
    p = PanelOutline(10, 4, bottom=[Notch(0, 1, 2)])
    assert same_cycle(p.points(), [(1, 0), (10, 0), (10, 4), (0, 4), (0, 2), (1, 2)])
    assert p.area() == 40 - 2


def test_touching_notches_of_different_depth():
    p = PanelOutline(10, 4, bottom=[Notch(2, 3, 1), Notch(3, 4, 2)])
    pts = p.points()
    assert len(set(pts)) == len(pts)
    assert axis_aligned(pts)
    assert p.area() == 40 - 1 - 2


def test_finger_joint_edges_are_complementary():
    a = finger_notches(5.5, 0.25, 11, notch_first=False)
    b = finger_notches(5.5, 0.25, 11, notch_first=True)
    assert len(a) == 5 and len(b) == 6
    spans = sorted([(n.start, n.end) for n in a + b])
    assert spans[0][0] == 0 and spans[-1][1] == 5.5
    assert all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1))


def test_side_wall_with_corner_fingers_and_top_notches():
    fingers = finger_notches(5.5, 0.25, 11, notch_first=True)
    tops = [Notch.centered(x, 0.25, 2.75) for x in (3.0, 6.0, 9.0)]
    p = PanelOutline(12, 5.5, left=fingers, right=fingers, top=tops)
    pts = p.points()
    assert len(set(pts)) == len(pts)
    assert axis_aligned(pts)
    expected = 12 * 5.5 - 2 * sum(n.width * n.depth for n in fingers) - sum(n.width * n.depth for n in tops)
    assert p.area() == pytest.approx(expected)
    assert p.contains(6.0, 1.0) and not p.contains(6.0, 5.0) and not p.contains(0.1, 0.1)


def test_validation_rejects_bad_notches():
    with pytest.raises(ValueError):
        PanelOutline(10, 4, top=[Notch(1, 3, 1), Notch(2, 4, 1)]).points()
    with pytest.raises(ValueError):
        PanelOutline(10, 4, top=[Notch(9, 11, 1)]).points()
    with pytest.raises(ValueError):
        PanelOutline(10, 4, top=[Notch(1, 2, 4)]).points()
    with pytest.raises(ValueError):
        Notch(2, 2, 1)


def test_odd_finger_count():
    assert odd_finger_count(5.5, 0.5) == 11
    assert odd_finger_count(6.0, 0.5) == 11
    assert odd_finger_count(1.0, 0.5) == 3


def test_placement_round_trip():
    pl = Placement.upright_along_y((3, 0, 0))
    w = pl.to_world(2, 1, 0.25)
    assert w == (3.25, 2, 1)
    assert pl.to_panel(w) == pytest.approx((2, 1, 0.25))


def test_polygon_area_sign():
    assert polygon_area([(0, 0), (1, 0), (1, 1), (0, 1)]) == 1
    assert polygon_area([(0, 0), (0, 1), (1, 1), (1, 0)]) == -1


def test_bed_fit():
    assert bed_fit(19.5, 11) == "fits bed"
    assert bed_fit(5.5, 29.625) == "passthrough"
    assert bed_fit(20.125, 5.5) == "passthrough"
    assert bed_fit(20, 20) == "too wide"
