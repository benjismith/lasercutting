"""Generate Glowforge cut files for the drawer organizer.

Runs in plain Python (no Blender). From the repo root:

    uv run python projects/drawer-organizer/cutfiles.py --layout three-plus-two --kerf 0.008

Stock defaults come from config.STOCK (the sheets on hand); the options override them.

Writes into --out (default out/cut):
    <layout>.svg        every part nested on one sheet, in inches, ready for the Glowforge
    kerf-coupon.svg     a test piece with three slots at three kerf settings
    <layout>-nesting.txt  where each part sits, and the sheet length needed

Options:
    --layout NAME        a layout from config.LAYOUTS (default config.CONFIG)
    --kerf IN            laser kerf; parts are offset outward by half of it (default from config.STOCK)
    --sheet-width IN     material width (at most 20, the Pro passthrough limit)
    --edge-margin IN     material left clear along each long edge (default from config.STOCK)
    --cut-width IN       most the laser can cut across the sheet (default 19.5, the bed width)
    --sheet-length IN    material length; parts are split across as many sheets as needed
                         (pass 0 for one sheet of any length)
    --end-margin IN      material left clear at each end of the sheet (default from config.STOCK)
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
    ap.add_argument("--kerf", type=float, default=config.STOCK.get("kerf", glowforge.KERF))
    ap.add_argument("--sheet-width", type=float, default=config.STOCK["width"])
    ap.add_argument("--cut-width", type=float, default=glowforge.BED_LONG)
    ap.add_argument("--edge-margin", type=float, default=config.STOCK.get("edge_margin", 0.0))
    ap.add_argument("--sheet-length", type=float, default=config.STOCK["length"])
    ap.add_argument("--end-margin", type=float, default=config.STOCK.get("end_margin", 0.0))
    ap.add_argument("--gap", type=float, default=0.1)
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "cut"))
    return ap.parse_args()


def nest_design(d: design.Design, band: float, gap: float, kerf: float,
                sheet_length: float | None, end_margin: float = 0.0):
    """Nest all panels; returns the nestings (one per sheet) and the panels by name.

    `band` is the width the parts may occupy and `sheet_length - 2 * end_margin` the
    length. The nester insets everything by one `gap` from its own edges, so both are
    passed with a gap added at each side to cancel that; the margins then come out
    exactly as asked.
    """
    by_name = {p.name: p for p in d.panels}
    parts = []
    for p in d.panels:
        w, h = p.outline.size()
        parts.append(Part(p.name, w + kerf, h + kerf))
    usable = None if sheet_length is None else sheet_length - 2 * end_margin + 2 * gap
    sheets = []
    remaining = parts
    while remaining:
        result = nest(remaining, band + 2 * gap, gap, tries=2000, max_length=usable)
        if not result.placed:
            raise SystemExit("a part does not fit on the sheet at all")
        sheets.append(result)
        remaining = result.leftover
    return sheets, by_name


def occupied(nesting, gap: float) -> tuple[float, float]:
    """Width and length the placed parts actually span, net of the nester's inset."""
    return (max(pl.x + pl.width for pl in nesting.placed) - gap, nesting.length - gap)


def write_sheet(path: str, nesting, by_name, sheet_width: float, band: float,
                kerf: float, gap: float, fixed_length: float | None,
                edge_margin: float = 0.0, end_margin: float = 0.0) -> float:
    """Write one sheet. Parts sit `end_margin` from the near end and are centred
    across the band, so whatever the packing leaves over is split evenly side to side.
    They are not centred along the length: keeping them at one end leaves the rest of
    the sheet as a single usable offcut."""
    used_w, used_l = occupied(nesting, gap)
    length = fixed_length if fixed_length is not None else used_l + 2 * end_margin
    x0 = edge_margin - gap + (band - used_w) / 2      # centre the packed band
    y0 = end_margin - gap
    sheet = Sheet(sheet_width, length)
    for pl in nesting.placed:
        panel = by_name[pl.name]
        pts = panel.outline.points()
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        # the nested box includes the kerf allowance; centre the true outline in it
        place = placement_transform(x0 + pl.x + kerf / 2, y0 + pl.y + kerf / 2,
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
    if args.sheet_width > glowforge.PASSTHROUGH_WIDTH + 1e-9:
        raise SystemExit(f"sheet width {args.sheet_width:g} exceeds the passthrough limit of {glowforge.PASSTHROUGH_WIDTH:g} in")
    band = min(args.sheet_width - 2 * args.edge_margin, args.cut_width)
    if band <= 0:
        raise SystemExit("the edge margins leave no width for parts")
    if args.sheet_length is not None and args.sheet_length <= 0:
        args.sheet_length = None
    cfg = config.LAYOUTS[args.layout] if args.layout else config.CONFIG
    name = args.layout or next(k for k, v in config.LAYOUTS.items() if v is cfg)
    d = design.Design(cfg)
    os.makedirs(args.out, exist_ok=True)

    sheets, by_name = nest_design(d, band, args.gap, args.kerf, args.sheet_length, args.end_margin)
    report = [f"Layout {name}: {len(d.panels)} parts, kerf {args.kerf:g} in, gap {args.gap:g} in, "
              f"sheet {args.sheet_width:g} x {args.sheet_length:g} in; parts kept "
              f"{args.edge_margin:g} in from the long edges and {args.end_margin:g} in from the ends "
              f"(a {band:g} in band)"]
    area = sum(p.outline.area() for p in d.panels)
    total_length = 0.0
    for i, nesting in enumerate(sheets, start=1):
        suffix = "" if len(sheets) == 1 else f"-sheet{i}"
        path = os.path.join(args.out, f"{name}{suffix}.svg")
        length = write_sheet(path, nesting, by_name, args.sheet_width, band,
                             args.kerf, args.gap, args.sheet_length, args.edge_margin, args.end_margin)
        total_length += length
        used_w, used_l = occupied(nesting, args.gap)
        side = args.edge_margin + (band - used_w) / 2
        report.append(f"\n{os.path.relpath(path, ROOT)}: {args.sheet_width:g} x {length:.2f} in; "
                      f"parts span {side:.2f} to {args.sheet_width - side:.2f} across "
                      f"({side:.2f} in clear on each side) and {args.end_margin:.2f} to "
                      f"{args.end_margin + used_l:.2f} along ({length - args.end_margin - used_l:.2f} in "
                      f"clear at the far end)")
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
