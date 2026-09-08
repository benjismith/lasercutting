"""Parametric drawer organizer.

A floorless box with finger-jointed corners. Every wall carries a grid of notches cut
down from its top edge. Column dividers (running front to back) drop into the front
and back walls with egg-crate joints: a notch up from the divider's bottom edge mates
with the notch down from the wall's top edge, and the divider passes right through the
wall so both its faces are held. Column dividers carry the same top-edge notch grid
along their length, so row dividers (running left to right) drop onto them and onto
the side walls the same way. A row divider may span several columns, crossing the
column dividers in between with the same joint.

Four flat triangular gussets lie on the drawer floor in the box's corners, tabbed
through the bottom edges of both walls they touch, to keep the glued box square.

Top edges undulate. The rule that keeps the joints modular: a piece passing through a
joint (a divider's end, or a row divider at a crossing) always dips to one fixed low
level there, while the receiving piece's wavy edge stands above it by up to the
swing. Dividers anchor low at their ends and crossings and wander between; walls
wander freely between the low level and the full height, meeting at whatever height
each corner was given. Slot floors sit at a fixed level below the low level, so every
ear keeps the same engagement wherever it goes.

Coordinates: X runs left to right across the drawer, Y front to back, Z up. The box's
outer footprint is [0, width] x [0, depth]; the front wall is at y=0.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field

from lasercut.glowforge import bed_fit
from lasercut.panel import (Notch, Panel, PanelOutline, Placement, Profile, corner_gusset, even_tab_spans,
                            finger_notches, odd_finger_count)
from lasercut.wave import wander


@dataclass(frozen=True)
class RowDivider:
    """A row divider at row-grid index `row`, spanning from boundary `start` to
    boundary `end`. Boundaries are numbered left to right: 0 is the left wall,
    1..K are the column dividers in order, K+1 is the right wall. A divider whose
    span covers more than one column crosses the column dividers in between."""

    start: int
    end: int
    row: int


@dataclass
class OrganizerConfig:
    drawer_width: float = 29.75
    drawer_depth: float = 20.25
    drawer_height: float = 6.0
    clearance: float = 1 / 16       # gap between the box and each drawer wall
    height: float = 4.5             # wall and divider height at the crests
    thickness: float = 0.25         # measured stock thickness
    column_pitch: float = 1.5       # target spacing of column-divider positions along the width
    row_pitch: float = 2.5          # target spacing of row-divider positions along the depth
    notch_depth: float | None = None  # how far a divider's ear engages a slot; default height/2
    wave_swing: float = 0.0         # rise and fall of the top edges; 0 for straight tops
    wave_length: float = 10.0       # typical distance between crests
    wave_seed: int = 1              # change to reshuffle every panel's highs and lows
    finger_width: float = 0.5       # target finger width at the corners
    edge_margin: float = 0.5        # solid material kept between a grid notch and a corner joint
    gusset_leg: float = 3.0         # leg length of the corner gussets; 0 for none
    gusset_tabs: int = 2            # tabs along each gusset leg
    columns: list[int] = field(default_factory=list)       # column-grid indices holding a divider
    rows: list[RowDivider] = field(default_factory=list)


def snap_pitch(length: float, target_pitch: float, thickness: float) -> float:
    """The pitch nearest `target_pitch` such that an even number of pitches spans the
    wall's length minus one stock thickness. With that, a cell against a wall and a
    cell between two dividers are the same width for the same number of grid steps:
    every cell is steps * pitch - thickness."""
    span = length - thickness
    n = max(2, 2 * round(span / target_pitch / 2))
    return span / n


def grid(length: float, pitch: float, thickness: float, clear: float) -> dict[int, float]:
    """Notch centres along a wall of outer `length`, symmetric about its middle, every
    `pitch`, with nothing closer than `clear` to the inner face of the wall at either end."""
    center = length / 2
    inner = thickness + clear + thickness / 2
    k_max = int(math.floor((center - inner) / pitch + 1e-9))
    if k_max < 0:
        return {}
    return {k: center + k * pitch for k in range(-k_max, k_max + 1)}


class Design:
    def __init__(self, cfg: OrganizerConfig):
        self.cfg = cfg
        t = cfg.thickness
        self.width = cfg.drawer_width - 2 * cfg.clearance
        self.depth = cfg.drawer_depth - 2 * cfg.clearance
        self.height = cfg.height
        engagement = cfg.height / 2 if cfg.notch_depth is None else cfg.notch_depth
        self.ear_top = cfg.height - cfg.wave_swing          # low level every passing piece dips to
        self.slot_floor = self.ear_top - engagement          # fixed level of every receiving notch floor
        self.top_notch_depth = cfg.height - self.slot_floor  # measured from the nominal top
        self.bottom_notch_depth = self.slot_floor            # a divider's bottom notch reaches this high
        clear = max(cfg.edge_margin, cfg.gusset_leg)  # dividers must miss the gussets too
        self.column_pitch = snap_pitch(self.width, cfg.column_pitch, t)
        self.row_pitch = snap_pitch(self.depth, cfg.row_pitch, t)
        self.column_grid = grid(self.width, self.column_pitch, t, clear)
        self.row_grid = grid(self.depth, self.row_pitch, t, clear)
        self.gusset_tab_spans = even_tab_spans(cfg.gusset_leg, cfg.gusset_tabs) if cfg.gusset_leg > 0 else []
        self.finger_count = odd_finger_count(cfg.height, cfg.finger_width)
        self._validate()
        self.panels = self._build_panels()

    # --- layout bookkeeping -------------------------------------------------

    @property
    def column_count(self) -> int:
        """Number of columns (spaces), one more than the number of column dividers."""
        return len(self.cfg.columns) + 1

    def boundary_faces(self, i: int) -> tuple[float, float]:
        """X extent (left face, right face) of boundary `i`: the left wall, a column
        divider, or the right wall."""
        t = self.cfg.thickness
        k = len(self.cfg.columns)
        if i == 0:
            return (0.0, t)
        if i == k + 1:
            return (self.width - t, self.width)
        x = self.column_grid[self.cfg.columns[i - 1]]
        return (x - t / 2, x + t / 2)

    def _validate(self) -> None:
        cfg = self.cfg
        if cfg.wave_swing < 0 or cfg.wave_swing >= self.height:
            raise ValueError("wave_swing must be between 0 and the wall height")
        if not (0 < self.slot_floor < self.ear_top):
            raise ValueError("notch_depth plus wave_swing must leave some wall below the slots")
        if not self.column_grid or not self.row_grid:
            raise ValueError("grid pitch leaves no room for any notch")
        if cfg.gusset_leg < 0 or (cfg.gusset_leg > 0 and cfg.gusset_tabs < 1):
            raise ValueError("gusset_leg must be 0 or positive with at least one tab")
        if cfg.gusset_leg > 0 and 2 * cfg.thickness + 2 * cfg.gusset_leg > min(self.width, self.depth):
            raise ValueError("gussets would overlap each other")
        if list(cfg.columns) != sorted(set(cfg.columns)):
            raise ValueError("columns must be strictly ascending grid indices")
        for k in cfg.columns:
            if k not in self.column_grid:
                raise ValueError(f"column index {k} is outside the grid {min(self.column_grid)}..{max(self.column_grid)}")
        last = len(cfg.columns) + 1
        occupied: Counter[tuple[int, int]] = Counter()
        for r in cfg.rows:
            if not (0 <= r.start < r.end <= last):
                raise ValueError(f"row divider {r} must span boundaries within 0..{last}")
            if r.row not in self.row_grid:
                raise ValueError(f"row index {r.row} is outside the grid {min(self.row_grid)}..{max(self.row_grid)}")
            for b in range(r.start, r.end + 1):
                occupied[(b, r.row)] += 1
        clashes = [key for key, n in occupied.items() if n > 1]
        if clashes:
            raise ValueError(
                "two row dividers meet at the same notch (boundary, row) "
                f"{clashes}; make them one divider spanning both columns"
            )

    # --- panels -------------------------------------------------------------

    def _build_panels(self) -> list[Panel]:
        cfg = self.cfg
        t, W, D, H = cfg.thickness, self.width, self.depth, self.height
        top, bottom = self.top_notch_depth, self.bottom_notch_depth
        column_notches = [Notch.centered(x, t, top) for x in self.column_grid.values()]
        row_notches = [Notch.centered(y, t, top) for y in self.row_grid.values()]
        long_fingers = finger_notches(H, t, self.finger_count, notch_first=False)
        short_fingers = finger_notches(H, t, self.finger_count, notch_first=True)

        def long_wall(name: str) -> PanelOutline:
            return PanelOutline(W, H, left=long_fingers, right=long_fingers, top=column_notches,
                                bottom=self._gusset_notches(W), top_profile=self._wave(name, W, "wall"))

        def short_wall(name: str) -> PanelOutline:
            return PanelOutline(D, H, left=short_fingers, right=short_fingers, top=row_notches,
                                bottom=self._gusset_notches(D), top_profile=self._wave(name, D, "wall"))

        panels = [
            Panel("wall_front", long_wall("wall_front"), t, Placement.upright_along_x((0.0, 0.0, 0.0)), "wall"),
            Panel("wall_back", long_wall("wall_back"), t, Placement.upright_along_x((0.0, D - t, 0.0)), "wall"),
            Panel("wall_left", short_wall("wall_left"), t, Placement.upright_along_y((0.0, 0.0, 0.0)), "wall"),
            Panel("wall_right", short_wall("wall_right"), t, Placement.upright_along_y((W - t, 0.0, 0.0)), "wall"),
        ]

        for i, k in enumerate(cfg.columns, start=1):
            x = self.column_grid[k]
            name = f"column_{i}"
            column = PanelOutline(D, H, bottom=[Notch(0.0, t, bottom), Notch(D - t, D, bottom)],
                                  top=row_notches, top_profile=self._wave(name, D, "column"))
            panels.append(Panel(name, column, t, Placement.upright_along_y((x - t / 2, 0.0, 0.0)), "column"))

        for i, r in enumerate(cfg.rows, start=1):
            y = self.row_grid[r.row]
            x0 = self.boundary_faces(r.start)[0]
            x1 = self.boundary_faces(r.end)[1]
            notches = [Notch(a - x0, b - x0, bottom)
                       for a, b in (self.boundary_faces(j) for j in range(r.start, r.end + 1))]
            crossings = [(n.start + n.end) / 2 for n in notches[1:-1]]
            name = f"row_{i}"
            outline = PanelOutline(x1 - x0, H, bottom=notches,
                                   top_profile=self._wave(name, x1 - x0, "row", crossings))
            panels.append(Panel(name, outline, t, Placement.upright_along_x((x0, y - t / 2, 0.0)), "row"))

        if cfg.gusset_leg > 0:
            gusset = corner_gusset(cfg.gusset_leg, t, self.gusset_tab_spans)
            corners = {
                "gusset_front_left": ((t, t, 0.0), 1.0, 1.0),
                "gusset_front_right": ((W - t, t, 0.0), -1.0, 1.0),
                "gusset_back_left": ((t, D - t, 0.0), 1.0, -1.0),
                "gusset_back_right": ((W - t, D - t, 0.0), -1.0, -1.0),
            }
            for name, (origin, sx, sy) in corners.items():
                panels.append(Panel(name, gusset, t, Placement.flat(origin, sx, sy), "gusset"))
        return panels

    def corner_height(self, corner: str) -> float:
        """Height of the walls where they meet at a corner ('front_left' etc.), the
        same for both walls. Kept in the upper part of the range so the top corner
        finger is never a sliver."""
        cfg = self.cfg
        rng = random.Random(f"{cfg.wave_seed}:corner:{corner}")
        return rng.uniform(self.ear_top + 0.4 * cfg.wave_swing, self.height)

    WALL_CORNERS = {
        "wall_front": ("front_left", "front_right"),
        "wall_back": ("back_left", "back_right"),
        "wall_left": ("front_left", "back_left"),
        "wall_right": ("front_right", "back_right"),
    }

    def _wave(self, name: str, length: float, kind: str, anchors: list[float] = ()) -> Profile | None:
        """Top-edge profile for one panel, or None for a straight top. Walls are
        pinned only at their corners; dividers are pinned to the ear level at their
        ends and crossings. Everything else is left to `wander`."""
        cfg = self.cfg
        if cfg.wave_swing <= 0:
            return None
        rng = random.Random(f"{cfg.wave_seed}:{name}")
        if kind == "wall":
            a, b = self.WALL_CORNERS[name]
            pins = [(0.0, self.corner_height(a)), (length, self.corner_height(b))]
        else:
            pins = [(0.0, self.ear_top), (length, self.ear_top)] + [(x, self.ear_top) for x in anchors]
        return wander(length, pins, self.ear_top, self.height, cfg.wave_length, rng)

    def _gusset_notches(self, wall_length: float) -> list[Notch]:
        """Bottom-edge notches at both ends of a wall for the gusset tabs. Spans are
        measured from the wall's inner corner, so add the neighbouring wall's thickness."""
        t = self.cfg.thickness
        notches = []
        for a, b in self.gusset_tab_spans:
            notches.append(Notch(t + a, t + b, t))
            notches.append(Notch(wall_length - t - b, wall_length - t - a, t))
        return notches

    # --- reporting ----------------------------------------------------------

    def cells(self) -> list[tuple[int, float, list[float]]]:
        """Per column (1-based): its clear width and the front-to-back depth of each cell."""
        t, D = self.cfg.thickness, self.depth
        out = []
        for c in range(self.column_count):
            x0 = self.boundary_faces(c)[1]
            x1 = self.boundary_faces(c + 1)[0]
            ys = sorted(self.row_grid[r.row] for r in self.cfg.rows if r.start <= c < r.end)
            edges = [t] + [e for y in ys for e in (y - t / 2, y + t / 2)] + [D - t]
            depths = [edges[i + 1] - edges[i] for i in range(0, len(edges), 2)]
            out.append((c + 1, x1 - x0, depths))
        return out

    def cut_list(self) -> list[tuple[str, float, float, int, int, str]]:
        """(label, length, height, count, distinct shapes, bed fit), panels of the
        same kind and size grouped. Wavy tops make otherwise identical panels
        distinct shapes, hence the separate count."""
        groups: dict[tuple[str, float, float], list[tuple]] = {}
        labels = {"wall": "wall", "column": "column divider", "row": "row divider", "gusset": "corner gusset"}
        for p in self.panels:
            w, h = p.outline.size()
            key = (labels[p.kind], round(w, 4), round(h, 4))
            shape = tuple((round(x, 5), round(y, 5)) for x, y in p.outline.points())
            groups.setdefault(key, []).append(shape)
        return [(label, L, H, len(shapes), len(set(shapes)), bed_fit(L, H))
                for (label, L, H), shapes in groups.items()]

    def describe(self) -> str:
        cfg = self.cfg
        fmt = lambda v: f"{v:g}"
        lines = [
            f"Drawer organizer: outer {fmt(self.width)} x {fmt(self.depth)} x {fmt(self.height)} in, "
            f"{fmt(cfg.thickness)} in stock, {fmt(cfg.clearance)} in clearance per side",
            f"Column grid: {len(self.column_grid)} positions at {fmt(self.column_pitch)} in pitch "
            f"(x = {fmt(min(self.column_grid.values()))} .. {fmt(max(self.column_grid.values()))}); "
            f"a cell n steps wide is {fmt(self.column_pitch)}n - {fmt(cfg.thickness)}",
            f"Row grid:    {len(self.row_grid)} positions at {fmt(self.row_pitch)} in pitch "
            f"(y = {fmt(min(self.row_grid.values()))} .. {fmt(max(self.row_grid.values()))})",
            f"Egg-crate slots: floors {fmt(self.slot_floor)} in above the drawer bottom, "
            f"{fmt(self.ear_top - self.slot_floor)} in of ear engagement; divider bottom notches {fmt(self.bottom_notch_depth)} in",
            (f"Wavy tops: {fmt(cfg.wave_swing)} in swing between {fmt(self.ear_top)} and {fmt(self.height)} in, "
             f"crests about {fmt(cfg.wave_length)} in apart, seed {cfg.wave_seed}"
             if cfg.wave_swing > 0 else "Tops: straight"),
            f"Corner joints: {self.finger_count} fingers of {fmt(self.height / self.finger_count)} in",
            (f"Corner gussets: {fmt(cfg.gusset_leg)} in legs, {cfg.gusset_tabs} tabs per leg"
             if cfg.gusset_leg > 0 else "Corner gussets: none"),
            "",
            "Cut list (length x height, in):",
        ]
        for label, L, H, n, shapes, fit in self.cut_list():
            note = f"  ({shapes} distinct shapes)" if shapes > 1 else ""
            lines.append(f"  {n} x {label:<15} {fmt(L):>8} x {fmt(H):<5}  {fit}{note}")
        lines += ["", "Columns left to right, cells front to back:"]
        for c, w, depths in self.cells():
            lines.append(f"  column {c}: {fmt(w)} in wide, cells " + " / ".join(fmt(d) for d in depths) + " in deep")
        return "\n".join(lines)
