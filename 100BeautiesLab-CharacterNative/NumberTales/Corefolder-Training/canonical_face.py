"""Fit the 926-point editable face and its Humanoid joints to the actual #4 VRM.

Re-measure the correspondence from the two original files:
blender -b --offline-mode --disable-autoexec -P canonical_face.py -- --measure
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_character_export import Glb

ROOT = HERE.parents[2]
REFERENCE = ROOT / "Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-4/vrm_corefolder4.vrm"
NATIVE = HERE.parent / "Corefolder-4/VRCModel_CoreFloder-4.blend"
MAPPING = HERE / "canonical-face-map.json"
SLOTS = ("neck", "head", "leftEye", "rightEye")
CONVERT = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=np.float32)


def reference_data():
    glb = Glb(REFERENCE)
    face, = [n for n in glb.doc["nodes"] if n.get("name") == "Face" and "mesh" in n]
    mesh = glb.doc["meshes"][face["mesh"]]
    primitive, = mesh["primitives"]
    basis = glb.array(primitive["attributes"]["POSITION"]) @ CONVERT.T
    targets = {name: glb.array(target["POSITION"]) @ CONVERT.T
               for name, target in zip(mesh["extras"]["targetNames"], primitive["targets"])}
    human = {h["bone"]: h["node"] for h in glb.vrm["humanoid"]["humanBones"]}
    parents = {child: i for i, node in enumerate(glb.doc["nodes"]) for child in node.get("children", [])}
    rotations, positions = {}, {}
    def global_pose(i):
        if i not in rotations:
            node = glb.doc["nodes"][i]
            x, y, z, w = node.get("rotation", (0, 0, 0, 1))
            rotation = Quaternion((w, x, y, z))
            point = Vector(node.get("translation", (0, 0, 0)))
            if i in parents:
                parent_rot, parent_pos = global_pose(parents[i])
                point, rotation = parent_pos + parent_rot @ point, parent_rot @ rotation
            rotations[i], positions[i] = rotation, point
        return rotations[i], positions[i]
    joints = {}
    for slot in ("chest", *SLOTS):
        i = human[slot]
        rotation, point = global_pose(i)
        joints[slot] = {"origin": CONVERT @ point,
                        "axis": CONVERT @ np.array(rotation.to_matrix()) @ CONVERT.T,
                        "parent": next(h for h, parent in human.items() if parent == parents[i])}
    return basis, targets, joints


def measure():
    basis, morphs, joints = reference_data()
    bpy.ops.wm.open_mainfile(filepath=str(NATIVE), use_scripts=False)
    face = bpy.data.objects["Face"]
    keys = face.data.shape_keys.key_blocks
    def world_points(key):
        return np.array([face.matrix_world @ p.co for p in keys[key].data])
    native_basis = world_points("Basis")
    native = np.stack([native_basis] + [world_points(name) - native_basis for name in morphs], axis=1)
    exported = np.stack([basis, *morphs.values()], axis=1)
    indices = []
    for item in native:
        hits = np.flatnonzero(np.max(abs(basis - item[0]), axis=1) < .000001)
        if not len(hits):
            raise ValueError("A native face vertex is missing from the actual #4 VRM")
        # Resolve coincident points with their complete expression trajectories.
        indices.append(int(hits[np.argmin(np.linalg.norm(exported[hits] - item, axis=(1, 2)))]))
    if len(indices) != 926 or len(set(indices)) != 926:
        raise ValueError("The source-native to real-VRM correspondence must be one-to-one")
    arm = face.find_armature()
    slots = {h.bone: h.node.bone_name for h in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    roll = {}
    for slot in SLOTS:
        bone = arm.data.bones[slots[slot]]
        matrix = arm.matrix_world @ bone.matrix_local
        if np.linalg.norm(np.array(matrix.translation) - joints[slot]["origin"]) > 1e-6:
            raise ValueError(f"#4 native joint origin differs from the actual VRM: {slot}")
        # VRM 0.x rest nodes use the exported axes. The matching native basis
        # supplies Blender's bone-tail direction and roll for round-tripping.
        roll[slot] = {"blender_axis_from_vrm": (joints[slot]["axis"].T @ np.array(matrix.to_3x3())).tolist(),
                      "length": float((arm.matrix_world @ bone.tail_local - matrix.translation).length)}
    data = {"vrm_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
            "native_sha256": hashlib.sha256(NATIVE.read_bytes()).hexdigest(),
            "vertex_indices": indices, "joints": roll,
            "max_basis_correspondence_mm": float(np.max(np.linalg.norm(basis[indices] - native_basis, axis=1)) * 1000),
            "max_morph_correspondence_mm": float(np.max(np.linalg.norm(exported[indices, 1:] - native[:, 1:], axis=2)) * 1000)}
    MAPPING.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print("Measured", len(indices), "facial vertices and", len(roll), "joints", MAPPING)


def fit_reference_face(face, arm):
    if face.get("corefolder_canonical_face") == 4:
        return
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != mapping["vrm_sha256"]:
        raise ValueError("Re-measure canonical-face-map.json for the current #4 reference")
    basis, morphs, joints = reference_data()
    indices = mapping["vertex_indices"]
    keys = face.data.shape_keys.key_blocks
    if len(keys[0].data) != len(indices) or set(keys.keys()) != {"Basis", *morphs}:
        raise ValueError("Expected the #4-derived editable face and its 15 original keys")
    slots = {h.bone: h.node.bone_name for h in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    # Anchor the reference head/neck assembly on the character's own chest.
    chest = arm.matrix_world @ arm.data.bones[slots["chest"]].head_local
    offset = np.array(chest) - joints["chest"]["origin"]
    arm_inverse = arm.matrix_world.inverted()
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        for slot in SLOTS:
            edit = arm.data.edit_bones[slots[slot]]
            edit.parent = arm.data.edit_bones[slots[joints[slot]["parent"]]]
            roll = mapping["joints"][slot]
            matrix = Matrix((joints[slot]["axis"] @ roll["blender_axis_from_vrm"]).tolist()).to_4x4()
            matrix.translation = Vector(joints[slot]["origin"] + offset)
            edit.matrix = arm_inverse @ matrix
            edit.length = roll["length"] / float(arm.matrix_world.to_scale().y)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    local = np.array(face.matrix_world.inverted())
    for key in keys:
        world = basis if key.name == "Basis" else basis + morphs[key.name]
        target = (world[indices] + offset) @ local[:3,:3].T + local[:3,3]
        key.data.foreach_set("co", target.astype(np.float32).ravel())
    face.data.update()
    face["corefolder_canonical_face"] = 4


def compare_reference_face(face, arm, excluded):
    """Measure every included editable point in the head frame against the real reference."""
    basis, morphs, joints = reference_data()
    mapping = json.loads(MAPPING.read_text(encoding="utf8"))
    keep = np.setdiff1d(np.arange(len(mapping["vertex_indices"])), list(excluded))
    mapped = np.asarray(mapping["vertex_indices"])[keep]
    humanoid = {h.bone: h.node.bone_name for h in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    origin = np.array(arm.matrix_world @ arm.data.bones[humanoid["head"]].head_local)
    world = np.array(face.matrix_world)
    maximum = {}
    for key in face.data.shape_keys.key_blocks:
        data = np.empty(len(face.data.vertices)*3, dtype=np.float32)
        key.data.foreach_get("co", data)
        current = data.reshape(-1, 3)[keep] @ world[:3, :3].T + world[:3, 3] - origin
        reference = basis if key.name == "Basis" else basis + morphs[key.name]
        reference = reference[mapped] - joints["head"]["origin"]
        maximum[key.name] = float(np.max(np.linalg.norm(current - reference, axis=1))*1000)
    return {"vrm": REFERENCE.relative_to(ROOT).as_posix(), "reference_sha256": mapping["vrm_sha256"],
            "points_per_pose": len(keep), "excluded_oral_and_fan_points": len(excluded),
            "maximum_position_difference_mm": maximum}


if __name__ == "__main__" and "--measure" in sys.argv:
    measure()
