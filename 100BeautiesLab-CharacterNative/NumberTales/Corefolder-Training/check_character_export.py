"""Audit production VRMs against their editable sources, official tail counts and Khronos glTF Validator.

Run with Python, NumPy, Pillow and Node.js. --blender also uses SciPy for triangle matching.
Pass --db <CreationsDB checkout>.
The --validator argument accepts the installed gltf-validator npm package directory.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
TYPE = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Glb:
    def __init__(self, path):
        self.data = path.read_bytes()
        magic, version, size, length, kind = struct.unpack_from("<4sIII4s", self.data)
        if (magic, version, size, kind) != (b"glTF", 2, len(self.data), b"JSON"):
            raise ValueError(f"Invalid GLB header: {path}")
        self.doc = json.loads(self.data[20:20 + length])
        self.bin = memoryview(self.data)[28 + length:]
        self.vrm = self.doc["extensions"]["VRM"]

    def buffer(self, index):
        view = self.doc["bufferViews"][index]
        start = view.get("byteOffset", 0)
        return self.bin[start:start + view["byteLength"]]

    def array(self, index):
        a = self.doc["accessors"][index]
        width = WIDTH[a["type"]]
        dtype = np.dtype(TYPE[a["componentType"]])

        def read(view_index, offset, count, data_type, cols):
            size = data_type.itemsize
            stride = self.doc["bufferViews"][view_index].get("byteStride", size * cols)
            return np.ndarray((count, cols), dtype=data_type, buffer=self.buffer(view_index),
                              offset=offset, strides=(stride, size))

        arr = (read(a["bufferView"], a.get("byteOffset", 0), a["count"], dtype, width)
               if "bufferView" in a else np.zeros((a["count"], width), dtype=dtype))
        if sparse := a.get("sparse"):
            ix, values = sparse["indices"], sparse["values"]
            indices = read(ix["bufferView"], ix.get("byteOffset", 0), sparse["count"],
                           np.dtype(TYPE[ix["componentType"]]), 1)
            arr = arr.copy()
            arr[indices.ravel()] = read(values["bufferView"], values.get("byteOffset", 0),
                                        sparse["count"], dtype, width)
        if a.get("normalized"):
            return np.maximum(-1, arr / np.iinfo(dtype).max)
        return arr


def khronos(data, validator):
    source = """
const validator = require(process.argv[1]);
const data = require('fs').readFileSync(0);
validator.validateBytes(new Uint8Array(data), { format:'glb', maxIssues:0, writeTimestamp:false })
 .then(r => process.stdout.write(JSON.stringify({version:validator.version(), ...r.issues})))
 .catch(e => { console.error(e); process.exitCode=1; });
