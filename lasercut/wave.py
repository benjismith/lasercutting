"""Gently undulating edges.

`wander` lays out a Profile: fixed anchors the edge must pass through, with a varying
number of crests and troughs between them at irregular positions and heights, and
skewed rises and falls, all drawn from a seeded random generator so every panel
comes out different.
"""
from __future__ import annotations

import math
import random

from lasercut.panel import Point, Profile


def wander(length: float, anchors: list[Point], lo: float, hi: float,
           wavelength: float, rng: random.Random, min_spacing: float | None = None,
           max_slope: float = math.tan(math.radians(30))) -> Profile:
    """A wavy profile along [0, length] passing exactly through `anchors` (x, height),
    which must include x=0 and x=length.

    Between consecutive anchors the edge visits some crests and troughs, alternately
    in the upper and lower parts of [lo, hi]. How many is drawn around the span
    divided by `wavelength`, and their parity is picked so the edge always turns
    away from an anchor rather than sitting flat beside it. Positions are random
    with at least `min_spacing` between features (default a fifth of the wavelength,
    at least 2). Finally heights are pulled together wherever a rise or fall would be
    steeper than `max_slope`, so the edge stays gentle however bold the range.
    """
    anchors = sorted(anchors)
    if anchors[0][0] != 0.0 or anchors[-1][0] != length:
        raise ValueError("anchors must include x=0 and x=length")
    spacing = min_spacing if min_spacing is not None else max(2.0, 0.2 * wavelength)
    mid = (lo + hi) / 2
    pts: list[Point] = []
    skews: list[float] = []
    fixed: set[int] = set()
    for (xa, ha), (xb, hb) in zip(anchors, anchors[1:]):
        fixed.add(len(pts))
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
    fixed.add(len(pts))
    pts.append(anchors[-1])
    _limit_slopes(pts, skews, fixed, max_slope)
    return Profile(pts, skews)


def peak_slope_factor(skew: float) -> float:
    """How much steeper a skewed cosine segment gets at its steepest point than its
    average slope. It is pi/2 for a symmetric segment and rises with the skew."""
    best = 0.0
    for i in range(1, 400):
        u = i / 400
        best = max(best, skew * u ** (skew - 1) * math.sin(math.pi * u ** skew))
    return best * math.pi / 2


def _limit_slopes(pts: list[Point], skews: list[float], fixed: set[int], max_slope: float) -> None:
    """Pull neighbouring heights together until no segment is steeper than
    `max_slope` at its steepest point. Anchors (indices in `fixed`) never move."""
    factors = [peak_slope_factor(g) for g in skews]
    for _ in range(20):
        changed = False
        for i in range(len(pts) - 1):
            (x0, h0), (x1, h1) = pts[i], pts[i + 1]
            excess = abs(h1 - h0) - max_slope / factors[i] * (x1 - x0)
            if excess <= 1e-9 or (i in fixed and i + 1 in fixed):
                continue
            changed = True
            sign = 1.0 if h1 > h0 else -1.0
            if i in fixed:
                pts[i + 1] = (x1, h1 - sign * excess)
            elif i + 1 in fixed:
                pts[i] = (x0, h0 + sign * excess)
            else:
                pts[i] = (x0, h0 + sign * excess / 2)
                pts[i + 1] = (x1, h1 - sign * excess / 2)
        if not changed:
            return


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
