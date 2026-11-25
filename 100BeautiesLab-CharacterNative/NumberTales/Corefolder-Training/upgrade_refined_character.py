"""Rig and export the existing #57/#85 Refined mesh in an independent Blender process.

An optional Modeling/design_N.py can implement revise(arm, collection), returning
world-space centerlines keyed by mesh name for parts whose rest shape it changes.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from corefolder_springs import add_collider_group, add_spring_chain, bind_to_chain, register_spring, save_character
from atlas_tail_sculpt import revise_tails


def ring_guides(obj):
    """The Refined hair lofts contain 25 sequential sections of 16 vertices."""
    if len(obj.data.vertices) != 400:
        raise ValueError(f"Provide a replacement centerline for the remodeled {obj.name}")
    points = []
    for ring in (0, 6, 12, 18, 24):
        center = sum((obj.data.vertices[ring * 16 + j].co for j in range(16)), Vector()) / 16
        points.append(obj.matrix_world @ center)
    return points


def rig_tail(arm, obj, guide, collider):
    names = [f"{obj.name}.{i:03d}" for i in (1, 2, 3)]
    if guide is not None:
        points = [arm.matrix_world.inverted() @ Vector(p) for p in guide]
        if len(points) < 4 or any((b-a).length < 1e-6 for a,b in zip(points, points[1:])):
            raise ValueError(f"{obj.name} needs at least four distinct centerline positions")
        names.extend(f"{obj.name}.{i:03d}" for i in range(4, len(points)))
    else:
        points = [arm.data.bones[n].head_local.copy() for n in names]
        points.append(arm.data.bones[names[-1]].tail_local.copy())
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bones = arm.data.edit_bones
        previous = bones[names[0]].parent
        for i, name in enumerate(names):
            b = bones.get(name) or bones.new(name)
            b.use_connect = False
            b.parent = previous
            b.head, b.tail = points[i], points[i + 1]
            b.use_connect = i > 0
            previous = b
        end = bones.new(obj.name + "_end")
        end.head = points[-1]
        end.tail = points[-1] + 0.15 * (points[-1] - points[-2])
        end.parent = previous
        end.use_connect = True
        names.append(end.name)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    bind_to_chain(arm, obj, names)
    register_spring(arm, obj.name, names[0], "tail", .018, [collider])


def build(number, output, design):
    folder = HERE.parent / f"Corefolder-{number}"
    bpy.ops.wm.open_mainfile(filepath=str(folder / f"Corefolder-{number}-Refined.blend"), use_scripts=False)
    arm = bpy.data.objects["Armature"]
    col = bpy.data.objects["Body"].users_collection[0]
    guides = {}
    if design.is_file():
        spec = importlib.util.spec_from_file_location(f"corefolder_design_{number}", design)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(design.parent))
        spec.loader.exec_module(module)
        guides = module.revise(arm, col) or {}
    guides.update(revise_tails(number, arm, col))
    bpy.context.view_layer.update()
    rump = add_collider_group(arm, "Rump", "hips", [((0, .01, .34), .215)])
    head = add_collider_group(arm, "Head", "head", [((0, -.065, .87), .180)])
    tails = [o for o in col.objects if o.type == "MESH" and o.name.startswith("Tail_")]
    expected = {57: 7, 85: 8}[number]
    if len(tails) != expected:
        raise ValueError(f"Expected {expected} refined tails, found {len(tails)}")
    for tail in tails:
        rig_tail(arm, tail, guides.get(tail.name), rump)
    hair = ((("Hair ponytail",), "Hair_Ponytail"),
            (("Hair cheek R", "Hair fringe 3"), "Hair_Side_R"),
            (("Hair cheek L", "Hair fringe 4"), "Hair_Side_L"))
    for alternatives, spring in hair:
        obj = next((col.objects.get(n) for n in alternatives if col.objects.get(n)), None)
        if obj is None:
            raise ValueError(f"Missing hair mesh for {spring}: {alternatives}")
        points = guides.get(obj.name)
        if points is None:
            points = json.loads(obj["spring_path"]) if "spring_path" in obj else ring_guides(obj)
        bones = add_spring_chain(arm, obj, spring, points, parent="head", kind="hair", radius=.012,
                                 colliders=[head])
        if spring == "Hair_Ponytail" and (fork := col.objects.get("Hair ponytail fork")):
            bind_to_chain(arm, fork, bones)
    meshes = [o for o in col.objects if o.type == "MESH"]
    return save_character(arm, meshes, output / f"Corefolder-{number}.blend", output / f"Corefolder-{number}.vrm",
                          title=f"Corefolder-{number}", version="1.0", character_number=number)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--number", type=int, required=True, choices=(57, 85))
    p.add_argument("--out", type=Path)
    p.add_argument("--design", type=Path, help="Optional character-specific sculpt module")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.design and not args.design.is_file():
        p.error(f"Cannot find design module: {args.design}")
    folder = HERE.parent / f"Corefolder-{args.number}" / "Modeling"
    print(build(args.number, args.out or folder, args.design or folder / f"design_{args.number}.py"), flush=True)
