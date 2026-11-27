"""Rebuild mouth-profiles.npz and measure the mouths of the six native reference faces.

blender -b --offline-mode --disable-autoexec -P measure_face_profiles.py
Optional arguments after -- are --out <npz> and --measurements <json>.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from face_articulation import ORAL, PROFILES, RIM

# Right lip corner and two central rim vertices measured on each native mesh.
# These landmarks use the interior lip strip, including the duplicates at UV seams.
LANDMARKS = {4: (132, 370, 368), 16: (168, 173, 175), 20: (174, 179, 180),
             22: (572, 495, 194), 25: (153, 158, 159), 93: (131, 325, 323)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_native(number):
    path, = (HERE.parent / f"Corefolder-{number}").glob("VRCModel*.blend")
    bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
    obj, = [o for o in bpy.context.scene.objects if o.type == "MESH" and
            o.name.lower().startswith("face") and o.data.shape_keys]
    mesh = obj.data
    mesh.calc_loop_triangles()
    keys = {k.name: np.array([obj.matrix_world @ pt.co for pt in k.data], dtype="f4")
            for k in mesh.shape_keys.key_blocks}
    loop_indices = [i for t in mesh.loop_triangles for i in t.loops]
    indices = np.array([mesh.loops[i].vertex_index for i in loop_indices])
    uvs = np.array([mesh.uv_layers.active.data[i].uv[:] for i in loop_indices])
    arm = obj.find_armature()
    slots = {h.bone: h.node.bone_name for h in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    corner, upper, lower = LANDMARKS[number]
    b = keys["Basis"]
    center = b[upper]
    right = b[corner]
    mirrored = right.copy()
    mirrored[0] = 2 * center[0] - right[0]
    left = np.linalg.norm(b - mirrored, axis=1).argmin()
    width = abs(right[0] - b[left, 0])
    # Enumerate the outer face surface at the level of the cheeks. This excludes
    # the integrated ears, ponytails and accessories in several reference Face objects.
    band = (abs(b[:, 2] - center[2]) < .055) & (b[:, 1] < center[1] + .19)
    span = np.ptp(b[band, 0])
    gap = lambda x: float(x[upper, 2] - x[lower, 2])
    influential = lambda i: {obj.vertex_groups[g.group].name: float(g.weight)
                             for g in mesh.vertices[i].groups if g.weight > .0001 and
                             obj.vertex_groups[g.group].name in arm.data.bones}
    metrics = {"number": number, "native": path.relative_to(HERE.parents[2]).as_posix(),
               "sha256": sha(path), "face_mesh": mesh.name, "lip_corner_width_m": float(width),
               "front_surface_span_at_cheek_height_m": float(span), "width_to_span": float(width/span),
               "rest_central_gap_m": gap(b), "half_a_central_gap_m": gap((b + keys["a"])/2),
               "full_a_central_gap_m": gap(keys["a"]), "head": slots["head"], "neck": slots["neck"],
               "jaw": slots.get("jaw") or None, "upper_lip_raw_deform_weights": influential(upper),
               "lower_lip_raw_deform_weights": influential(lower)}
    return keys, indices, uvs, metrics


def correspond(original, sample):
    basis, tri, uv, _ = original
    target, target_tri, target_uv, _ = sample
    indices = []
    for i in ORAL:
        options = np.unique(uv[tri == i], axis=0)
        if i in RIM:
            options = options[options[:, 0] > .6]
        matches = np.unique(np.concatenate([target_tri[np.max(abs(target_uv - q), axis=1) < .000016]
                                            for q in options]))
        p = basis["Basis"][i]
        if abs(p[0]) > .00015:
            matches = matches[target["Basis"][matches, 0] * p[0] > 0]
        if not len(matches):
            raise ValueError(f"Missing corresponding inner UV for source vertex {i}")
        indices.append(int(matches[np.linalg.norm(target["Basis"][matches] - p, axis=1).argmin()]))
    if len(set(indices)) != len(ORAL):
        raise ValueError("Expected 192 distinct lip, oral wall and tongue vertices")
    return indices


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=HERE / "mouth-profiles.npz")
    p.add_argument("--measurements", type=Path, default=HERE / "production-review/canonical-mouth.json")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    outputs = {"target_indices": ORAL}
    records = []
    used = {profile[0] for profile in PROFILES.values()}
    for number in LANDMARKS:
        sample = read_native(number)
        records.append(sample[3])
        if number == 4:
            original = sample
        if number in used:
            indices = correspond(original, sample)
            outputs[f"{number}_indices"] = indices
            for name, coordinates in sample[0].items():
                outputs[f"{number}_{name}"] = coordinates[indices]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, **outputs)
    args.measurements.parent.mkdir(parents=True, exist_ok=True)
    args.measurements.write_text(json.dumps({"profile_sha256": sha(args.out), "references": records},
                                           indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
