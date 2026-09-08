"""Gently undulating edges.

`undulation` lays out control points for a Profile: anchors that the edge must pass
through at a fixed level, with crests (or troughs) between them whose positions and
heights are jittered by a seeded random generator so that no two panels match.
"""
from __future__ import annotations

import random

from lasercut.panel import Point, Profile


def undulation(length: float, anchors: list[float], level: float, swing: float,
               wavelength: float, direction: int, rng: random.Random) -> Profile:
    """A wavy profile along [0, length].

    The edge sits exactly at `level` at x=0, x=length and every x in `anchors`.
    Between consecutive anchors it swings away from `level` by up to `swing`, in
    `direction` (+1 up, -1 down), with roughly one full swing per `wavelength`.
    Successive swings within a span come back only part way, so the highs and lows
    vary. `rng` supplies the variation; seed it per panel for distinct shapes.
    """
    xs = sorted({0.0, length, *anchors})
    pts: list[Point] = []
    for a, b in zip(xs, xs[1:]):
        pts.append((a, level))
        span = b - a
        k = max(1, round(span / wavelength))
        seg = span / k
        for i in range(k):
            cx = a + seg * (i + 0.5 + rng.uniform(-0.15, 0.15))
            pts.append((cx, level + direction * swing * rng.uniform(0.7, 1.0)))
            if i < k - 1:
                mx = a + seg * (i + 1 + rng.uniform(-0.1, 0.1))
                pts.append((mx, level + direction * swing * rng.uniform(0.0, 0.3)))
    pts.append((length, level))
    return Profile(pts)
