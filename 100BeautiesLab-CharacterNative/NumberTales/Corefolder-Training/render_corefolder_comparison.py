"""Render local VRM candidates alongside the six references at one world scale in Blender."""
import argparse
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from prepare import read_vrm


def load_model(path, label, expected_hash=None, accept_candidate_license=False):
    _, digest = read_vrm(path)
    if expected_hash and digest != expected_hash:
        raise ValueError(f"Reference changed: {path}")
    before = set(bpy.data.objects)
    settings = {"filepath": str(path), "extract_textures_into_folder": False,
                "enable_mtoon_outline_preview": True}
    starter_record = path.parent / "starter.json"
    known_starter = False
    if not expected_hash and starter_record.is_file():
        record = json.loads(starter_record.read_text(encoding="utf-8"))
        known_starter = record.get("export", {}).get("sha256") == digest
    if expected_hash or known_starter or accept_candidate_license:
        imported = bpy.ops.wm.vrm_license_warning(import_anyway=True, **settings)
    else:
        imported = bpy.ops.import_scene.vrm(use_addon_preferences=False, **settings)
    if imported != {"FINISHED"}:
        raise RuntimeError(f"Import failed: {path}. If Blender requests a license confirmation, review the VRM Meta.")
    objects = set(bpy.data.objects) - before
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ Vector(point) for obj in objects
              if obj.type == "MESH" and not obj.hide_render for point in obj.bound_box]
    if not points:
        raise ValueError(f"No visible mesh: {path}")
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    model = bpy.data.collections.new(label)
    for obj in objects:
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        model.objects.link(obj)
    return model, (low + high) / 2, high - low, digest


def world_text(text, position, size, ink):
    curve = bpy.data.curves.new(text, "FONT")
    curve.body = text
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.materials.append(ink)
    obj = bpy.data.objects.new(text, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler.x = math.pi / 2


def render(candidates, out, accept_candidate_license=False):
    if not bpy.app.background or out.exists():
        raise ValueError("Start background Blender and choose a new output directory")
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    sources = json.loads((HERE / "style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    rows = [(f'#{rec["id"]}', ROOT / rec["source"], rec["sha256"]) for rec in sources]
    rows.extend((p.stem, p, None) for p in candidates)
    models = [load_model(path, label, expected, accept_candidate_license) for label, path, expected in rows]
    size = max(max(dim) for _, _, dim, _ in models)
    cell = 1.20 * size
    ink = bpy.data.materials.new("Caption")
    ink.use_nodes = True
    emission = ink.node_tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (0.90, 0.90, 0.90, 1)
    output = next(node for node in ink.node_tree.nodes if node.type == "OUTPUT_MATERIAL")
    ink.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    column_x = (-0.60 * cell, 0.48 * cell, 1.56 * cell)
    views = (("Front", 0), ("Side", -math.pi / 2), ("Back", math.pi))
    for x, (view, _) in zip(column_x, views):
        world_text(view, (x, -3 * size, cell * 0.65), cell * 0.14, ink)
    for index, ((label, _, _), (model, center, _, _)) in enumerate(zip(rows, models)):
        z = -index * cell
        display_label = label.replace("Corefolder-", "#").replace("-Starter", "\nStarter")
        world_text(display_label, (-1.53 * cell, -3 * size, z), cell * 0.12, ink)
        for x, (_, rotation) in zip(column_x, views):
            instance = bpy.data.objects.new(label, None)
            scene.collection.objects.link(instance)
            instance.instance_type = "COLLECTION"
            instance.instance_collection = model
            instance.rotation_euler.z = rotation
            instance.location = Vector((x, 0, z)) - instance.rotation_euler.to_matrix() @ center
    width = cell * 4.30
    height = cell * (len(rows) + 0.38)
    camera = bpy.data.objects.new("Comparison camera", bpy.data.cameras.new("Comparison camera"))
    scene.collection.objects.link(camera)
    camera.location = (0, -max(15.0, size * 9), (0.30 - (len(rows) - 1)) * cell / 2)
    camera.rotation_euler.x = math.pi / 2
    camera.data.type = "ORTHO"
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.ortho_scale = width
    scene.camera = camera
    sun = bpy.data.objects.new("Comparison light", bpy.data.lights.new("Comparison light", "SUN"))
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector((0.35, 1, -0.6)).to_track_quat("-Z", "Y").to_euler()
    sun.data.energy = 2.0
    scene.world = bpy.data.worlds.new("Gray background")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.14, 0.14, 0.14, 1)
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16
    scene.eevee.use_shadows = False
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = 960
    scene.render.resolution_y = round(960 * height / width)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temp:
        work = Path(temp) / "comparison"
        work.mkdir()
        scene.render.filepath = str(work / "three-views.png")
        bpy.ops.render.render(write_still=True)
        facts = {"renderer": scene.render.engine, "blender": bpy.app.version_string,
                 "width_in_blender_units": width, "views": [v for v, _ in views],
                 "models": [{"label": label, "source": str(path), "sha256": digest,
                             "dimensions": list(dim)} for (label, path, _), (_, _, dim, digest) in zip(rows, models)]}
        (work / "comparison.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
        work.rename(out)
    print(f"Rendered {out / 'three-views.png'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--accept-candidate-license", action="store_true",
                        help="Confirm that the supplied candidates' VRM Meta permits this local review")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    render([p.resolve() for p in args.candidate], args.output.resolve(), args.accept_candidate_license)
