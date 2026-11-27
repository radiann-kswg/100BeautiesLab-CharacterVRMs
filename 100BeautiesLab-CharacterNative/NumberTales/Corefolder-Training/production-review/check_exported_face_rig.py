"""Compare the actual VRM 0.x rest joints and eye skin in head coordinates against #4."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from check_character_export import Glb, sha

REFERENCE_IDS = (4, 16, 20, 22, 25, 93)
TARGET_IDS = (6, 49, 57, 85)
JOINTS = ("neck", "head", "leftEye", "rightEye")


def pose_matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"]).reshape(4, 4).T
    out = np.eye(4)
    out[:3, 3] = node.get("translation", (0, 0, 0))
    rotation = Rotation.from_quat(node.get("rotation", (0, 0, 0, 1)))
    out[:3, :3] = rotation.as_matrix() @ np.diag(node.get("scale", (1, 1, 1)))
    return out


def read_rig(path):
    glb = Glb(path)
    nodes = glb.doc["nodes"]
    parents = {j: i for i, n in enumerate(nodes) for j in n.get("children", [])}
    slots = {b["bone"]: b["node"] for b in glb.vrm["humanoid"]["humanBones"]}
    labels = {i: name for name, i in slots.items()}
    world = {}

    def transform(i):
        if i not in world:
            local = pose_matrix(nodes[i])
            world[i] = transform(parents[i]) @ local if i in parents else local
        return world[i]

    rig = {slot: (labels[parents[slots[slot]]], pose_matrix(nodes[slots[slot]])) for slot in JOINTS}
    points = {slot: [] for slot in JOINTS[2:]}
    first_person = glb.vrm["firstPerson"]
    head_inv = np.linalg.inv(transform(slots["head"]))
    for node in nodes:
        if "skin" not in node or "mesh" not in node:
            continue
        skin = glb.doc["skins"][node["skin"]]
        if not any(slots[eye] in skin["joints"] for eye in points):
            continue
        inverse = glb.array(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
        bones = np.array([head_inv @ transform(i) @ inv for i, inv in zip(skin["joints"], inverse)])
        joint_ids = np.asarray(skin["joints"])
        for prim in glb.doc["meshes"][node["mesh"]]["primitives"]:
            attr = prim["attributes"]
            coords = glb.array(attr["POSITION"])
            homogeneous = np.column_stack((coords, np.ones(len(coords))))
            joints = glb.array(attr["JOINTS_0"]).astype(int)
            weights = glb.array(attr["WEIGHTS_0"]).astype(float)
            weights /= weights.sum(axis=1, keepdims=True)
            posed = np.einsum("nvij,nj,nv->ni", bones[joints], homogeneous, weights)[:, :3]
            for slot in points:
                mask = ((joint_ids[joints] == slots[slot])*weights).sum(axis=1) > .45
                points[slot].extend(posed[mask])
    points = {eye: np.unique(np.round(xyz, 7), axis=0) for eye, xyz in points.items()}
    if any(len(xyz) < 8 for xyz in points.values()):
        raise ValueError(f"Missing eye geometry: {path}")
    return sha(glb.data), rig, points, {"jawMapped": "jaw" in slots, "lookAt": first_person.get("lookAtTypeName")}


def compare(model, reference):
    digest, rig, eyes, props = model
    result = {"sha256": digest, **props, "joints": {}, "eyes": {}}
    for slot in JOINTS:
        parent, m = rig[slot]
        ref_parent, ref_m = reference[1][slot]
        result["joints"][slot] = dict(parent=parent, matchesParent=parent==ref_parent,
            parentTranslationMM=(m[:3, 3]*1000).tolist(),
            restTranslationErrorMM=float(np.linalg.norm(m[:3, 3]-ref_m[:3, 3])*1000),
            maxAxisOrScaleDifference=float(np.max(abs(m[:3, :3]-ref_m[:3, :3]))))
    for eye, pts in eyes.items():
        other = reference[2][eye]
        forward = cKDTree(other).query(pts)[0]
        reverse = cKDTree(pts).query(other)[0]
        result["eyes"][eye] = dict(uniqueWeightedPositions=len(pts), referencePositions=len(other),
            maxBidirectionalDistanceMM=float(max(forward.max(), reverse.max())*1000))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE/"face-rig-reference.json")
    parser.add_argument("--measure-only", action="store_true", help="Record a previous revision with known differences")
    args = parser.parse_args()
    root = HERE.parents[3]
    manifest = json.loads((HERE.parent/"style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    refs = {s["id"]:read_rig(root/s["source"]) for s in manifest}
    if any(refs[s["id"]][0] != s["sha256"] for s in manifest):
        raise ValueError("Reference VRM differs from the project manifest")
    candidates = {n:read_rig(HERE.parent.parent/f"Corefolder-{n}/Modeling/Corefolder-{n}.vrm") for n in TARGET_IDS}
    output = {"reference":4, "coordinateSystem":"glTF metres, joint rest local to physical parent; each eye surface "
        "evaluated with joint rest and inverse bind matrices in the head frame; duplicated UV seam points deduplicated.",
        "references":{n:compare(refs[n], refs[4]) for n in REFERENCE_IDS},
        "candidates":{n:compare(model, refs[4]) for n,model in candidates.items()}}
    args.out.write_text(json.dumps(output, indent=2)+"\n", encoding="utf8")
    for n, record in output["candidates"].items():
        joint = max(v["restTranslationErrorMM"] for v in record["joints"].values())
        eye = max(v["maxBidirectionalDistanceMM"] for v in record["eyes"].values())
        axes = max(v["maxAxisOrScaleDifference"] for v in record["joints"].values())
        print(f"#{n}: joint {joint:.5f} mm; eye geometry {eye:.5f} mm; axes {axes:.8f}")
        if not args.measure_only and (joint>.01 or eye>.01 or axes>1e-5 or record["jawMapped"] or
                                     not all(v["matchesParent"] for v in record["joints"].values())):
            raise ValueError(f"Face rig differs from reference #4: #{n}")


if __name__ == "__main__":
    main()
