"""Build an editable Corefolder starter from the common body, #4 face/rig and a chosen VRM material."""
import argparse
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
import numpy as np
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from foundation import common_body, sha
from prepare import IDS, read_vrm
from refine_models import toon

STYLE_FIELDS = (
    "shading_shift_factor", "shading_toony_factor", "gi_equalization_factor",
    "outline_width_mode", "outline_width_factor", "outline_lighting_mix_factor",
)
VRM0_STYLE_FIELDS = (
    "_ShadeShift", "_ShadeToony", "_IndirectLightIntensity",
    "_OutlineWidthMode", "_OutlineWidth", "_OutlineLightingMix",
)


def official_inputs(db_root, number):
    works = db_root / "data/Works_NumberTales"
    records = json.loads((works / "DataBases/db_Primary.json").read_text(encoding="utf-8-sig"))
    record, = [r for r in records if str(r["Num"]) == str(number)]
    if record.get("Progress") != "released" or any(
        record.get(k) for k in ("isPrivate", "DB_Hidden", "Works_Hidden", "AI_Optout")
    ):
        raise ValueError(f"Check the source permissions and release status of #{number}")
    images = works / "Images/DB_Primary"
    refs = [images / "corefolder" / (name + ".png") for name in record["Images"]["corefolder_PNGPath"]]
    if not refs:
        raise ValueError(f"No official Corefolder image for #{number}")
    tail = images / f"attr/tailsUnit/attr_tailsUnitNTS-{number}.png"
    if tail.is_file():
        refs.append(tail)
    for path in refs:
        if not path.is_file() or not path.resolve().is_relative_to(images.resolve()):
            raise ValueError(f"Unavailable official reference: {path}")
    return record, refs


