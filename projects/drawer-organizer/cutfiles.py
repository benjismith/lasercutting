"""Generate Glowforge cut files for the drawer organizer.

Runs in plain Python (no Blender). From the repo root:

    uv run python projects/drawer-organizer/cutfiles.py --layout three-plus-two --kerf 0.008

Writes into --out (default out/cut):
    <layout>.svg        every part nested on one sheet, in inches, ready for the Glowforge
    kerf-coupon.svg     a test piece with three slots at three kerf settings
    <layout>-nesting.txt  where each part sits, and the sheet length needed

Options:
    --layout NAME        a layout from config.LAYOUTS (default config.CONFIG)
    --kerf IN            laser kerf; parts are offset outward by half of it (default 0.008)
    --sheet-width IN     material width (default 20, the most the Pro passthrough takes)
    --cut-width IN       cuttable width across the bed (default 19.5)
    --sheet-length IN    fixed material length; splits into several sheets (default: one sheet, any length)
    --gap IN             spacing between parts (default 0.1)
    --out DIR
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import config  # noqa: E402
import design  # noqa: E402
from lasercut import glowforge  # noqa: E402
from lasercut.nest import Part, nest  # noqa: E402
from lasercut.svg import CUT, SCORE, Sheet, part_path, placement_transform  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout")
    ap.add_argument("--kerf", type=float, default=glowforge.KERF)
    ap.add_argument("--sheet-width", type=float, default=20.0)
    ap.add_argument("--cut-width", type=float, default=glowforge.BED_LONG)
    ap.add_argument("--sheet-length", type=float)
    ap.add_argument("--gap", type=float, default=0.1)
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "cut"))
    return ap.parse_args()


def nest_design(d: design.Design, cut_width: float, gap: float, kerf: float,
                sheet_length: float | None):
    """Nest all panels; returns a list of (nesting, panels-by-name) per sheet."""
    by_name = {p.name: p for p in d.panels}
    parts = []
    for p in d.panels:
        w, h = p.outline.size()
        parts.append(Part(p.name, w + kerf, h + kerf))
    sheets = []
    remaining = parts
    while remaining:
        if sheet_length is None:
            result = nest(remaining, cut_width, gap, tries=2000)
            sheets.append(result)
            break
        # fixed length: pack what fits, biggest first, and carry the rest to another sheet
        result = None
        order = sorted(remaining, key=lambda p: -max(p.width, p.height))
        chosen = list(order)
        while chosen:
            try:
                result = nest(chosen, cut_width, gap, tries=2000, max_length=sheet_length)
                break
            except ValueError:
                chosen = chosen[:-1]
        if result is None:
            raise SystemExit("a part does not fit on the sheet at all")
        sheets.append(result)
        placed = {pl.name for pl in result.placed}
        remaining = [p for p in remaining if p.name not in placed]
    return sheets, by_name


def write_sheet(path: str, nesting, by_name, sheet_width: float, cut_width: float,
                kerf: float, gap: float, fixed_length: float | None) -> float:
    margin = (sheet_width - cut_width) / 2
    length = fixed_length if fixed_length is not None else nesting.length + 2 * margin
    sheet = Sheet(sheet_width, length)
    for pl in nesting.placed:
        panel = by_name[pl.name]
        pts = panel.outline.points()
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        # the nested box includes the kerf allowance; centre the true outline in it
        place = placement_transform(margin + pl.x + kerf / 2, margin + pl.y + kerf / 2,
                                    min(xs), min(ys), max(xs), max(ys), pl.rotated)
        sheet.add(part_path(panel, kerf, place), pl.name)
    with open(path, "w") as f:
        f.write(sheet.render())
    return length


def write_coupon(path: str, thickness: float, kerf: float) -> None:
    """A 4 x 1.5 in piece with three slots cut for kerf - 0.004, kerf and kerf + 0.004,
    marked with one, two and three score ticks. Whichever slot takes a scrap of the
    stock with the right friction tells you the kerf to use."""
    from lasercut.panel import Notch, Panel, PanelOutline, Placement
    settings = [kerf - 0.004, kerf, kerf + 0.004]
    width, height, depth = 4.0, 1.5, 0.75
    # draw each slot narrowed for its own kerf setting, then offset the whole part by
    # the nominal half-kerf like any other part; the difference is what we are testing
    slots = []
    for i, k in enumerate(settings):
        cx = 1.0 + i * 1.0
        slots.append(Notch.centered(cx, thickness - (k - kerf), depth))
    outline = PanelOutline(width, height, top=slots)
    panel = Panel("coupon", outline, thickness, Placement.upright_along_x((0.0, 0.0, 0.0)))
    sheet = Sheet(width + 0.5, height + 0.5)
    place = placement_transform(0.25, 0.25, 0.0, 0.0, width, height, False)
    sheet.add(part_path(panel, kerf, place), "coupon", CUT)
    for i in range(3):
        for tick in range(i + 1):
            x = 0.25 + 1.0 + i * 1.0 - 0.1 * i + 0.2 * tick
            sheet.add_line((x, 0.25 + height - 0.45), (x, 0.25 + height - 0.2), f"tick_{i}_{tick}", SCORE)
    with open(path, "w") as f:
        f.write(sheet.render())


def main() -> None:
    args = parse_args()
    cfg = config.LAYOUTS[args.layout] if args.layout else config.CONFIG
    name = args.layout or next(k for k, v in config.LAYOUTS.items() if v is cfg)
    d = design.Design(cfg)
    os.makedirs(args.out, exist_ok=True)

    sheets, by_name = nest_design(d, args.cut_width, args.gap, args.kerf, args.sheet_length)
    report = [f"Layout {name}: {len(d.panels)} parts, kerf {args.kerf:g} in, gap {args.gap:g} in, "
              f"sheet {args.sheet_width:g} in wide ({args.cut_width:g} in cuttable)"]
    area = sum(p.outline.area() for p in d.panels)
    total_length = 0.0
    for i, nesting in enumerate(sheets, start=1):
        suffix = "" if len(sheets) == 1 else f"-sheet{i}"
        path = os.path.join(args.out, f"{name}{suffix}.svg")
        length = write_sheet(path, nesting, by_name, args.sheet_width, args.cut_width,
                             args.kerf, args.gap, args.sheet_length)
        total_length += length
        report.append(f"\n{os.path.relpath(path, ROOT)}: {args.sheet_width:g} x {length:.2f} in"
                      + (f" (parts use {nesting.length:.2f} in of length)" if args.sheet_length else ""))
        for pl in sorted(nesting.placed, key=lambda q: (q.y, q.x)):
            report.append(f"  {pl.name:<20} at x={pl.x:6.2f} y={pl.y:6.2f}  "
                          f"{pl.width:5.2f} x {pl.height:5.2f}{'  rotated' if pl.rotated else ''}")
    used = area / (args.sheet_width * total_length)
    report.append(f"\nMaterial: {args.sheet_width:g} x {total_length:.2f} in total; parts cover {used:.0%} of it")
    report.append("Parts longer than 11 in need the passthrough; the Glowforge app will step the sheet through.")

    coupon = os.path.join(args.out, "kerf-coupon.svg")
    write_coupon(coupon, cfg.thickness, args.kerf)
    report.append(f"{os.path.relpath(coupon, ROOT)}: kerf test coupon for {cfg.thickness:g} in stock "
                  f"(slots at kerf {args.kerf - 0.004:g}, {args.kerf:g}, {args.kerf + 0.004:g}; one, two, three ticks)")

    text = "\n".join(report)
    with open(os.path.join(args.out, f"{name}-nesting.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
