"""Turn Panels into Blender objects and render quick previews.

Only import this inside Blender. Scenes are built in inches (one Blender unit is one
inch, and the UI is told so), matching the rest of the toolkit.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Euler, Quaternion, Vector

from lasercut.panel import Panel, Vec3


def reset_scene() -> bpy.types.Scene:
    """Start from an empty file and switch the UI to inches."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "IMPERIAL"
    scene.unit_settings.length_unit = "INCHES"
    scene.unit_settings.scale_length = 0.0254
    return scene


def collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def material(name: str, rgb: tuple[float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def panel_object(panel: Panel, col: bpy.types.Collection,
                 mat: bpy.types.Material | None = None,
                 offset: Vec3 = (0.0, 0.0, 0.0)) -> bpy.types.Object:
    """A solid prism: the panel outline extruded through the stock thickness."""
    pts = panel.outline.points()
    place = panel.placement
    bm = bmesh.new()
    lower = [bm.verts.new(Vector(place.to_world(x, y, 0.0)) + Vector(offset)) for x, y in pts]
    upper = [bm.verts.new(Vector(place.to_world(x, y, panel.thickness)) + Vector(offset)) for x, y in pts]
    caps = [bm.faces.new(lower), bm.faces.new(upper)]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lower[i], lower[j], upper[j], upper[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Blender's default n-gon fill mis-tessellates long concave outlines (curved
    # tops with many vertices); ear clipping handles them correctly.
    bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    mesh = bpy.data.meshes.new(panel.name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(panel.name, mesh)
    col.objects.link(obj)
    if mat is not None:
        mesh.materials.append(mat)
        obj.color = mat.diffuse_color
    return obj


def wire_box(name: str, col: bpy.types.Collection, lo: Vec3, hi: Vec3,
             rgb: tuple[float, float, float] = (0.3, 0.3, 0.3)) -> bpy.types.Object:
    """A cuboid reduced to thin struts along its edges, for showing the space a
    design must fit inside. A Wireframe modifier is used rather than wire display so
    it also appears in renders."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(tuple(lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    wire = obj.modifiers.new("wire", "WIREFRAME")
    wire.thickness = 0.08
    wire.use_boundary = True
    obj.color = (*rgb, 1.0)
    col.objects.link(obj)
    return obj


def mesh_points(objects) -> list[Vector]:
    return [obj.matrix_world @ v.co for obj in objects for v in obj.data.vertices]


VIEW_ROTATIONS = {
    # camera looks along its local -Z; these orient that axis for each named view
    "top": Quaternion((1.0, 0.0, 0.0, 0.0)),
    "front": Euler((math.pi / 2, 0.0, 0.0)).to_quaternion(),
    "left": Euler((math.pi / 2, 0.0, -math.pi / 2)).to_quaternion(),
    "back": Euler((math.pi / 2, 0.0, math.pi)).to_quaternion(),
    "iso": (-Vector((-0.75, -1.0, 0.8))).to_track_quat("-Z", "Y"),
    # steep look down into the front-left corner from inside the box
    "corner": Vector((-0.6, -0.8, -1.4)).to_track_quat("-Z", "Y"),
}


def ortho_camera(name: str, rotation: Quaternion, points: list[Vector],
                 resolution: tuple[int, int], margin: float = 1.06,
                 distance: float = 100.0) -> bpy.types.Object:
    """An orthographic camera with the given rotation, pulled back along its view
    axis and scaled so every point in `points` is in frame."""
    right = rotation @ Vector((1.0, 0.0, 0.0))
    up = rotation @ Vector((0.0, 1.0, 0.0))
    back = rotation @ Vector((0.0, 0.0, 1.0))
    xs = [p.dot(right) for p in points]
    ys = [p.dot(up) for p in points]
    zs = [p.dot(back) for p in points]
    center = (right * (max(xs) + min(xs)) / 2 + up * (max(ys) + min(ys)) / 2
              + back * (max(zs) + min(zs)) / 2)
    aspect = resolution[0] / resolution[1]
    ext_x, ext_y = max(xs) - min(xs), max(ys) - min(ys)
    scale = max(ext_x, ext_y * aspect) if aspect >= 1 else max(ext_y, ext_x / aspect)

    cam = bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = scale * margin
    cam.clip_start = 0.1
    cam.clip_end = distance * 4
    obj = bpy.data.objects.new(name, cam)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = rotation
    obj.location = center + back * distance
    bpy.context.scene.collection.objects.link(obj)
    return obj


def setup_workbench(scene: bpy.types.Scene) -> None:
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "OBJECT"
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.show_object_outline = True
    shading.show_shadows = False
    shading.use_world_space_lighting = True
    scene.display.render_aa = "8"
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.color = (1.0, 1.0, 1.0)


def render_png(scene: bpy.types.Scene, camera: bpy.types.Object, path: str,
               resolution: tuple[int, int]) -> None:
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.compression = 90
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