def read_style(number, material_name):
    refs = json.loads((HERE / "style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    ref, = [r for r in refs if r["id"] == number]
    path = ROOT / ref["source"]
    gltf, digest = read_vrm(path)
    if digest != ref["sha256"]:
        raise ValueError(f"Reference changed: {path}")
    vrm = gltf["extensions"]["VRM"]
    materials = {m["name"]: m for m in vrm["materialProperties"] if m["shader"] == "VRM/MToon"}
    if material_name is None and len(materials) == 1:
        material_name = next(iter(materials))
    if material_name not in materials:
        raise ValueError(f"Select one --material from #{number}: {', '.join(materials)}")
    bpy.ops.wm.read_homefile(use_empty=True)
    result = bpy.ops.wm.vrm_license_warning(
        filepath=str(path), import_anyway=True, extract_textures_into_folder=False,
        enable_mtoon_outline_preview=False,
    )
    if result != {"FINISHED"}:
        raise RuntimeError(f"Could not read reference VRM: {result}")
    mtoon = bpy.data.materials[material_name].vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon
    return {
        "reference": ref["source"], "sha256": digest, "material": material_name,
        "blender": {field: getattr(mtoon, field) for field in STYLE_FIELDS},
        "vrm0": {field: materials[material_name]["floatProperties"][field] for field in VRM0_STYLE_FIELDS},
    }


def split_donor_leg_weights(body, arm):
    """The #4 bare body has right-leg groups on both halves of its symmetric surface."""
    slots = {slot.bone: slot.node.bone_name for slot in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    to_arm = arm.matrix_world.inverted() @ body.matrix_world
    changes = {}
    for segment in ("UpperLeg", "Toes"):
        left_name, right_name = (slots[side + segment] for side in ("left", "right"))
        right = body.vertex_groups.get(right_name)
        left = body.vertex_groups.get(left_name)
        if right is None or (left and any(
            g.group == left.index and g.weight > 0 for v in body.data.vertices for g in v.groups
        )):
            continue
        left = left or body.vertex_groups.new(name=left_name)
        left_x = arm.data.bones[left_name].head_local.x
        right_x = arm.data.bones[right_name].head_local.x
        if math.isclose(left_x, right_x, abs_tol=1e-6):
            raise ValueError(f"Leg bones have no lateral separation: {segment}")
        moved = 0
        for vertex in body.data.vertices:
            weight = next((g.weight for g in vertex.groups if g.group == right.index), 0.0)
            x = (to_arm @ vertex.co).x
            share = min(1.0, max(0.0, (x - right_x) / (left_x - right_x)))
            if weight > 0 and share > 0:
                left.add([vertex.index], weight * share, "REPLACE")
                if share == 1.0:
                    right.remove([vertex.index])
                else:
                    right.add([vertex.index], weight * (1.0 - share), "REPLACE")
                moved += 1
        changes[segment] = moved
    for vertex in body.data.vertices:
        if not math.isclose(sum(g.weight for g in vertex.groups), 1.0, abs_tol=1e-5):
            raise ValueError(f"Body weight sum changed on vertex {vertex.index}")
    return changes


def make_base(number, styles, body_color):
    donor = HERE.parent / "Corefolder-4/VRCModel_CoreFloder-4.blend"
    bpy.ops.wm.open_mainfile(filepath=str(donor), load_ui=False, use_scripts=False)
    arm, face = bpy.data.objects["Armature"], bpy.data.objects["Face"]
    for obj in list(bpy.data.objects):
        if obj.name not in ("Body", "Armature", "Face"):
            bpy.data.objects.remove(obj, do_unlink=True)
    body_info = common_body(ROOT / "100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend")
    body = bpy.data.objects["Body"]
    body_info["bilateral_weight_vertices"] = split_donor_leg_weights(body, arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in list(arm.data.edit_bones):
        if bone.name.startswith("Tail"):
            arm.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode="OBJECT")
    ext = arm.data.vrm_addon_extension
    ext.spec_version = "0.0"
    vrm = ext.vrm0
    vrm.secondary_animation.bone_groups.clear()
    vrm.secondary_animation.collider_groups.clear()
    vrm.meta.title = f"Corefolder-{number} / editable starter"
    vrm.meta.version = "starter"
    vrm.meta.texture = None
    # The donor can contain older MToon node templates under the same names as 4.10.5.
    # Only the rig, UVs and shape keys are used from this in-memory copy.
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for group in list(bpy.data.node_groups):
        if group.bl_idname == "ShaderNodeTree":
            bpy.data.node_groups.remove(group)
    for obj, color in ((body, body_color or "#BFBFBF"), (face, "#BFBFBF")):
        mat = toon(f"Corefolder-{number} {obj.name} working material", color)
        props = mat.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon
        for key, value in styles[obj.name]["blender"].items():
            setattr(props, key, value)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for poly in obj.data.polygons:
            poly.material_index = 0
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (arm, face, body):
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    return arm, body_info, donor


def inspect_export(path, arm, styles):
    doc, digest = read_vrm(path)
    vrm = doc["extensions"]["VRM"]
    bones = {b["bone"] for b in vrm["humanoid"]["humanBones"]}
    groups = vrm["blendShapeMaster"]["blendShapeGroups"]
    expected = {
        (group.preset_name if group.preset_name != "unknown" else group.name, bind.index)
        for group in arm.data.vrm_addon_extension.vrm0.blend_shape_master.blend_shape_groups
        for bind in group.binds if bind.weight > 0
    }
    bound = set()
    for group in groups:
        for bind in group.get("binds", []):
            if not 0 <= bind["mesh"] < len(doc["meshes"]):
                raise ValueError(f"Unresolved expression mesh: {group['name']}")
            mesh = doc["meshes"][bind["mesh"]]
            primitives = mesh["primitives"]
            if not 0 <= bind["index"] < min(len(p.get("targets", [])) for p in primitives):
                raise ValueError(f"Unresolved expression bind: {group['name']}")
            if bind["weight"] > 0:
                preset = group["presetName"] if group["presetName"] != "unknown" else group["name"]
                bound.add((preset, mesh["extras"]["targetNames"][bind["index"]]))
    mapped_bones = {b.bone for b in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones if b.node.bone_name}
    if vrm["specVersion"] != "0.0" or bones != mapped_bones or len(bones) != 53 or expected != bound or ("blink", "EyeClose") not in bound:
        raise ValueError(f"Unexpected base rig or expression bindings: {bound}")
    materials = vrm["materialProperties"]
    if len(materials) != 2 or len(doc["meshes"]) != 2:
        raise ValueError("Expected only the body and face in the starter export")
    by_name = {mat["name"]: mat for mat in materials}
    for obj_name, style in styles.items():
        mat = by_name[bpy.data.objects[obj_name].active_material.name]
        if mat["shader"] != "VRM/MToon" or any(
            not math.isclose(mat["floatProperties"][key], value, abs_tol=1e-5)
            for key, value in style["vrm0"].items()
        ):
            raise ValueError(f"MToon settings changed for {mat['name']}")
    return {"sha256": digest, "humanoid_slots": len(bones), "bound_expressions": sorted({k for k, _ in bound}),
            "meshes": len(doc["meshes"]), "verified_mtoon_materials": len(materials)}


def body_pose_check(arm):
    """Measure actual deformation of the common torso, including registered but unused leg slots."""
    body = bpy.data.objects["Body"]
    slots = {b.bone: b.node.bone_name for b in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}

    def positions():
        bpy.context.view_layer.update()
        mesh = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
        coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", coords)
        return coords.reshape((-1, 3))

    neutral = positions()
    deltas = {}
    for slot in ("hips", "leftUpperLeg", "rightUpperLeg", "leftToes", "rightToes"):
        bone = arm.pose.bones[slots[slot]]
        rest = bone.matrix_basis.copy()
        try:
            bone.matrix_basis = rest @ Matrix.Rotation(math.radians(15), 4, "X")
            deltas[slot] = float(np.linalg.norm(positions() - neutral, axis=1).max())
        finally:
            bone.matrix_basis = rest
    if not np.allclose(positions(), neutral, atol=1e-6):
        raise ValueError("Body did not return to its neutral pose")
    if min(deltas.values()) <= 1e-4:
        raise ValueError(f"A tested bone did not deform the starter torso: {deltas}")
    return deltas


def build(args):
    if not bpy.app.background:
        raise RuntimeError("Run this in a separate background Blender process")
    dest = args.output.resolve() / f"Corefolder-{args.number}"
    if dest.exists() or dest.is_relative_to(ROOT / "Assets"):
        raise ValueError(f"Choose a new production folder outside Assets: {dest}")
    record, refs = official_inputs(args.db.resolve(), args.number)
    palette = [entry["Hex"] for entry in record.get("ColorPalette", []) if entry.get("Hex")]
    if args.body_color and args.body_color.upper() not in {c.upper() for c in palette}:
        raise ValueError(f"--body-color must come from the official palette: {palette}")
    body_style = read_style(args.style, args.material)
    face_style = body_style
    if args.face_style is not None or args.face_material is not None:
        face_style = read_style(args.face_style or args.style, args.face_material)
    styles = {"Body": body_style, "Face": face_style}
    arm, body_info, donor = make_base(args.number, styles, args.body_color)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=dest.parent, prefix=".corefolder-") as temp:
        work = Path(temp) / dest.name
        work.mkdir()
        vrm = work / f"{dest.name}-Starter.vrm"
        result = bpy.ops.export_scene.vrm(filepath=str(vrm), use_addon_preferences=False,
                    export_only_selections=True, armature_object_name=arm.name, ignore_warning=True)
        if result != {"FINISHED"}:
            raise RuntimeError(f"Export failed: {result}")
        checks = inspect_export(vrm, arm, styles)
        refs_collection = bpy.data.collections.new("Official references")
        bpy.context.scene.collection.children.link(refs_collection)
        for i, ref in enumerate(refs):
            image = bpy.data.images.load(str(ref), check_existing=True)
            image.pack()
            obj = bpy.data.objects.new(ref.stem, None)
            obj.empty_display_type = "IMAGE"
            obj.data = image
            obj.rotation_euler.x = math.pi / 2
            obj.empty_display_size = 1.4
            obj.location = (-1.5 * (i + 1), 0.5, 0.6)
            obj.hide_render = True
            refs_collection.objects.link(obj)
        report = {
            "number": args.number, "stage": "editable body and expression starter",
            "body": body_info, "rig_face_source": donor.relative_to(ROOT).as_posix(),
            "rig_face_sha256": sha(donor), "styles": styles, "body_color": args.body_color,
            "official_palette": palette, "official_tails": record.get("TailsUnit", []),
            "reference_images": [{"path": p.relative_to(args.db.resolve()).as_posix(), "sha256": sha(p)} for p in refs],
            "export": checks,
            "body_max_delta_at_15_degrees": body_pose_check(arm),
            "pending": ["face design and textures", "hair", "target tails, weights and springs",
                        "accessories", "three-view and runtime review"],
        }
        bpy.context.scene["corefolder_stage"] = report["stage"]
        bpy.data.orphans_purge(do_recursive=True)
        bpy.context.preferences.filepaths.file_preview_type = "NONE"
        bpy.ops.wm.save_as_mainfile(filepath=str(work / f"{dest.name}-Starter.blend"))
        (work / "starter.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        work.rename(dest)
    print(f"Created {dest}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--db", required=True, type=Path, help="CreationsDB checkout")
    parser.add_argument("--output", required=True, type=Path, help="Parent of a new Corefolder-N directory")
    parser.add_argument("--style", required=True, type=int, choices=IDS, help="MToon reference model number")
    parser.add_argument("--material", help="Exact reference material name; required when there is more than one")
    parser.add_argument("--face-style", type=int, choices=IDS, help="Optional separate shading reference for Face")
    parser.add_argument("--face-material", help="Select the Face reference material by name")
    parser.add_argument("--body-color", help="Explicit official palette hex; omitted for a neutral working material")
    build(parser.parse_args(sys.argv[sys.argv.index("--") + 1:]))
