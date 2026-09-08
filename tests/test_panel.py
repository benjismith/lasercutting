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


def test_profile_is_level_at_control_points_and_smooth_between():
    from lasercut.panel import Profile
    f = Profile([(0, 4.5), (5, 4.0), (10, 4.5)])
    assert f(0) == 4.5 and f(5) == 4.0 and f(10) == 4.5
    assert f(2.5) == pytest.approx(4.25)
    assert f(-1) == 4.5 and f(11) == 4.5
    # nearly flat right next to a control point
    assert abs(f(0.25) - 4.5) < 0.005
    assert f.max == 4.5 and f.min == 4.0


def test_curved_top_with_notch():
    from lasercut.panel import Profile
    f = Profile([(0, 4.5), (5, 4.0), (10, 4.5)])
    p = PanelOutline(10, 4.5, top=[Notch(4.875, 5.125, 1.75)], top_profile=f)
    pts = p.points()
    top = [pt for pt in pts if pt[1] > 3.0]
    assert max(y for _, y in top) == pytest.approx(4.5)
    assert min(y for _, y in top) == pytest.approx(4.0, abs=0.01)
    assert (5.125, 2.75) in pts and (4.875, 2.75) in pts   # slot floor at height - depth
    assert 0 < p.area() < 45
    assert p.contains(5.0, 2.5) and not p.contains(5.0, 3.0) and not p.contains(5.0, 4.4)
    assert p.contains(2.5, 4.2) and not p.contains(2.5, 4.45)


def test_curved_top_rejects_bad_profiles():
    from lasercut.panel import Profile
    with pytest.raises(ValueError):
        PanelOutline(10, 4.5, top_profile=Profile([(0, 5.0), (10, 5.0)])).points()
    with pytest.raises(ValueError):
        PanelOutline(10, 4.5, top=[Notch(4, 6, 0.25)],
                     top_profile=Profile([(0, 4.5), (5, 4.0), (10, 4.5)])).points()


def test_wander_hits_anchors_and_stays_in_range():
    import random
    from lasercut.wave import wander
    f = wander(20.0, [(0.0, 4.0), (8.0, 4.0), (20.0, 4.0)], 4.0, 4.5, 10.0, random.Random("t"))
    for x in (0.0, 8.0, 20.0):
        assert f(x) == 4.0
    samples = [f(x / 10) for x in range(201)]
    assert 4.0 <= min(samples) and max(samples) <= 4.5
    assert max(samples) > 4.25
    g = wander(29.0, [(0.0, 4.4), (29.0, 4.2)], 4.0, 4.5, 10.0, random.Random("u"))
    assert g(0) == 4.4 and g(29) == 4.2
    # gentle: no chord steeper than about 25 degrees
    ys = [g(x / 8) for x in range(233)]
    assert max(abs(b - a) for a, b in zip(ys, ys[1:])) < 0.125 * 0.47
    with pytest.raises(ValueError):
        wander(10.0, [(1.0, 4.0), (10.0, 4.0)], 4.0, 4.5, 10.0, random.Random(1))


def test_different_seeds_give_different_profiles():
    import random
    from lasercut.wave import wander
    pins = [(0.0, 4.0), (20.0, 4.0)]
    shapes = {tuple(round(wander(20.0, pins, 4.0, 4.5, 10.0, random.Random(seed))(x / 4), 4)
                    for x in range(81)) for seed in range(6)}
    assert len(shapes) == 6


def test_skewed_profile_keeps_ends_level():
    from lasercut.panel import Profile
    f = Profile([(0, 4.0), (10, 4.5)], skews=[1.4])
    assert f(0) == 4.0 and f(10) == 4.5
    assert f(5) < 4.25                          # reaches the far level late
    assert abs(f(0.1) - 4.0) < 0.001 and abs(f(9.9) - 4.5) < 0.001
    with pytest.raises(ValueError):
        Profile([(0, 4.0), (10, 4.5)], skews=[0.4])


def test_side_notches_clip_to_a_low_corner():
    from lasercut.panel import Profile
    fingers = finger_notches(4.5, 0.25, 9, notch_first=True)   # top slot is a notch
    f = Profile([(0, 4.2), (5, 4.5), (10, 4.3)])
    p = PanelOutline(10, 4.5, left=fingers, right=fingers, top_profile=f)
    pts = p.points()
    assert max(y for _, y in pts) <= 4.5 + 1e-9
    # clipped notch corners (the curve may add a hair of height at the inner face)
    assert any(x == 0.25 and abs(y - 4.2) < 0.002 for x, y in pts)
    assert any(x == 9.75 and abs(y - 4.3) < 0.002 for x, y in pts)
    assert not any(abs(x) < 1e-9 and y > 4.2 + 1e-9 for x, y in pts)


def test_wander_caps_the_slope():
    import math
    import random
    from lasercut.wave import wander
    # a 1 in range with features allowed 2 in apart would be steeper than 30 degrees unlimited
    f = wander(12.0, [(0.0, 3.5), (12.0, 3.5)], 3.5, 4.5, 4.0, random.Random("steep"), min_spacing=2.0)
    ys = [f(x / 32) for x in range(12 * 32 + 1)]
    assert max(abs(b - a) for a, b in zip(ys, ys[1:])) <= (1 / 32) * math.tan(math.radians(31))
    assert f(0) == 3.5 and f(12) == 3.5


