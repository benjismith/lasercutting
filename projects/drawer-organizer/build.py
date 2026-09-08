"""Build the drawer organizer as a Blender scene.

Headless, from the repo root:

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python projects/drawer-organizer/build.py -- \
        --blend out/organizer.blend --render out/renders

Or open this file in Blender's Text Editor and press Run Script to build the scene in
the open session (re-running picks up edits to design.py and config.py).

Options after the `--`:
    --blend PATH     save the scene as a .blend file
    --render DIR     write iso.png, top.png and front.png previews into DIR
    --views LIST     comma-separated subset of iso,top,front,corner (default iso,top,front)
    --explode IN     lift column dividers by IN inches, row dividers by twice that, and
                     drop the gussets by IN
    --size WxH       render size in pixels (default 1800x1200)
    --region X0,Y0,X1,Y1   frame the renders on this part of the floor plan only
    --hide KINDS     comma-separated panel kinds to leave out of renders (wall,column,row,gusset)
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

import bpy


def _here() -> str:
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:  # running from Blender's Text Editor
        return os.path.dirname(bpy.path.abspath(bpy.context.space_data.text.filepath))


HERE = _here()
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import lasercut.panel, lasercut.glowforge, lasercut.blender  # noqa: E402,E401
import design, config  # noqa: E402,E401
for m in (lasercut.panel, lasercut.glowforge, lasercut.blender, design, config):
    importlib.reload(m)
lb = lasercut.blender

COLORS = {
    "wall": (0.88, 0.76, 0.55),
    "column": (0.78, 0.55, 0.34),
    "row": (0.52, 0.64, 0.42),
    "gusset": (0.62, 0.42, 0.40),
}
LABELS = {"wall": "Walls", "column": "Column dividers", "row": "Row dividers", "gusset": "Corner gussets"}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend")
    ap.add_argument("--render")
    ap.add_argument("--views", default="iso,top,front")
    ap.add_argument("--explode", type=float, default=0.0)
    ap.add_argument("--size", default="1800x1200")
    ap.add_argument("--region")
    ap.add_argument("--hide", default="")
    return ap.parse_args(argv)


def build(explode: float = 0.0) -> tuple[design.Design, list[bpy.types.Object]]:
    d = design.Design(config.CONFIG)
    cols = {kind: lb.collection(label) for kind, label in LABELS.items()}
    mats = {kind: lb.material(kind, rgb) for kind, rgb in COLORS.items()}
    lift = {"wall": 0.0, "column": explode, "row": 2 * explode, "gusset": -explode}
    objects = [lb.panel_object(p, cols[p.kind], mats[p.kind], (0.0, 0.0, lift[p.kind])) for p in d.panels]
    c = d.cfg.clearance
    lb.wire_box("drawer_interior", lb.collection("Reference"),
                (-c, -c, 0.0), (d.width + c, d.depth + c, d.cfg.drawer_height))
    return d, objects


def main() -> None:
    args = parse_args()
    scene = lb.reset_scene()
    d, objects = build(args.explode)
    print(d.describe())

    if args.blend:
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"saved {args.blend}")

    if args.render:
        os.makedirs(args.render, exist_ok=True)
        size = tuple(int(v) for v in args.size.lower().split("x"))
        lb.setup_workbench(scene)
        hidden = {k for k in args.hide.split(",") if k}
        shown = [o for o, p in zip(objects, d.panels) if p.kind not in hidden]
        for o, p in zip(objects, d.panels):
            o.hide_render = p.kind in hidden
        points = lb.mesh_points(shown)
        if args.region:
            x0, y0, x1, y1 = (float(v) for v in args.region.split(","))
            points = [p for p in points if x0 <= p.x <= x1 and y0 <= p.y <= y1]
        for view in args.views.split(","):
            cam = lb.ortho_camera(f"cam_{view}", lb.VIEW_ROTATIONS[view], points, size)
            path = os.path.join(args.render, f"{view}.png")
            lb.render_png(scene, cam, path, size)
            print(f"rendered {path}")


if __name__ == "__main__":
    main()
