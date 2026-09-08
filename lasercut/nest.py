"""Nesting rectangular parts on a sheet of fixed width and open-ended length.

The Glowforge Pro's passthrough makes the feed direction effectively unlimited, so
the goal is the shortest sheet. Parts are packed as bounding boxes with the MaxRects
heuristic, choosing for each part the free rectangle that keeps the used length
shortest, trying both orientations. Because the heuristic is order-sensitive, many
orderings are tried and the best kept.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Part:
    name: str
    width: float   # bounding box along the sheet's width when not rotated
    height: float  # bounding box along the sheet's length when not rotated


@dataclass(frozen=True)
class Placed:
    name: str
    x: float        # across the sheet
    y: float        # along the sheet (feed direction)
    width: float    # footprint across, after any rotation
    height: float   # footprint along
    rotated: bool


@dataclass
class Nesting:
    placed: list[Placed]
    length: float                 # sheet length used
    leftover: list[Part] = field(default_factory=list)   # parts that did not fit (fixed-length sheets only)


_Rect = tuple[float, float, float, float]  # x, y, w, h


def nest(parts: list[Part], width: float, gap: float = 0.0, tries: int = 300,
         seed: int = 1, max_length: float | None = None) -> Nesting:
    """Pack `parts` onto a sheet `width` across, with at least `gap` between parts
    and from the edges, minimising the length used. With `max_length` the sheet is
    that long: parts that do not fit are returned in `leftover` (the ordering that
    places the most area wins, then the shortest), and a part that can never fit
    raises ValueError."""
    for p in parts:
        if min(p.width, p.height) + 2 * gap > width:
            raise ValueError(f"{p.name} is too wide for the sheet in either orientation")
        if max_length is not None:
            fits_flat = p.width + 2 * gap <= width and p.height + 2 * gap <= max_length
            fits_turned = p.height + 2 * gap <= width and p.width + 2 * gap <= max_length
            if not (fits_flat or fits_turned):
                raise ValueError(f"{p.name} does not fit the sheet in either orientation")
    rng = random.Random(seed)
    orders = [
        sorted(parts, key=lambda p: -max(p.width, p.height)),
        sorted(parts, key=lambda p: -p.width * p.height),
        sorted(parts, key=lambda p: (-max(p.width, p.height), -min(p.width, p.height))),
        sorted(parts, key=lambda p: -min(p.width, p.height)),
    ]
    while len(orders) < tries:
        order = list(parts)
        rng.shuffle(order)
        orders.append(order)
    best: Nesting | None = None
    for order in orders:
        result = _pack(order, width, gap, max_length)
        if best is None or _better(result, best):
            best = result
    assert best is not None
    return best


def _placed_area(n: Nesting) -> float:
    return sum(p.width * p.height for p in n.placed)


def _better(a: Nesting, b: Nesting) -> bool:
    """More placed area wins; then the shorter sheet."""
    if abs(_placed_area(a) - _placed_area(b)) > 1e-9:
        return _placed_area(a) > _placed_area(b)
    return a.length < b.length - 1e-9


def _pack(order: list[Part], width: float, gap: float, max_length: float | None) -> Nesting:
    inner_w = width - gap                      # each part carries one gap on its right and top
    limit = (max_length - gap) if max_length is not None else 1e9
    free: list[_Rect] = [(gap, gap, inner_w - gap, limit - gap)]
    placed: list[Placed] = []
    leftover: list[Part] = []
    used = 0.0
    for part in order:
        choice = None
        for fx, fy, fw, fh in free:
            for rotated in (False, True):
                w, h = (part.height, part.width) if rotated else (part.width, part.height)
                w_g, h_g = w + gap, h + gap
                if w_g <= fw + 1e-9 and h_g <= fh + 1e-9:
                    score = (fy + h_g, fx)
                    if choice is None or score < choice[0]:
                        choice = (score, fx, fy, w, h, rotated)
        if choice is None:
            leftover.append(part)
            continue
        _, x, y, w, h, rotated = choice
        placed.append(Placed(part.name, x, y, w, h, rotated))
        used = max(used, y + h)
        free = _split(free, (x, y, w + gap, h + gap))
    return Nesting(placed, used + gap, leftover)


def _split(free: list[_Rect], used: _Rect) -> list[_Rect]:
    ux, uy, uw, uh = used
    out: list[_Rect] = []
    for fx, fy, fw, fh in free:
        if ux >= fx + fw or ux + uw <= fx or uy >= fy + fh or uy + uh <= fy:
            out.append((fx, fy, fw, fh))
            continue
        if ux > fx:
            out.append((fx, fy, ux - fx, fh))
        if ux + uw < fx + fw:
            out.append((ux + uw, fy, fx + fw - ux - uw, fh))
        if uy > fy:
            out.append((fx, fy, fw, uy - fy))
        if uy + uh < fy + fh:
            out.append((fx, uy + uh, fw, fy + fh - uy - uh))
    # drop rectangles contained in another (keeping the first of any duplicates)
    kept: list[_Rect] = []
    for i, a in enumerate(out):
        redundant = any(_contains(b, a) and (not _contains(a, b) or j < i)
                        for j, b in enumerate(out) if j != i)
        if not redundant:
            kept.append(a)
    return kept


def _contains(outer: _Rect, inner: _Rect) -> bool:
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return ix >= ox - 1e-9 and iy >= oy - 1e-9 and ix + iw <= ox + ow + 1e-9 and iy + ih <= oy + oh + 1e-9
