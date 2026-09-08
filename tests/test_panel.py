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
    assert (0.25, 4.2) in pts and (9.75, 4.3) in pts       # clipped notch corners
    assert not any(abs(x) < 1e-9 and y > 4.2 + 1e-9 for x, y in pts)
