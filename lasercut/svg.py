"""SVG cut files.

Documents are written in real inches: `width="20in"` with a matching viewBox, so one
user unit is one inch and no viewer has to guess a DPI. Each part is one closed path;
straight edges are lines and ease shoulders are cubic Beziers. Every part is offset
outward by half the kerf before writing, so it comes off the laser at nominal size.
Stroke colour selects the Glowforge operation: one colour for cuts, another for scores.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from lasercut.panel import Panel, Point, offset_polygon

CUT = "#000000"
SCORE = "#0000ff"
STROKE_WIDTH = 0.01

Transform = Callable[[float, float], Point]


def part_path(panel: Panel, kerf: float, place: Transform) -> str:
    """SVG path data for one part: its outline offset by half the kerf, with ease
    shoulders as Beziers, mapped through `place` (panel coords to sheet coords)."""
    outline = panel.outline
    pts = outline.points()
    off = offset_polygon(pts, kerf / 2) if kerf else pts
    curves = _bezier_runs(outline, pts)
    cmds: list[str] = []
    i = 0
    n = len(pts)
    while i < n:
        x, y = place(*off[i])
        cmds.append(f"{'M' if i == 0 else 'L'} {x:.4f} {y:.4f}")
        if i in curves:
            j, run = curves[i]
            (x0, y0), (x1, y1) = off[i], off[j]
            # walking the top edge right to left: from x_end down to x_start
            c1 = place(x0 - run / 3, y0)
            c2 = place(x1 + run / 3, y1)
            end = place(x1, y1)
            cmds.append(f"C {c1[0]:.4f} {c1[1]:.4f} {c2[0]:.4f} {c2[1]:.4f} {end[0]:.4f} {end[1]:.4f}")
            i = j + 1
        else:
            i += 1
    cmds.append("Z")
    return " ".join(cmds)


def _bezier_runs(outline, pts: list[Point]) -> dict[int, tuple[int, float]]:
    """Index of the first sampled point of each ease shoulder -> (index of its last
    point, run). The outline walks the top edge right to left, so a run starts at
    the shoulder's x_end and finishes at its x_start."""
    profile = getattr(outline, "top_profile", None)
    spans = getattr(profile, "bezier_spans", lambda: [])()
    if not spans:
        return {}
    runs: dict[int, tuple[int, float]] = {}
    for x_start, x_end, h_start, h_end in spans:
        found = False
        for i, (x, y) in enumerate(pts):
            if abs(x - x_end) > 1e-6 or abs(y - h_end) > 1e-6:
                continue
            # follow the sampled curve leftwards to the shoulder's start (the
            # simplifier may have dropped a collinear sample near the inflection)
            j = i + 1
            while j < len(pts) and x_start + 1e-6 < pts[j][0] < x_end:
                j += 1
            if j < len(pts) and abs(pts[j][0] - x_start) < 1e-6 and abs(pts[j][1] - h_start) < 1e-6 and j > i + 1:
                runs[i] = (j, x_end - x_start)
                found = True
                break
        if not found:
            raise ValueError(f"could not find the sampled shoulder at x={x_start}..{x_end}")
    return runs


@dataclass
class Sheet:
    """An SVG document in inches. Paths are grouped by stroke colour."""

    width: float
    height: float
    groups: dict[str, list[str]] = field(default_factory=dict)

    def add(self, path_d: str, part_id: str, color: str = CUT) -> None:
        self.groups.setdefault(color, []).append(f'    <path id="{part_id}" d="{path_d}"/>')

    def add_line(self, a: Point, b: Point, line_id: str, color: str = SCORE) -> None:
        self.add(f"M {a[0]:.4f} {a[1]:.4f} L {b[0]:.4f} {b[1]:.4f}", line_id, color)

    def render(self) -> str:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width:g}in" height="{self.height:g}in" '
            f'viewBox="0 0 {self.width:g} {self.height:g}">',
        ]
        for color, paths in self.groups.items():
            label = "cut" if color == CUT else "score" if color == SCORE else color.strip("#")
            lines.append(f'  <g id="{label}" fill="none" stroke="{color}" stroke-width="{STROKE_WIDTH}" '
                         f'stroke-linejoin="miter">')
            lines += paths
            lines.append("  </g>")
        lines.append("</svg>")
        return "\n".join(lines) + "\n"


def placement_transform(x0: float, y0: float, min_x: float, min_y: float, max_x: float, max_y: float,
                        rotated: bool) -> Transform:
    """Map panel coordinates (x along the part, y up) into sheet coordinates (x across,
    y down the sheet) with the part's bounding box at (x0, y0). Unrotated, the part
    lies as drawn with its length across the sheet; rotated, its length runs down
    the sheet."""
    if rotated:
        return lambda x, y: (x0 + (y - min_y), y0 + (x - min_x))
    return lambda x, y: (x0 + (x - min_x), y0 + (max_y - y))
