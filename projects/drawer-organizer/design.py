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

Tops: the front corners stand at full height from the corner to just before the first
slot, drop by an S-shaped shoulder to the interior level, and the walls run flat at
that level across the slotted region. The back edge of the whole box sits lower: the
back wall is flat at `back_level`, and the side walls and column dividers step down to
it through the same shoulder inverted, just past the last row slot, so everything
behind the last row position is at the back level. Dividers are otherwise flat at the interior level, so every ear is flush
with the edge it passes through. Slot floors sit a fixed engagement below the local
top, so the back wall's slots are lower than the rest.

Coordinates: X runs left to right across the drawer, Y front to back, Z up. The box's
outer footprint is [0, width] x [0, depth]; the front wall is at y=0.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from lasercut.glowforge import bed_fit
from lasercut.panel import (Notch, Panel, PanelOutline, Placement, SteppedEnds, corner_gusset,
                            even_tab_spans, finger_notches, odd_finger_count)


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
    height: float = 4.5             # wall height at the raised corners
    thickness: float = 0.25         # measured stock thickness
    column_steps: int = 18          # grid steps across the width (even); equal columns need a divisor of this
    row_steps: int = 8              # grid steps along the depth (even)
    notch_depth: float | None = None  # how far a divider's ear engages a slot; default half the interior level
    corner_rise: float = 0.5        # how much higher the front corners stand than the interior level
    back_level: float | None = None  # height of the whole back edge; None for raised back corners like the front
    step_gap: float = 0.5           # flat edge kept between a step and the nearest slot
    corner_plateau_min: float = 1.5  # least full-height edge kept at a corner before the shoulder begins
    corner_curve: str = "ease"      # shoulder shape: 'ease' (cubic S over step_run), 'ogee' (two quarter circles) or 'round'
    step_run: float = 2.0           # length of an 'ease' shoulder; circular shoulders are as long as the step is tall
    finger_width: float = 0.5       # target finger width at the corners
    edge_margin: float = 0.5        # solid material kept between a grid notch and a corner joint
    gusset_leg: float = 3.0         # leg length of the corner gussets; 0 for none
    gusset_tabs: int = 2            # tabs along each gusset leg
    columns: list[int] = field(default_factory=list)       # column-grid indices holding a divider
    rows: list[RowDivider] = field(default_factory=list)


def step_pitch(length: float, steps: int, thickness: float) -> float:
    """The grid pitch when the wall's length minus one stock thickness is divided into
    `steps` equal steps. With an even count, a cell against a wall and a cell between
    two dividers are the same width for the same number of steps: every cell is
    steps * pitch - thickness, and m equal columns need `steps` divisible by m."""
    if steps < 2 or steps % 2:
        raise ValueError("grid steps must be an even number of at least 2")
    return (length - thickness) / steps


def grid(length: float, pitch: float, thickness: float, clear: float) -> dict[int, float]:
    """Notch centres along a wall of outer `length`, symmetric about its middle, every
    `pitch`, with nothing closer than `clear` to the inner face of the wall at either end."""
    center = length / 2
    inner = thickness + clear + thickness / 2
    k_max = int(math.floor((center - inner) / pitch + 1e-9))
    if k_max < 0:
        return {}
    return {k: center + k * pitch for k in range(-k_max, k_max + 1)}


class _Flat:
    """A level top edge below the panel's nominal height."""

    def __init__(self, level: float):
        self.level = self.top = level

    def __call__(self, x: float) -> float:
        return self.level

    def samples(self, lo: float, hi: float) -> list[float]:
        return [lo, hi]