"""
    result = subprocess.run(["node", "-e", source, str(validator.resolve())],
                            input=data, check=True, capture_output=True)
    report = json.loads(result.stdout)
    return {"version": report["version"], "errors": report["numErrors"], "warnings": report["numWarnings"],
            "infos": report["numInfos"], "hints": report["numHints"],
            "diagnostic_counts": dict(Counter(m["code"] for m in report["messages"])),
            "error_and_warning_messages": [m for m in report["messages"] if m["severity"] <= 1]}


def geometry(glb):
    doc = glb.doc
    by_node = {}
    for node in doc["nodes"]:
        if "mesh" not in node:
            continue
        triangles = 0
        for p in doc["meshes"][node["mesh"]]["primitives"]:
            if p.get("mode", 4) != 4:
                raise ValueError(f"Unexpected primitive mode in {node['name']}")
            accessor = p["indices"] if "indices" in p else p["attributes"]["POSITION"]
            triangles += doc["accessors"][accessor]["count"] // 3
        by_node[node["name"]] = triangles
    return {"mesh_count": len(doc["meshes"]), "material_count": len(doc["materials"]),
            "triangles": sum(by_node.values()), "triangles_by_node": by_node}


def mtoon_materials(glb):
    fields = ("_ShadeShift", "_ShadeToony", "_IndirectLightIntensity", "_OutlineWidthMode", "_OutlineWidth")
    return {m["name"]: {"shader": m["shader"], **{f: m["floatProperties"].get(f) for f in fields}}
            for m in glb.vrm["materialProperties"]}


def display_layers(glb, errors):
    doc = glb.doc
    by_node = {node["name"]: sorted({doc["materials"][p["material"]]["name"]
               for p in doc["meshes"][node["mesh"]]["primitives"]}) for node in doc["nodes"] if "mesh" in node}
    if not by_node.get("Outfit"):
        errors.append("Missing independently switchable Outfit renderer")
    skull = {node for node, mats in by_node.items() if any(m.startswith("Corefolder Cranial Base") for m in mats)}
    if skull != {"Body"}:
        errors.append("The naked cranial skin must remain visible with Hair and Outfit disabled")
    return {"materials_by_renderer":by_node, "cranial_skin_nodes":sorted(skull)}


def canonical_stats():
    refs = json.loads((HERE / "style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    result = []
    for ref in refs:
        glb = Glb(ROOT / ref["source"])
        if sha(glb.data) != ref["sha256"]:
            raise ValueError(f"Reference changed: {ref['source']}")
        result.append({"number": ref["id"], "source": ref["source"], "sha256": ref["sha256"],
                       **geometry(glb), "materials": mtoon_materials(glb)})
    return result


def skinning(glb, errors):
    doc = glb.doc
    weighted = {}
    vertex_count, max_error, max_influences = 0, 0.0, 0
    unskinned = []
    for node in doc["nodes"]:
        if "mesh" not in node:
            continue
        if "skin" not in node:
            unskinned.append(node["name"])
            continue
        joints = np.array(doc["skins"][node["skin"]]["joints"])
        for p in doc["meshes"][node["mesh"]]["primitives"]:
            attr = p["attributes"]
            n = doc["accessors"][attr["POSITION"]]["count"]
            total = np.zeros(n)
            influences = np.zeros(n, dtype=int)
            for suffix in sorted(k[8:] for k in attr if k.startswith("WEIGHTS_")):
                weights = glb.array(attr["WEIGHTS_" + suffix])
                joint_nodes = joints[glb.array(attr["JOINTS_" + suffix])]
                mask = weights > 1e-6
                if not np.isfinite(weights).all() or (weights < 0).any():
                    errors.append(f"Invalid skin weights in {node['name']}")
                total += weights.sum(axis=1)
                influences += mask.sum(axis=1)
                for idx, count in zip(*np.unique(joint_nodes[mask], return_counts=True)):
                    counts = weighted.setdefault(int(idx), {})
                    counts[node["name"]] = counts.get(node["name"], 0) + int(count)
            vertex_count += n
            max_error = max(max_error, float(abs(total - 1).max()))
            max_influences = max(max_influences, int(influences.max()))
    if max_error > 1e-4:
        errors.append(f"Skin weight sum error {max_error}")
    return weighted, {"skinned_primitive_vertices": vertex_count, "max_weight_sum_error": max_error,
                      "max_influences": max_influences, "unskinned_mesh_nodes": unskinned}


def springs(glb, weighted, record, errors):
    nodes = glb.doc["nodes"]
    parent = {child: i for i, node in enumerate(nodes) for child in node.get("children", [])}
    slots = {b["node"]: b["bone"] for b in glb.vrm["humanoid"]["humanBones"]}
    animation = glb.vrm["secondaryAnimation"]
    groups = []
    for group in animation["boneGroups"]:
        for root in group["bones"]:
            chain = [root]
            while children := nodes[chain[-1]].get("children", []):
                if len(children) != 1:
                    errors.append(f"Unexpected fork within spring {group['comment']}")
                    break
                chain.append(children[0])
            anchor = slots.get(parent[root], nodes[parent[root]]["name"])
            counts = [sum(weighted.get(i, {}).values()) for i in chain]
            # The terminal provides a direction. The preceding joints must drive skin.
            if min(counts[:-1], default=0) < 1 or not nodes[chain[-1]]["name"].endswith("_end"):
                errors.append(f"Incomplete skinning or terminal bone in {group['comment']}")
            groups.append({"name": group["comment"], "parent": anchor, "nodes": [nodes[i]["name"] for i in chain],
                           "weighted_vertex_counts": counts,
                           "mesh_nodes": sorted({m for i in chain for m in weighted.get(i, {})}),
                           "stiffness": group["stiffiness"], "drag_force": group["dragForce"],
                           "gravity": {"direction": group["gravityDir"], "power": group["gravityPower"]},
                           "hit_radius": group["hitRadius"],
                           "collider_groups": group["colliderGroups"]})
    tail_count = sum(g["parent"] == "hips" for g in groups)
    expected = sum(unit["Count"] for unit in record["TailsUnit"])
    if tail_count != expected or sum(g["parent"] == "head" for g in groups) < 1:
        errors.append(f"Expected {expected} tail roots and animated hair")
    layer_counts = {}
    for unit in record["TailsUnit"]:
        for layer in unit.get("Branches") or []:
            token = layer["Laterality"].split("_")[-1].lower()
            if token == "lower":
                token = "low"
            count = sum(g["parent"] == "hips" and token in g["name"].lower() for g in groups)
            layer_counts[layer["Laterality"]] = count
            if count != layer["TailCount"]:
                errors.append(f"Official branch count differs for {layer['Laterality']}")
    return {"official_tail_units": record["TailsUnit"], "tail_roots_attached_to_hips": tail_count,
            "named_roots_by_official_branch_layer": layer_counts,
            "hair_roots_attached_to_head": sum(g["parent"] == "head" for g in groups),
            "groups": groups, "colliders": [{"node": nodes[c["node"]]["name"], "spheres": c["colliders"]}
                                            for c in animation.get("colliderGroups", [])]}


def expressions(glb, errors):
    result = {}
    for group in glb.vrm["blendShapeMaster"]["blendShapeGroups"]:
        name = group["name"] if group["presetName"] == "unknown" else group["presetName"]
        binds = []
        for bind in group["binds"]:
            if bind["weight"] <= 0:
                continue
            mesh = glb.doc["meshes"][bind["mesh"]]
            max_distance, vertices = 0.0, 0
            for prim in mesh["primitives"]:
                target = (prim.get("targets") or [])[bind["index"]]
                if "POSITION" in target:
                    length = np.linalg.norm(glb.array(target["POSITION"]), axis=1)
                    max_distance = max(max_distance, float(length.max()))
                    vertices += int((length > 1e-6).sum())
            if not vertices:
                errors.append(f"Expression {name} is bound to a stationary morph")
            binds.append({"mesh": mesh["name"], "target": bind["index"], "weight": bind["weight"],
                          "moving_primitive_vertices": vertices, "max_local_delta": round(max_distance, 7)})
        if binds:
            result[name] = binds
    return result


def textures(glb, errors):
    from PIL import Image

    uses = {}
    for material in glb.vrm["materialProperties"]:
        for key, index in material["textureProperties"].items():
            source = glb.doc["textures"][index]["source"]
            uses.setdefault(source, []).append([material["name"], key])
    images = []
    for i, item in enumerate(glb.doc.get("images", [])):
        data = glb.buffer(item["bufferView"])
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            bbox = image.convert("RGB").getextrema()
            images.append({"name": item["name"], "bytes": len(data), "sha256": sha(data), "mime": item["mimeType"],
                           "size": list(image.size), "rgb_channel_ranges": bbox, "mtoon_bindings": uses.get(i, [])})
    if not images or not uses:
        errors.append("Missing embedded material textures")
    return images


def inspect_editable_scene(ungrouped):
    import bmesh
    import bpy
    from mathutils import Matrix

    def coordinates(obj):
        bpy.context.view_layer.update()
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        data = np.empty(len(evaluated.data.vertices) * 3, dtype="f")
        evaluated.data.vertices.foreach_get("co", data)
        return data.reshape(-1, 3)

    arm, = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    ext = arm.data.vrm_addon_extension.vrm0
    images = {i.name: i.packed_file.size if i.packed_file else 0
              for i in bpy.data.images if i.source == "FILE"}
    refs = {o.data.name for o in bpy.context.scene.objects
            if o.type == "EMPTY" and o.empty_display_type == "IMAGE" and o.data}
    for col in bpy.data.collections:
        if "official references" in col.name.lower():
            for obj in col.objects:
                for slot in obj.material_slots:
                    material = slot.material
                    if material and material.node_tree:
                        refs.update(n.image.name for n in material.node_tree.nodes
                                    if n.type == "TEX_IMAGE" and n.image)
    manifest = bpy.context.scene.get("corefolder_export_meshes")
    selected = ([bpy.context.scene.objects[n] for n in json.loads(manifest)] if manifest else
                [o for o in bpy.context.scene.objects if o.type == "MESH" and o.find_armature() == arm])
    bpy.ops.object.select_all(action="DESELECT")
    for obj in [arm, *selected]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    result = bpy.ops.export_scene.vrm(filepath=ungrouped, use_addon_preferences=False, export_only_selections=True,
                                      armature_object_name=arm.name, ignore_warning=True)
    if result != {"FINISHED"}:
        raise RuntimeError(f"Unmerged verification export failed: {result}")
    groups = sorted(g.comment for g in ext.secondary_animation.bone_groups)
    keys = {o.name: len(o.data.shape_keys.key_blocks) for o in bpy.context.scene.objects
            if o.type == "MESH" and o.data.shape_keys}
    from face_articulation import LOWER, ORAL, UPPER
    from canonical_face import compare_reference_face
    face, = [o for o in selected if o.get("corefolder_mouth_revision")]
    reference_face = compare_reference_face(face, arm, set(ORAL) | {10, 30, 59, 238, 263, 268, 292, 298})
    face_keys = face.data.shape_keys.key_blocks
    human = {h.bone: h.node.bone_name for h in ext.humanoid.human_bones}
    head = arm.pose.bones[human["head"]]
    face_from_arm = face.matrix_world.inverted() @ arm.matrix_world
    mouth = {}
    poses = {"Neutral": {}, "Aa25": {"a": .25}, "Aa50": {"a": .5}, "Aa100": {"a": 1},
             "Aa50Joy50": {"a": .5, "Joy": .5}, "Ih50Sorrow50": {"i": .5, "Sorrow": .5}}
    for label, values in poses.items():
        for key in list(face_keys)[1:]:
            key.value = values.get(key.name, 0.)
        rest = coordinates(face)
        gaps = rest[list(UPPER[1:-1]), 2] - rest[list(LOWER[1:-1]), 2]
        rec = {"center_gap_mm": float(gaps[3] * 1000), "minimum_rim_gap_mm": float(gaps.min() * 1000),
               "corner_width_mm": float(abs(rest[UPPER[0], 0] - rest[UPPER[-1], 0]) * 1000)}
        for slot, angle in (("head", 12), ("neck", 8)):
            parent = arm.pose.bones[human[slot]]
            basis = parent.matrix_basis.copy()
            head_before = face_from_arm @ head.matrix
            try:
                parent.matrix_basis = basis @ Matrix.Rotation(np.deg2rad(angle), 4, "Y")
                actual = coordinates(face)[ORAL]
                delta = np.array(face_from_arm @ head.matrix @ head_before.inverted())
                rigid = rest[ORAL] @ delta[:3, :3].T + delta[:3, 3]
                rec[f"{slot}_{angle}_deg_rigid_residual_mm"] = float(np.linalg.norm(actual - rigid, axis=1).max() * 1000)
            finally:
                parent.matrix_basis = basis
                bpy.context.view_layer.update()
        mouth[label] = rec
    for key in list(face_keys)[1:]:
        key.value = 0
    checks = []
    for group in ext.secondary_animation.bone_groups:
        name = group.bones[0].bone_name
        bone = arm.pose.bones[name]
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH" or name not in obj.vertex_groups:
                continue
            rest = coordinates(obj)
            basis = bone.matrix_basis.copy()
            try:
                bone.matrix_basis = basis @ Matrix.Rotation(.20, 4, "X")
                moved = float(np.linalg.norm(coordinates(obj) - rest, axis=1).max())
            finally:
                bone.matrix_basis = basis
            residual = float(np.linalg.norm(coordinates(obj) - rest, axis=1).max())
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            nonmanifold = sum(not e.is_manifold for e in bm.edges)
            bm.free()
            checks.append(dict(group=group.comment, mesh=obj.name, max_local_delta=moved,
                               max_rest_residual=residual, nonmanifold_edges=nonmanifold))
    return dict(blender=bpy.app.version_string, packed_images=images, reference_images=sorted(refs),
                springs=groups, shape_keys=keys, root_rotation_0_2_rad=checks, mouth_poses=mouth,
                canonical_face_geometry=reference_face)


def inspect_blend(path, blender, grouped, images, expected_groups, errors):
    from compare_export_meshes import compare_triangles

    with TemporaryDirectory() as tmp:
        separate = Path(tmp) / "editing-parts.vrm"
        result = subprocess.run([str(blender), "-b", "--offline-mode", "--disable-autoexec", str(path),
                                 "-t", "2", "--python-exit-code", "1", "-P", __file__, "--",
                                 "--inspect-blend", str(separate)],
                                check=True, capture_output=True, encoding="utf-8", errors="replace")
        comparison = compare_triangles(Glb(separate), grouped)
    report = json.loads(next(s.removeprefix("EDITABLE_JSON ") for s in result.stdout.splitlines()
                             if s.startswith("EDITABLE_JSON ")))
    required = [t["name"] for t in images] + report["reference_images"]
    if any(report["packed_images"].get(i, 0) == 0 for i in required):
        errors.append("Editable blend is missing packed material or reference images")
    if not report["reference_images"] or report["springs"] != sorted(expected_groups) or not report["shape_keys"]:
        errors.append("Editable blend contents differ from VRM or lack reference images")
    poses = report["mouth_poses"]
    if max(report["canonical_face_geometry"]["maximum_position_difference_mm"].values()) > .01:
        errors.append("The exterior face or eyelids in one or more poses differ from the #4 reference geometry")
    if not (poses["Neutral"]["center_gap_mm"] < 1 and
            poses["Neutral"]["center_gap_mm"] < poses["Aa25"]["center_gap_mm"] <
            poses["Aa50"]["center_gap_mm"] < poses["Aa100"]["center_gap_mm"]):
        errors.append("Closure or progressive phoneme opening failed")
    if any(p["minimum_rim_gap_mm"] < -.01 or p["head_12_deg_rigid_residual_mm"] > .001 or
           p["neck_8_deg_rigid_residual_mm"] > .001 for p in poses.values()):
        errors.append("Fitted oral surfaces intersect or fail to follow the head in one or more poses")
    checks = report["root_rotation_0_2_rad"]
    if set(g["group"] for g in checks) != set(expected_groups):
        errors.append("Some spring roots do not address editable mesh vertices")
    for check in checks:
        if check["max_local_delta"] <= 1e-4 or check["max_rest_residual"] > 1e-5:
            errors.append(f"Pose or rest-delta check failed on {check['mesh']}")
    return {"file": path.relative_to(ROOT).as_posix(), "sha256": sha(path.read_bytes()),
            "mesh_group_comparison": comparison, **report}


def audit(path, starter, record, validator, blender, unity_root):
    errors = []
    glb = Glb(path)
    doc, ext = glb.doc, glb.vrm
    base = Glb(starter)
    report = khronos(glb.data, validator)
    slots = sorted(b["bone"] for b in ext["humanoid"]["humanBones"])
    if slots != sorted(b["bone"] for b in base.vrm["humanoid"]["humanBones"]):
        errors.append("Humanoid slots differ from starter")
    rights_keys = set(base.vrm["meta"]) - {"title", "version", "texture"}
    if any(base.vrm["meta"][key] != ext["meta"].get(key) for key in rights_keys):
        errors.append("Author, attribution or license metadata differ from starter")
    morphs = expressions(glb, errors)
    if set(morphs) != set(expressions(base, [])):
        errors.append("Bound expression set differs from starter")
    weighted, skin = skinning(glb, errors)
    secondary = springs(glb, weighted, record, errors)
    images = textures(glb, errors)
    materials = mtoon_materials(glb)
    if any(v["shader"] != "VRM/MToon" for v in materials.values()):
        errors.append("Non-MToon VRM material")
    if report["errors"]:
        errors.append("glTF Validator errors")
    if ext["specVersion"] != "0.0":
        errors.append(f"Unexpected VRM specification {ext['specVersion']}")
    blend = (inspect_blend(path.with_suffix(".blend"), blender, glb, images,
                           [g["name"] for g in secondary["groups"]], errors) if blender else None)
    deployed = None
    if unity_root:
        target = unity_root / f"Corefolder-{record['Num']}" / path.name
        deployed = {"file": target.resolve().relative_to(ROOT).as_posix(),
                    "sha256": sha(target.read_bytes()) if target.is_file() else None}
        if deployed["sha256"] != sha(glb.data):
            errors.append("Unity VRM missing or different from the native export")
    number = int(record["Num"])
    source_blend = (HERE.parent / f"Corefolder-{number}/Corefolder-{number}-Refined.blend"
                    if number in (57, 85) else starter.with_suffix(".blend"))
    return {"number": number, "file": path.relative_to(ROOT).as_posix(), "sha256": sha(glb.data),
            "bytes": len(glb.data), "source_vrm_sha256": sha(base.data),
            "source_blend": source_blend.name, "source_blend_sha256": sha(source_blend.read_bytes()),
            "generator": doc["asset"]["generator"],
            "vrm_version": ext["specVersion"], "metadata": ext["meta"], "humanoid_slots": len(slots),
            "geometry": geometry(glb), "display_layers":display_layers(glb, errors),
            "skins": len(doc["skins"]), "skinning": skin,
            "materials": materials, "textures": images, "bound_expressions": morphs,
            "secondary_animation": secondary, "khronos_gltf_validator": report, "editable_blend": blend,
            "unity_asset": deployed, "errors": errors}


if __name__ == "__main__" and "--inspect-blend" in sys.argv:
    sys.path.insert(0, str(HERE))
    print("EDITABLE_JSON " + json.dumps(inspect_editable_scene(sys.argv[-1]), ensure_ascii=True))
elif __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True, type=Path)
    cache = ROOT / ".cache/vrm-5.3-tests"
    p.add_argument("--starters", type=Path, default=cache / "verified-20261125")
    p.add_argument("--validator", type=Path, default=cache / "khronos/node_modules/gltf-validator")
    p.add_argument("--blender", type=Path, help="Also reopen and verify the adjacent editable blend")
    p.add_argument("--unity-root", type=Path, help="Verify the identical deployed copy in each Corefolder-N")
    p.add_argument("--candidate", action="append", nargs=2, metavar=("NUMBER", "VRM"))
    p.add_argument("--out", type=Path, default=HERE / "production-review/format-checks.json")
    args = p.parse_args()
    db_path = args.db / "data/Works_NumberTales/DataBases/db_Primary.json"
    records = {str(r["Num"]): r for r in json.loads(db_path.read_text(encoding="utf-8-sig"))}
    candidates = args.candidate or [(n, HERE.parent / f"Corefolder-{n}/Modeling/Corefolder-{n}.vrm")
                                    for n in (6, 49, 57, 85)]
    audits = []
    for number, path in candidates:
        number = int(number)
        starter = (ROOT / f"Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{number}/Refined/Corefolder-{number}-Refined.vrm"
                   if number in (57, 85) else args.starters / f"Corefolder-{number}/Corefolder-{number}-Starter.vrm")
        result = audit(Path(path).resolve(), starter,
                       records[str(number)], args.validator, args.blender, args.unity_root)
        print(f"#{number} {result['sha256']} {result['errors']}")
        audits.append(result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    contents = {"official_db": "data/Works_NumberTales/DataBases/db_Primary.json", "official_db_sha256": sha(db_path.read_bytes()),
                "canonical_geometry": canonical_stats(), "characters": audits}
    args.out.write_text(json.dumps(contents, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    raise SystemExit(int(any(result["errors"] for result in audits)))
