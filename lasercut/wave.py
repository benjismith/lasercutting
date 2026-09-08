"""Gently undulating edges.

`wander` lays out a Profile: fixed anchors the edge must pass through, with a varying
number of crests and troughs between them at irregular positions and heights, and
skewed rises and falls, all drawn from a seeded random generator so every panel
comes out different.
"""
from __future__ import annotations

import random

from lasercut.panel import Point, Profile


def wander(length: float, anchors: list[Point], lo: float, hi: float,
           wavelength: float, rng: random.Random, min_spacing: float | None = None) -> Profile:
    """A wavy profile along [0, length] passing exactly through `anchors` (x, height),
    which must include x=0 and x=length.

    Between consecutive anchors the edge visits some crests and troughs, alternately
    in the upper and lower parts of [lo, hi]. How many is drawn around the span
    divided by `wavelength`, and their parity is picked so the edge always turns
    away from an anchor rather than sitting flat beside it. Positions are random
    with at least `min_spacing` between features (default a fifth of the wavelength,
    at least 2), which is what keeps the slopes gentle.
    """
    anchors = sorted(anchors)
    if anchors[0][0] != 0.0 or anchors[-1][0] != length:
        raise ValueError("anchors must include x=0 and x=length")
    spacing = min_spacing if min_spacing is not None else max(2.0, 0.2 * wavelength)
    mid = (lo + hi) / 2
    pts: list[Point] = []
    skews: list[float] = []
    for (xa, ha), (xb, hb) in zip(anchors, anchors[1:]):
        pts.append((xa, ha))
        span = xb - xa
        first_high = ha < mid                    # turn away from the anchor
        want_odd = (ha < mid) == (hb < mid)      # so the last feature turns toward the next anchor
        base = max(1, round(span / wavelength))
        room = int((span - spacing) // spacing)  # most features that can fit
        options = [n for n in range(max(1, base - 1), base + 3)
                   if n % 2 == (1 if want_odd else 0) and n <= room]
        n = rng.choice(options) if options else (1 if want_odd else 2)
        xs = _spread(xa, xb, n, spacing, rng)
        for i, x in enumerate(xs):
            high = first_high if i % 2 == 0 else not first_high
            h = rng.uniform(lo + 0.55 * (hi - lo), hi) if high else rng.uniform(lo, lo + 0.45 * (hi - lo))
            pts.append((x, h))
        skews += [rng.uniform(0.7, 1.45) for _ in range(n + 1)]
    pts.append(anchors[-1])
    return Profile(pts, skews)


def _spread(xa: float, xb: float, n: int, spacing: float, rng: random.Random) -> list[float]:
    """`n` sorted positions strictly inside (xa, xb), each at least `spacing` from its
    neighbours and from the ends; falls back to jittered even spacing if random
    placement keeps failing."""
    lo, hi = xa + spacing, xb - spacing
    if n == 1:
        return [rng.uniform(lo, hi)] if hi > lo else [(xa + xb) / 2]
    for _ in range(200):
        xs = sorted(rng.uniform(lo, hi) for _ in range(n))
        if all(b - a >= spacing for a, b in zip(xs, xs[1:])):
            return xs
    seg = (xb - xa) / (n + 1)
    return [xa + seg * (i + 1) + rng.uniform(-0.2, 0.2) * seg for i in range(n)]
