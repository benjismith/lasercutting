"""Flat panels: a rectangle with rectangular notches taken out of its edges.

Everything the laser cuts for us is a flat panel of sheet stock. A panel is described
in its own 2D coordinates (x along its length, y along its height, origin at the
bottom-left corner) and gets a Placement to position it in 3D. The same outline later
becomes a cut path, so this module stays free of Blender imports.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

EPS = 1e-7

Point = tuple[float, float]
Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class Notch:
    """A rectangular bite out of one edge of a panel.

    `start` and `end` are positions along the edge in panel coordinates (x for the top
    and bottom edges, y for the left and right edges). `depth` is how far the notch
    reaches into the panel, perpendicular to that edge.
    """

    start: float
    end: float
    depth: float

    def __post_init__(self) -> None:
        if self.end - self.start <= EPS:
            raise ValueError(f"notch has no width: {self}")
        if self.depth <= EPS:
            raise ValueError(f"notch has no depth: {self}")

    @property
    def width(self) -> float:
        return self.end - self.start

    @classmethod
    def centered(cls, center: float, width: float, depth: float) -> "Notch":
        return cls(center - width / 2, center + width / 2, depth)


@dataclass
class PanelOutline:
    """A `length` x `height` rectangle with notches on any of its four edges.

    Notches on the bottom edge cut upward from y=0, on the top edge downward from
    y=height, on the left edge inward from x=0, on the right edge inward from x=length.
    A notch may sit at a corner: a notch on the bottom edge starting at x=0 simply
    removes that corner, which is how finger joints and egg-crate ends are expressed.
    """

    length: float
    height: float
    bottom: list[Notch] = field(default_factory=list)
    right: list[Notch] = field(default_factory=list)
    top: list[Notch] = field(default_factory=list)
    left: list[Notch] = field(default_factory=list)

    def validate(self) -> None:
        edges = (
            ("bottom", self.bottom, self.length, self.height),
            ("top", self.top, self.length, self.height),
            ("left", self.left, self.height, self.length),
            ("right", self.right, self.height, self.length),
        )
        for name, notches, along, across in edges:
            prev_end = -math.inf
            for n in sorted(notches, key=lambda n: n.start):
                if n.start < -EPS or n.end > along + EPS:
                    raise ValueError(f"{name} notch {n} falls outside the edge (length {along})")
                if n.depth >= across - EPS:
                    raise ValueError(f"{name} notch {n} cuts right through the panel ({across})")
                if n.start < prev_end - EPS:
                    raise ValueError(f"{name} notches overlap at {n}")
                prev_end = n.end

    def points(self) -> list[Point]:
        """The outline as a simple polygon, counter-clockwise, starting near the
        bottom-left corner. Notched corners are handled by walking each edge with
        its notches and then removing the spikes and duplicates that leaves."""
        self.validate()
        L, H = self.length, self.height
        pts: list[Point] = [(0.0, 0.0)]
        for n in sorted(self.bottom, key=lambda n: n.start):
            pts += [(n.start, 0.0), (n.start, n.depth), (n.end, n.depth), (n.end, 0.0)]
        pts.append((L, 0.0))
        for n in sorted(self.right, key=lambda n: n.start):
            pts += [(L, n.start), (L - n.depth, n.start), (L - n.depth, n.end), (L, n.end)]
        pts.append((L, H))
        for n in sorted(self.top, key=lambda n: n.start, reverse=True):
            pts += [(n.end, H), (n.end, H - n.depth), (n.start, H - n.depth), (n.start, H)]
        pts.append((0.0, H))
        for n in sorted(self.left, key=lambda n: n.start, reverse=True):
            pts += [(0.0, n.end), (n.depth, n.end), (n.depth, n.start), (0.0, n.start)]
        return simplify(pts)

    def area(self) -> float:
        return polygon_area(self.points())

    def contains(self, x: float, y: float) -> bool:
        return point_in_polygon(self.points(), x, y)

    def size(self) -> tuple[float, float]:
        return (self.length, self.height)


class PolygonOutline:
    """Any simple polygon, given directly as counter-clockwise points. For panels that
    are not notched rectangles, such as a triangular corner gusset."""

    def __init__(self, points: list[Point]):
        self._points = simplify(points)
        if polygon_area(self._points) <= 0:
            raise ValueError("polygon points must run counter-clockwise")

    def points(self) -> list[Point]:
        return list(self._points)

    def area(self) -> float:
        return polygon_area(self._points)

    def contains(self, x: float, y: float) -> bool:
        return point_in_polygon(self._points, x, y)

    def size(self) -> tuple[float, float]:
        xs = [p[0] for p in self._points]
        ys = [p[1] for p in self._points]
        return (max(xs) - min(xs), max(ys) - min(ys))


def corner_gusset(leg: float, tab_depth: float, tabs: list[tuple[float, float]]) -> PolygonOutline:
    """A right isosceles triangle with its legs along +x and +y from the origin, with
    tabs sticking `tab_depth` outward from both legs over the given spans (measured
    from the right-angle corner). The tabs pass through the walls the legs sit against."""
    pts: list[Point] = [(0.0, 0.0)]
    for a, b in sorted(tabs):
        pts += [(a, 0.0), (a, -tab_depth), (b, -tab_depth), (b, 0.0)]
    pts += [(leg, 0.0), (0.0, leg)]
    for a, b in sorted(tabs, reverse=True):
        pts += [(0.0, b), (-tab_depth, b), (-tab_depth, a), (0.0, a)]
    return PolygonOutline(pts)


def even_tab_spans(length: float, count: int) -> list[tuple[float, float]]:
    """`count` tabs spread evenly along `length`, tabs and gaps all the same width,
    with a gap at each end."""
    w = length / (2 * count + 1)
    return [((2 * i + 1) * w, (2 * i + 2) * w) for i in range(count)]


def point_in_polygon(pts: list[Point], x: float, y: float) -> bool:
    """Even-odd test."""
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            x_cross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def _close(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) < EPS and abs(a[1] - b[1]) < EPS


def simplify(pts: list[Point]) -> list[Point]:
    """Drop repeated points and any point lying on the straight line through its
    neighbours. That also removes the spikes the edge walk leaves at a notched
    corner (it steps to the corner and straight back)."""
    pts = list(pts)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        kept: list[Point] = []
        n = len(pts)
        for i, p in enumerate(pts):
            a, b = pts[i - 1], pts[(i + 1) % n]
            if _close(p, a) or abs(_cross(a, p, b)) < EPS:
                changed = True
                continue
            kept.append(p)
        pts = kept
    return pts


def polygon_area(pts: list[Point]) -> float:
    """Signed shoelace area; positive for counter-clockwise outlines."""
    total = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        total += x0 * y1 - x1 * y0
    return total / 2


def odd_finger_count(edge_length: float, target_width: float) -> int:
    """Largest odd number of fingers whose width is at least `target_width`."""
    n = int(edge_length / target_width + 1e-9)
    if n % 2 == 0:
        n -= 1
    return max(n, 3)


def finger_notches(edge_length: float, depth: float, count: int, notch_first: bool) -> list[Notch]:
    """Finger-joint profile for one edge: `count` equal slots, alternating finger and
    notch. With `notch_first` the slot touching the edge's start (and, since the count
    is odd, its end) is a notch; the mating panel uses the opposite setting."""
    if count < 3 or count % 2 == 0:
        raise ValueError("finger count must be odd and at least 3")
    f = edge_length / count
    return [Notch(i * f, (i + 1) * f, depth) for i in range(count) if (i % 2 == 0) == notch_first]


@dataclass(frozen=True)
class Placement:
    """Where a panel sits in 3D. Panel point (x, y) at depth d through the stock maps
    to origin + x*u + y*v + d*n. u, v, n are unit vectors and mutually perpendicular."""

    origin: Vec3
    u: Vec3
    v: Vec3
    n: Vec3

    def to_world(self, x: float, y: float, d: float = 0.0) -> Vec3:
        o, u, v, n = self.origin, self.u, self.v, self.n
        return tuple(o[i] + x * u[i] + y * v[i] + d * n[i] for i in range(3))  # type: ignore[return-value]

    def to_panel(self, p: Vec3) -> Vec3:
        r = tuple(p[i] - self.origin[i] for i in range(3))
        dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
        return (dot(r, self.u), dot(r, self.v), dot(r, self.n))

    @classmethod
    def upright_along_x(cls, origin: Vec3) -> "Placement":
        """Standing panel whose length runs along +X, thickness toward +Y."""
        return cls(origin, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))

    @classmethod
    def upright_along_y(cls, origin: Vec3) -> "Placement":
        """Standing panel whose length runs along +Y, thickness toward +X."""
        return cls(origin, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))

    @classmethod
    def flat(cls, origin: Vec3, x_sign: float = 1.0, y_sign: float = 1.0) -> "Placement":
        """Panel lying in the XY plane, thickness upward; the signs mirror its axes so
        one part can be placed in any of four corners."""
        return cls(origin, (x_sign, 0.0, 0.0), (0.0, y_sign, 0.0), (0.0, 0.0, 1.0))


@dataclass
class Panel:
    name: str
    outline: PanelOutline | PolygonOutline
    thickness: float
    placement: Placement
    kind: str = "panel"

    def contains(self, p: Vec3) -> bool:
        x, y, d = self.placement.to_panel(p)
        return 0.0 < d < self.thickness and self.outline.contains(x, y)

    def bounds(self) -> tuple[Vec3, Vec3]:
        corners = [self.placement.to_world(x, y, d)
                   for x, y in self.outline.points()
                   for d in (0.0, self.thickness)]
        lo = tuple(min(c[i] for c in corners) for i in range(3))
        hi = tuple(max(c[i] for c in corners) for i in range(3))
        return lo, hi  # type: ignore[return-value]