def has_sliver(pts):
    """True if the outline doubles back on itself: two consecutive edges pointing in
    nearly opposite directions."""
    n = len(pts)
    for i in range(n):
        (ax, ay), (bx, by), (cx, cy) = pts[i - 1], pts[i], pts[(i + 1) % n]
        ux, uy, vx, vy = bx - ax, by - ay, cx - bx, cy - by
        lu, lv = (ux * ux + uy * uy) ** 0.5, (vx * vx + vy * vy) ** 0.5
        if lu == 0 or lv == 0:
            return True
        cos = (ux * vx + uy * vy) / (lu * lv)
        if cos < -0.999:
            return True
    return False


def test_curved_top_over_corner_notches_leaves_no_sliver():
    from lasercut.panel import Profile
    fingers = finger_notches(4.5, 0.25, 9, notch_first=True)
    f = Profile([(0, 4.3), (7, 3.6), (14, 4.4), (20, 4.1)])
    slots = [Notch.centered(x, 0.25, 2.25) for x in (5.0, 10.0, 15.0)]
    p = PanelOutline(20, 4.5, left=fingers, right=fingers, top=slots, top_profile=f)
    pts = p.points()
    assert not has_sliver(pts)
    # nothing above the top corner notches within the neighbouring wall's thickness
    assert all(y <= 4.0 + 1e-9 for x, y in pts if x < 0.25 - 1e-9 or x > 19.75 + 1e-9)
    assert sum(1 for x, y in pts if abs(y - 2.25) < 1e-9) == 6
    # and the plain rectangular case is unchanged
    q = PanelOutline(20, 4.5, left=fingers, right=fingers, top=slots)
    assert not has_sliver(q.points())
    assert (19.75, 4.5) in q.points() and (0.25, 4.5) in q.points()


def test_raised_ends_round_and_ogee():
    import math
    from lasercut.panel import RaisedEnds
    f = RaisedEnds(20.0, 4.0, 0.5, 1.0, "round")
    assert f(0) == 4.5 and f(1.0) == 4.5 and f(19.0) == 4.5 and f(20.0) == 4.5
    assert f(1.5) == 4.0 and f(10.0) == 4.0 and f(18.5) == 4.0
    assert f(1.25) == pytest.approx(4.0 + math.sqrt(0.25 - 0.0625))
    assert f(18.75) == f(1.25)                                # symmetric
    xs = f.samples(0.0, 20.0)
    assert xs[0] == 0.0 and xs[-1] == 20.0 and len(xs) == 2 + 2 * 13
    assert f.samples(2.0, 18.0) == [2.0, 18.0]                # nothing to sample on the flat
    g = RaisedEnds(20.0, 4.0, 0.5, 1.0, "ogee")
    assert g(1.0) == 4.5 and g(1.5) == pytest.approx(4.0) and g(1.25) == pytest.approx(4.25)
    assert g(1.1) > 4.45 and g(1.4) < 4.05                    # level at both ends of the S
    with pytest.raises(ValueError):
        RaisedEnds(2.0, 4.0, 0.5, 1.0)


def test_raised_ends_outline_is_compact():
    import math
    from lasercut.panel import RaisedEnds
    f = RaisedEnds(20.0, 4.0, 0.5, 1.0)
    slots = [Notch.centered(x, 0.25, 1.75) for x in (5.0, 10.0, 15.0)]
    fingers = finger_notches(4.5, 0.25, 9, notch_first=True)
    p = PanelOutline(20, 4.5, left=fingers, right=fingers, top=slots, top_profile=f)
    pts = p.points()
    assert not has_sliver(pts)
    assert len(pts) < 80                                      # arcs sampled, flats not
    assert p.area() == pytest.approx(20 * 4.0 + 2 * (1.0 * 0.5 + math.pi * 0.25 / 4)
                                     - 2 * sum(n.width * n.depth for n in fingers if n.end <= 4.0)
                                     - 2 * 0.25 * 0.5           # top corner finger notches
                                     - 3 * 0.25 * 1.75, rel=0.01)


def test_stepped_ends_with_a_dropped_end():
    from lasercut.panel import SteppedEnds
    f = SteppedEnds(20.0, 4.0, 0.5, -0.5, 1.0, "ogee")
    assert f(0) == 4.5 and f(1.0) == 4.5 and f(1.5) == pytest.approx(4.0)
    assert f(10.0) == 4.0
    assert f(18.5) == pytest.approx(4.0) and f(18.75) == pytest.approx(3.75)
    assert f(19.0) == 3.5 and f(20.0) == 3.5
    assert f(18.6) > 3.95 and f(18.9) < 3.55                   # inverted S is level at both ends
    assert f.top == 4.5
    g = SteppedEnds(20.0, 4.0, 0.0, -0.5, 1.0)
    assert g(0) == 4.0 and g(0.5) == 4.0 and g.top == 4.0
    assert g.samples(0.0, 10.0) == [0.0, 10.0]                  # no shoulder at the flat end
    assert len(g.samples(18.0, 20.0)) == 2 + 13
    r = SteppedEnds(20.0, 4.0, 0.0, -0.5, 1.0, "round")
    assert r(18.5) == pytest.approx(4.0) and r(19.0) == 3.5
    assert r(18.75) == pytest.approx(4.0 - (0.25 - 0.0625) ** 0.5)
