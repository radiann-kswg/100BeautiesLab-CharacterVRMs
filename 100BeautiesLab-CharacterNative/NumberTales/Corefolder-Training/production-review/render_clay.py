"""Render comparable untextured whole, body and tail views of the original and production models.

python render_clay.py --blender <Blender executable> [--out <folder>] [--candidate 57 <VRM>] [--undressed]
"""
import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT / "100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend"
TILE = 448
SPAN = 1.76
GROUPS = ("whole", "body", "tail")
VIEWS = ("Front", "Side", "Back")
REFS = (4, 16, 20, 22, 25, 93)
CHARACTERS = (6, 49, 57, 85)
sys.path.insert(0, str(HERE))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_model(source, output, undressed=False):
    import bpy
    import numpy as np
    from mathutils import Vector

    if source.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    else:
        bpy.ops.wm.read_homefile(use_empty=True)
        result = bpy.ops.wm.vrm_license_warning(import_anyway=True, filepath=str(source),
                  extract_textures_into_folder=False, enable_mtoon_outline_preview=False)
        if result != {"FINISHED"}:
            raise RuntimeError(f"Failed to import {source}")
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    raw = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]
    import undressed_parts
    layers = undressed_parts.GROUPS if undressed else GROUPS
    geometry = {k: bpy.data.collections.new("Clay geometry " + k) for k in layers}
    bounds = []
    membership = {}
    torso = []
    for obj in raw:
        # Freeze the actual skinned neutral mesh (or the base's mirror modifiers).
        ev = obj.evaluated_get(graph)
        mesh = bpy.data.meshes.new_from_object(ev, depsgraph=graph)
        vertex = np.empty(len(mesh.vertices)*3, dtype=np.float32)
        mesh.vertices.foreach_get("co", vertex)
        matrix = np.array(obj.matrix_world)
        points = vertex.reshape(-1, 3) @ matrix[:3,:3].T + matrix[:3,3]
        bounds.extend((points.min(axis=0), points.max(axis=0)))
        if undressed:
            subsets, membership[obj.name], skin = undressed_parts.select(output.name, obj, mesh, points)
            if skin is not None:
                torso.append(skin)
            extracted = {}
            for group, polygons in subsets.items():
                if not polygons:
                    continue
                key = tuple(polygons)
                if key not in extracted:
                    part = undressed_parts.extract(mesh, polygons)
                    baked = bpy.data.objects.new("Clay " + obj.name, part)
                    baked.matrix_world = obj.matrix_world.copy()
                    extracted[key] = baked
                geometry[group].objects.link(extracted[key])
            continue
        groups = ["whole"]
        partial = []
        if obj.name.lower().startswith("tail"):
            groups.append("tail")
        if obj.name.lower().startswith(("body","outfit")):
            # Production Body also carries a head-weighted cranial patch that
            # survives toggling Hair. Keep the dressed-torso panel anatomical.
            shell = {slot for slot, material in enumerate(mesh.materials)
                     if material and material.name.startswith("Corefolder Cranial Base")}
            if shell:
                kept = [p.index for p in mesh.polygons if p.material_index not in shell]
                if kept:
                    part = bpy.data.objects.new("Clay torso " + obj.name, undressed_parts.extract(mesh,kept))
                    part.matrix_world = obj.matrix_world.copy()
                    geometry["body"].objects.link(part)
                    partial.append("body excluding cranial patch")
            else:
                groups.append("body")
        membership[obj.name] = groups + partial
        mesh.materials.clear()
        baked = bpy.data.objects.new("Clay " + obj.name, mesh)
        baked.matrix_world = obj.matrix_world.copy()
        for group in groups:
            geometry[group].objects.link(baked)
    for obj in list(scene.objects):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
    if not all(len(c.objects) for c in geometry.values()):
        raise ValueError(f"Check body/tail object naming in {source}: {membership}")
    low, high = np.min(bounds, axis=0), np.max(bounds, axis=0)
    center = Vector((low + high) / 2)
    if undressed:
        if len(torso) != 1:
            raise ValueError(f"Expected one torso in {source}")
        lo, hi = torso[0]
        center = Vector(((lo[0] + hi[0])/2, (lo[1] + hi[1])/2, lo[2] + .60))
    if np.max(high-low) >= SPAN:
        raise ValueError(f"Model exceeds common camera width: {source}")
    for row, group in enumerate(layers):
        for col, angle in enumerate((0., -math.pi/2, math.pi)):
            instance = bpy.data.objects.new(group+" "+VIEWS[col], None)
            scene.collection.objects.link(instance)
            instance.instance_type = "COLLECTION"
            instance.instance_collection = geometry[group]
            instance.rotation_euler.z = angle
            instance.location = Vector(((col-1)*SPAN, 0, (1-row)*SPAN)) - instance.rotation_euler.to_matrix() @ center
    camera = bpy.data.objects.new("Clay camera", bpy.data.cameras.new("Clay camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3*SPAN
    camera.location = (0,-12,0)
    camera.rotation_euler.x = math.pi/2
    scene.render.engine = "BLENDER_WORKBENCH"
    shade = scene.display.shading
    shade.light = "STUDIO"
    shade.studio_light = "studio.sl"
    shade.studiolight_rotate_z = 0
    shade.studiolight_intensity = 1
    shade.use_studiolight_view_rotation = False
    shade.color_type = "SINGLE"
    shade.single_color = (.57,.57,.57)
    shade.background_type = "WORLD"
    scene.world = bpy.data.worlds.new("Clay grey background")
    scene.world.color = (.115,.125,.14)
    shade.show_shadows = True
    scene.display.light_direction = (-.55,.36,.75)
    shade.show_cavity = True
    shade.cavity_type = "BOTH"
    shade.cavity_ridge_factor = .55
    shade.cavity_valley_factor = .82
    shade.curvature_ridge_factor = .40
    shade.curvature_valley_factor = .58
    scene.display.matcap_ssao_distance = .071
    scene.display.matcap_ssao_samples = 32
    shade.show_specular_highlight = True
    shade.show_object_outline = False
    shade.show_backface_culling = False
    shade.show_xray = False
    scene.display.render_aa = "16"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.film_transparent = False
    scene.render.resolution_x = scene.render.resolution_y = 3*TILE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output.with_suffix(".png"))
    bpy.ops.render.render(write_still=True)
    return {"sha256":digest(source), "bounds_m":[low.tolist(),high.tolist()], "camera_center_m":list(center), "meshes":membership,
            "blender":bpy.app.version_string}


def body_widths(prefix, model):
    import numpy as np
    from PIL import Image
    from scipy.ndimage import label

    image = np.array(Image.open(prefix.with_suffix(".png")).convert("RGB"), dtype=int)
    center_z = model["camera_center_m"][2]
    shared_z = .36
    shared_row = int((.5 + (center_z - shared_z)/SPAN)*TILE)
    result = {}
    for col, dimension in enumerate(("width", "depth")):
        tile = image[TILE:2*TILE, col*TILE:(col+1)*TILE]
        silhouette = np.max(abs(tile - tile[0,0]), axis=2) > 5
        labels, _ = label(silhouette)
        counts = np.bincount(labels.ravel())
        counts[0] = 0
        mask = labels == np.argmax(counts)
        occupied = np.where(mask)[0]
        middle_row = (occupied.min() + occupied.max()) // 2
        def span(row):
            cols = np.flatnonzero(mask[row])
            return int(cols.max() - cols.min() + 1)
        middle_px, shared_px = span(middle_row), span(shared_row)
        result[dimension] = {"half_silhouette_height_px":middle_px,
                             "half_silhouette_height_m":middle_px*SPAN/TILE,
                             "world_z_0_36_px":shared_px, "world_z_0_36_m":shared_px*SPAN/TILE}
    return result


def assemble(records, cached, output, layers):
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("segoeui.ttf", 22)
    bold = ImageFont.truetype("segoeuib.ttf", 30)
    gutter, header, left = 8, 100, 80
    panel = left+3*TILE
    for row_index, group in enumerate(layers):
        sheet = Image.new("RGB", (gutter+2*panel, header+6*TILE), "#292e34")
        pen = ImageDraw.Draw(sheet)
        for side, (title, ids) in enumerate((("Reference VRMs", REFS), ("Common base and production VRMs", ("Base", *CHARACTERS)))):
            x = side*(panel+gutter)
            pen.text((x+left,8), title, font=bold, fill="#ffffff")
            for col, view in enumerate(VIEWS):
                pen.text((x+left+(col+.5)*TILE,73), view, anchor="mm", font=font, fill="#e1e6eb")
            for row, number in enumerate(ids):
                y = header + row*TILE
                label = "Base" if number=="Base" else f"#{number}"
                pen.text((x+left/2,y+TILE/2), label, anchor="mm", font=font, fill="white")
                with Image.open(cached[str(number)].with_suffix(".png")) as raw:
                    sheet.paste(raw.crop((0,row_index*TILE,3*TILE,(row_index+1)*TILE)).convert("RGB"), (x+left,y))
        if group in ("body", "bare-torso"):
            x, y = panel+gutter+left, header+5*TILE
            pen.text((x+22,y+15), "Body section at 0.36 m", font=bold, fill="white")
            columns = (x+22, x+375, x+740)
            for column, heading in zip(columns, ("Model", "Front width (m)", "Side depth (m)")):
                pen.text((column,y+76),heading,font=font,fill="#bbc8d2")
            def readings(numbers, dimension):
                values = [records["models"][str(n)]["body_silhouette"][dimension]["world_z_0_36_m"] for n in numbers]
                lo, hi = min(values), max(values)
                return f"{lo:.3f}" if lo == hi else f"{lo:.3f} – {hi:.3f}"
            sets = [("Six reference VRMs",REFS), ("Common base",("Base",))]
            sets.extend((f"#{n}", (n,)) for n in CHARACTERS)
            for i, (label, numbers) in enumerate(sets):
                for column, value in zip(columns, (label, readings(numbers,"width"), readings(numbers,"depth"))):
                    pen.text((column,y+120+42*i),value,font=font,fill="white")
            pen.text((x+22,y+390),f"One image pixel = {1000*SPAN/TILE:.2f} mm",font=font,fill="#bbc8d2")
        if group in ("undressed", "cranial-base"):
            message = ("Clothing off. Hair and ears visible." if group == "undressed" else
                       "Underlying head and torso. Integrated ears and head shells retained.")
            x, y = panel+gutter+left+22, header+5*TILE+30
            pen.text((x,y),message,font=font,fill="white")
            pen.text((x,y+53),"#16 has an opening where the original blue cap covered the crown.",
                     font=font,fill="#c2cbd2")
        sheet.save(output/f"clay-{group}.png", optimize=True)
    name = "clay-undressed.json" if "undressed" in layers else "clay-views.json"
    (output/name).write_text(json.dumps(records, indent=2)+"\n", encoding="utf8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--candidate", nargs=2, action="append", default=[], metavar=("NUMBER", "VRM"))
    parser.add_argument("--out", type=Path, default=HERE)
    parser.add_argument("--undressed",action="store_true",help="Render the torso and head from actual mesh islands, with clothing hidden")
    args = parser.parse_args()
    import undressed_parts
    layers = undressed_parts.GROUPS if args.undressed else GROUPS
    cache = ROOT / ".cache/vrm-5.3-tests/clay"
    cache.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    sources = {"Base":BASE}
    manifest = json.loads((HERE.parent/"style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    for ref in manifest:
        path = ROOT/ref["source"]
        if digest(path) != ref["sha256"]:
            raise ValueError(f"Reference #{ref['id']} changed")
        sources[str(ref["id"])] = path
    sources.update({str(n):HERE.parent.parent/f"Corefolder-{n}/Modeling/Corefolder-{n}.vrm" for n in CHARACTERS})
    sources.update({n:Path(p).resolve() for n,p in args.candidate})
    metadata = {"camera_span_m":SPAN, "tile_px":TILE, "views":VIEWS, "renderer":"Workbench studio.sl, single grey",
                "surface":"Neutral evaluated skinned meshes and evaluated base modifiers; vertex normals retained. "
                          "Material textures, opacity and MToon inverted-hull outlines are omitted.",
                "groups":["whole rendered mesh", "Body and Outfit nodes excluding the head-weighted cranial patch", "tail-named mesh nodes"],
                "cavity":"world + screen, distance 0.071m, 32 samples", "models":{}}
    metadata["body_width_method"] = {"metres_per_pixel":SPAN/TILE, "image_threshold_8bit":5,
        "area":"Largest connected torso silhouette; clothing joined in projection is included.",
        "levels":"At half height of each isolated silhouette and at the shared character-space height z=0.36m."}
    if args.undressed:
        metadata["groups"] = list(layers)
        metadata["alignment"] = "Center each model on the torso island's bounding-box midpoint in XY and 0.60m above its floor."
        metadata["selection"] = "Weld positions to 10 micrometres for island membership. Preserve evaluated positions and per-corner normals. #4 and #16 have an open face front. Retain the real hair-backed shell. Remove #16's cap and bill by its blue/grey atlas UV islands. An uncovered opening remains where the artist supplied no second skin beneath the cap. #20, #22, #25, #93 have an integrated skin/ear shell. Clothing and tails are excluded; each part is enumerated below."
        metadata["body_width_method"]["area"] = "The isolated torso skin, measured with all attached clothing and head meshes hidden."
    render_source = (inspect.getsource(render_model), TILE, SPAN, layers, VIEWS,
                     inspect.getsource(undressed_parts) if args.undressed else "",
                     str(args.blender.resolve()), args.blender.stat().st_mtime_ns)
    render_id = hashlib.sha256(repr(render_source).encode()).hexdigest()
    stored = cache/"by-sha"/render_id
    stored.mkdir(parents=True, exist_ok=True)
    cached = {label:stored/digest(source) for label,source in sources.items()}
    missing = {label:str(source) for label,source in sources.items() if
               not (cached[label].with_suffix(".json").exists() and cached[label].with_suffix(".png").exists())}
    if missing:
        # Each run renders privately; concurrent candidates can never replace a
        # different asset's thumbnails while the contact sheet is being built.
        with TemporaryDirectory(dir=cache) as staging:
            job = Path(staging)/"job.json"
            job.write_text(json.dumps({"sources":missing,"undressed":args.undressed}), encoding="utf8")
            subprocess.run([str(args.blender), "-b", "--offline-mode", "--disable-autoexec", "-t", "3",
                            "--python-exit-code", "1", "-P", __file__, "--", "--render", str(job)],check=True)
            for label in missing:
                fresh = job.parent/label
                if json.loads(fresh.with_suffix(".json").read_text())["sha256"] != cached[label].name:
                    raise ValueError(f"Source changed during the clay render of {label}")
                for extension in (".png", ".json"):
                    fresh.with_suffix(extension).replace(cached[label].with_suffix(extension))
    for label, source in sources.items():
        data = json.loads(cached[label].with_suffix(".json").read_text())
        data["source"] = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source)
        data["body_silhouette"] = body_widths(cached[label],data)
        metadata["models"][label] = data
    assemble(metadata, cached, args.out, layers)


if __name__ == "__main__":
    if "--render" in sys.argv:
        job = Path(sys.argv[-1])
        jobdata = json.loads(job.read_text())
        for label, source in jobdata["sources"].items():
            prefix = job.parent/label
            meta = render_model(Path(source), prefix, jobdata["undressed"])
            prefix.with_suffix(".json").write_text(json.dumps(meta), encoding="utf8")
    else:
        main()