class Design:
    def __init__(self, cfg: OrganizerConfig):
        self.cfg = cfg
        t = cfg.thickness
        self.width = cfg.drawer_width - 2 * cfg.clearance
        self.depth = cfg.drawer_depth - 2 * cfg.clearance
        self.height = cfg.height                             # at the raised corners
        self.level = cfg.height - cfg.corner_rise            # interior top level: walls between corners, all dividers
        self.back_level = self.level if cfg.back_level is None else cfg.back_level   # top of the back wall
        self.back_step = self.back_level - self.level        # how the side walls and column dividers reach it
        engagement = self.level / 2 if cfg.notch_depth is None else cfg.notch_depth
        self.engagement = engagement
        self.slot_floor = self.level - engagement            # receiving notch floors at the interior level
        self.back_slot_floor = self.back_level - engagement  # receiving notch floors in the back wall
        self.wall_slot_depth = self.height - self.slot_floor  # front and side wall slots, from the nominal height
        self.back_wall_slot_depth = self.height - self.back_slot_floor
        self.divider_slot_depth = self.level - self.slot_floor
        self.bottom_notch_depth = self.slot_floor            # a divider's bottom notch reaches this high
        self.back_bottom_notch_depth = self.back_slot_floor  # at a column divider's back end
        # Slots must miss the gussets and leave room for the corner plateau, a
        # shoulder and its gap between the corner joint and the first slot.
        shoulder = max(self.shoulder_width(cfg.corner_rise), self.shoulder_width(self.back_step))
        clear = max(cfg.edge_margin, cfg.gusset_leg, cfg.corner_plateau_min + shoulder + cfg.step_gap)
        self.column_pitch = step_pitch(self.width, cfg.column_steps, t)
        self.row_pitch = step_pitch(self.depth, cfg.row_steps, t)
        self.column_grid = grid(self.width, self.column_pitch, t, clear)
        self.row_grid = grid(self.depth, self.row_pitch, t, clear)
        self.gusset_tab_spans = even_tab_spans(cfg.gusset_leg, cfg.gusset_tabs) if cfg.gusset_leg > 0 else []
        # Plateau lengths: each raised or lowered band runs from the wall's end to a
        # step that finishes `step_gap` short of the nearest slot.
        gap = cfg.step_gap
        rise_w = self.shoulder_width(cfg.corner_rise)
        col_first = min(self.column_grid.values()) - t / 2
        col_last = max(self.column_grid.values()) + t / 2
        row_first = min(self.row_grid.values()) - t / 2
        row_last = max(self.row_grid.values()) + t / 2
        self.front_wall_plateau = (col_first - gap - rise_w, self.width - col_last - gap - rise_w)
        self.side_front_plateau = row_first - gap - rise_w
        back_w = self.shoulder_width(self.back_step) if cfg.back_level is not None else rise_w
        self.back_plateau = self.depth - row_last - gap - back_w
        self.finger_count = odd_finger_count(cfg.height, cfg.finger_width)
        self._validate()
        self.panels = self._build_panels()

    # --- layout bookkeeping -------------------------------------------------

    def shoulder_width(self, step: float) -> float:
        """Horizontal length of the shoulder that makes a step of the given size."""
        if step == 0:
            return 0.0
        return self.cfg.step_run if self.cfg.corner_curve == "ease" else abs(step)

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
        if not (0 <= cfg.corner_rise < self.height):
            raise ValueError("corner_rise must be between 0 and the wall height")
        if not (0 < self.slot_floor < self.level):
            raise ValueError("notch_depth must leave some wall below the slots")
        if cfg.back_level is not None and not (0 < self.back_slot_floor < self.back_level <= self.height):
            raise ValueError("back_level must be between the slot engagement and the wall height")
        for plateau in (*self.front_wall_plateau, self.side_front_plateau, self.back_plateau):
            if plateau < cfg.thickness:
                raise ValueError("a step would run into a corner joint; increase edge_margin or reduce step_gap")
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

    def _top(self, length: float, start_step: float, end_step: float,
             start_plateau: float, end_plateau: float) -> SteppedEnds | None:
        """Top-edge profile with the given steps and plateaus, or None if both steps are zero."""
        if start_step == 0 and end_step == 0:
            return None
        return SteppedEnds(length, self.level, start_step, end_step, start_plateau,
                           self.cfg.corner_curve, end_plateau=end_plateau, run=self.cfg.step_run)

    def _front_wall_top(self, length: float) -> SteppedEnds | None:
        rise = self.cfg.corner_rise
        return self._top(length, rise, rise, *self.front_wall_plateau)

    def _side_wall_top(self, length: float) -> SteppedEnds | None:
        rise = self.cfg.corner_rise
        back = rise if self.cfg.back_level is None else self.back_step
        return self._top(length, rise, back, self.side_front_plateau, self.back_plateau)

    def _column_top(self, length: float) -> SteppedEnds | None:
        return self._top(length, 0.0, self.back_step, 0.0, self.back_plateau)

    def _build_panels(self) -> list[Panel]:
        cfg = self.cfg
        t, W, D, H, level = cfg.thickness, self.width, self.depth, self.height, self.level
        bottom, back_bottom = self.bottom_notch_depth, self.back_bottom_notch_depth
        front_slots = [Notch.centered(x, t, self.wall_slot_depth) for x in self.column_grid.values()]
        back_slots = [Notch.centered(x, t, self.back_wall_slot_depth) for x in self.column_grid.values()]
        row_slots_in_wall = [Notch.centered(y, t, self.wall_slot_depth) for y in self.row_grid.values()]
        row_slots_in_divider = [Notch.centered(y, t, self.divider_slot_depth) for y in self.row_grid.values()]
        long_fingers = finger_notches(H, t, self.finger_count, notch_first=False)
        short_fingers = finger_notches(H, t, self.finger_count, notch_first=True)

        front_wall = PanelOutline(W, H, left=long_fingers, right=long_fingers, top=front_slots,
                                  bottom=self._gusset_notches(W), top_profile=self._front_wall_top(W))
        if cfg.back_level is None:
            back_wall = front_wall
        else:
            back_wall = PanelOutline(W, H, left=long_fingers, right=long_fingers, top=back_slots,
                                     bottom=self._gusset_notches(W), top_profile=_Flat(self.back_level))
        side_wall = PanelOutline(D, H, left=short_fingers, right=short_fingers, top=row_slots_in_wall,
                                 bottom=self._gusset_notches(D), top_profile=self._side_wall_top(D))
        panels = [
            Panel("wall_front", front_wall, t, Placement.upright_along_x((0.0, 0.0, 0.0)), "wall"),
            Panel("wall_back", back_wall, t, Placement.upright_along_x((0.0, D - t, 0.0)), "wall"),
            Panel("wall_left", side_wall, t, Placement.upright_along_y((0.0, 0.0, 0.0)), "wall"),
            Panel("wall_right", side_wall, t, Placement.upright_along_y((W - t, 0.0, 0.0)), "wall"),
        ]

        column = PanelOutline(D, level, bottom=[Notch(0.0, t, bottom), Notch(D - t, D, back_bottom)],
                              top=row_slots_in_divider, top_profile=self._column_top(D))
        for i, k in enumerate(cfg.columns, start=1):
            x = self.column_grid[k]
            panels.append(Panel(f"column_{i}", column, t, Placement.upright_along_y((x - t / 2, 0.0, 0.0)), "column"))

        for i, r in enumerate(cfg.rows, start=1):
            y = self.row_grid[r.row]
            x0 = self.boundary_faces(r.start)[0]
            x1 = self.boundary_faces(r.end)[1]
            notches = [Notch(a - x0, b - x0, bottom)
                       for a, b in (self.boundary_faces(j) for j in range(r.start, r.end + 1))]
            outline = PanelOutline(x1 - x0, level, bottom=notches)
            panels.append(Panel(f"row_{i}", outline, t, Placement.upright_along_x((x0, y - t / 2, 0.0)), "row"))

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
        same kind and size grouped."""
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
            f"Column grid: {cfg.column_steps} steps of {fmt(self.column_pitch)} in across the width, "
            f"{len(self.column_grid)} usable positions (x = {fmt(min(self.column_grid.values()))} .. "
            f"{fmt(max(self.column_grid.values()))}); a cell n steps wide is {fmt(self.column_pitch)}n - {fmt(cfg.thickness)}",
            f"Row grid:    {cfg.row_steps} steps of {fmt(self.row_pitch)} in along the depth, "
            f"{len(self.row_grid)} usable positions (y = {fmt(min(self.row_grid.values()))} .. "
            f"{fmt(max(self.row_grid.values()))})",
            f"Tops: interior level {fmt(self.level)} in; front corners {fmt(cfg.corner_rise)} in higher, "
            f"stepping down ({cfg.corner_curve}, {fmt(self.shoulder_width(cfg.corner_rise))} in long) "
            f"{fmt(cfg.step_gap)} in before the first slot "
            f"(raised bands {fmt(self.front_wall_plateau[0])} in on the front wall, {fmt(self.side_front_plateau)} in on the sides)"
            + (f"; back edge at {fmt(self.back_level)} in over the last {fmt(self.back_plateau)} in, "
               f"stepping down {fmt(cfg.step_gap)} in past the last row slot"
               if cfg.back_level is not None else "; back corners like the front"),
            f"Egg-crate slots: {fmt(self.engagement)} in of ear engagement everywhere; floors at "
            f"{fmt(self.slot_floor)} in (back wall {fmt(self.back_slot_floor)} in) above the drawer bottom",
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
