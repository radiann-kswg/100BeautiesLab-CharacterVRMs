"""Verify the exported bare torso, posterior scalp, facial seam and removable outfit."""
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from compare_torso_profiles import posed_parts, TARGETS

HERE = Path(__file__).resolve().parent


def separation_mm(a, b):
    return max(cKDTree(b).query(a)[0].max(), cKDTree(a).query(b)[0].max())*1000


def measure(path, rig):
    layers = {"head": [], "face": [], "torso": [], "outfit": []}
    materials = []
    for node,material,vertices,faces in posed_parts(path,("body","face","outfit")):
        points = vertices[np.unique(faces)]
        if material.startswith("Corefolder Cranial Base"):
            assert node=="Body", (path, node)
            layers["head"].append(points)
        elif node=="Body":
            layers["torso"].append(points)
        elif node=="Face":
            layers["face"].append(points)
        elif node=="Outfit":
            layers["outfit"].append(points)
            materials.append(material)
    if not all(layers.values()):
        raise ValueError(f"Missing layer in {path}")
    points = {name:np.concatenate(parts) for name,parts in layers.items()}
    rows = np.array(rig["head_rows"])
    skull = np.vstack((rows.reshape(-1,3),rig["head_pole"]))
    delta = {"body_to_reference_mm":separation_mm(points["torso"], rig["body_points"]),
             "scalp_to_reference_profile_mm":separation_mm(points["head"],skull),
             "facial_seam_gap_mm":cKDTree(points["face"]).query(rows[0])[0].max()*1000}
    if max(delta.values())>.02:
        raise ValueError((path, delta))
    return {"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            **{k:round(float(v),6) for k,v in delta.items()},
            "outfit_materials":materials}


if __name__=="__main__":
    rig = json.loads((HERE.parent/"canonical-core-envelope.json").read_text(encoding="utf8"))
    records = {n:measure(HERE.parents[1]/f"Corefolder-{n}/Modeling/Corefolder-{n}.vrm",rig)
               for n in TARGETS}
    report = {"reference_vrms":rig["source_vrm_sha256"],"method":rig["method"],
              "body_reference_points":len(rig["body_points"]),"face_boundary_vertices":len(rig["rim"]),
              "measurement":"Bidirectional nearest-vertex distances after rest-pose skinning. The face "
                            "seam uses the maximum distance from the reference boundary to the facial mesh. "
                            "The independent Outfit renderer has no base vertices or materials.",
              "models":records}
    (HERE/"core-envelope.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
