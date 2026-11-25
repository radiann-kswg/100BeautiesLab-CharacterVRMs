"""Compare actual neutral VRM torso surfaces with the evaluated common Blender base."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT / "100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend"
TARGETS = (6,49,57,85)
LEVELS_MM = np.arange(10,701,10)
AXES = np.column_stack((np.cos(np.arange(16)*np.pi/8), np.sin(np.arange(16)*np.pi/8)))


def section_data(vertices, triangles):
    # Mat boundaries and UV seams duplicate export vertices. Recover connectivity at 10 µm.
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    _, index, weld = np.unique(np.round(vertices,5), axis=0, return_index=True, return_inverse=True)
    points = vertices[index]
    triangles = weld[triangles]
    edges = np.unique(np.sort(np.concatenate((triangles[:,[0,1]],triangles[:,[1,2]],triangles[:,[2,0]])),
                              axis=1), axis=0)
    graph = coo_matrix((np.ones(len(edges)), (edges[:,0],edges[:,1])),shape=(len(points),len(points)))
    count, groups = connected_components(graph, directed=False)
    # Several originals put a collar or separate garment in the Body renderer.
    # Select the near-floor, rounded, torso-only component by its three world extents.
    scored = []
    for i in range(count):
        sub = points[groups==i]
        span = np.ptp(sub, axis=0)
        if sub[:,2].min() < .06 and .52 < span[2] < .84 and min(span[:2]) > .55:
            scored.append((np.linalg.norm(span-[.855,.875,.712]),i))
    if not scored:
        raise ValueError("No ground-reaching original torso in the Body nodes")
    _, torso = min(scored)
    mask = groups==torso
    points_in = points[mask]
    start,end = points[edges[mask[edges[:,0]]]].transpose(1,0,2)
    result = []
    for mm in LEVELS_MM:
        z = mm/1000
        selected = (start[:,2] <= z) != (end[:,2] <= z)
        a,b = start[selected],end[selected]
        if not len(a):
            raise ValueError(f"Missing section at {mm} mm")
        cross = a + (b-a)*((z-a[:,2])/(b[:,2]-a[:,2]))[:,None]
        support = np.max(cross[:,:2]@AXES.T,axis=0)*1000
        result.append(np.round(support,3).tolist())
    return {"dimensions_mm":np.round(1000*np.ptp(points_in,axis=0),3).tolist(),
            "floor_mm":round(float(points_in[:,2].min())*1000,3),"support_mm":result}


def frozen_vrm(path):
    from check_exported_face_rig import Glb, pose_matrix

    glb = Glb(path)
    nodes = glb.doc["nodes"]
    parents = {c:i for i,n in enumerate(nodes) for c in n.get("children",[])}
    world = {}
    def matrix(i):
        if i not in world:
            m = pose_matrix(nodes[i])
            world[i] = matrix(parents[i]) @ m if i in parents else m
        return world[i]
    chunks, triangles, offset = [], [], 0
    for i,node in enumerate(nodes):
        if not (node.get("name","").lower().startswith("body") and "mesh" in node):
            continue
        skin = glb.doc["skins"][node["skin"]]
        inverse = glb.array(skin["inverseBindMatrices"]).reshape(-1,4,4).transpose(0,2,1)
        bones = np.array([matrix(j)@mat for j,mat in zip(skin["joints"],inverse)])
        for prim in glb.doc["meshes"][node["mesh"]]["primitives"]:
            attr = prim["attributes"]
            p = glb.array(attr["POSITION"])
            joints = glb.array(attr["JOINTS_0"]).astype(int)
            weights = glb.array(attr["WEIGHTS_0"]).astype(float)
            weights /= weights.sum(axis=1,keepdims=True)
            xyz = np.einsum("nvij,nj,nv->ni",bones[joints],np.column_stack((p,np.ones(len(p)))),weights)
            chunks.append(xyz[:,[0,2,1]])
            triangles.append(glb.array(prim["indices"]).reshape(-1,3).astype(int)+offset)
            offset += len(p)
    return section_data(np.concatenate(chunks),np.concatenate(triangles))


def base_mesh(out):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(BASE),use_scripts=False)
    obj = bpy.data.objects["body"].evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = obj.data
    mesh.calc_loop_triangles()
    np.savez(out,vertices=np.array([obj.matrix_world @ v.co for v in mesh.vertices]),
             triangles=np.array([tri.vertices[:] for tri in mesh.loop_triangles]))


def measure(blender, out):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        base_file = Path(tmp)/"basis.npz"
        subprocess.run([str(blender),"-b","--offline-mode","--disable-autoexec","-t","1",
                        "--python-exit-code","1","-P",__file__,"--","--base",str(base_file)],check=True)
        with np.load(base_file) as data:
            records = {"Base":section_data(data["vertices"],data["triangles"])}
    records["Base"]["sha256"] = hashlib.sha256(BASE.read_bytes()).hexdigest()
    manifest = json.loads((HERE.parent/"style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    refs = [str(ref["id"]) for ref in manifest]
    paths = {str(ref["id"]):ROOT/ref["source"] for ref in manifest}
    paths.update({str(n):HERE.parents[1]/f"Corefolder-{n}/Modeling/Corefolder-{n}.vrm" for n in TARGETS})
    for key,path in paths.items():
        records[key] = frozen_vrm(path)
        records[key]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    for ref in manifest:
        if records[str(ref["id"])]["sha256"] != ref["sha256"]:
            raise ValueError("Changed canonical VRM")
    reference = np.median([records[n]["support_mm"] for n in refs],axis=0)
    for row in records.values():
        support = np.asarray(row["support_mm"])
        widths = support[:,:8]+support[:,8:]
        reference_widths = reference[:,:8]+reference[:,8:]
        row["max_width_delta_to_reference_mm"] = np.round(np.abs(widths-reference_widths).max(axis=0),3).tolist()
        row["max_outline_delta_to_reference_mm"] = round(float(abs(support-reference).max()),3)
    out.write_text(json.dumps({"levels_mm":LEVELS_MM.tolist(),"directions_degrees":list(np.arange(16).astype(float)*22.5),
                               "units":"mm, Blender world X and depth, ground at z=0; angular support from origin",
                               "reference_ids":refs,"targets":list(TARGETS),"records":records},
                              ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")


if __name__ == "__main__":
    if "--base" in sys.argv:
        base_mesh(Path(sys.argv[-1]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--blender",required=True,type=Path)
        parser.add_argument("--out",type=Path,default=HERE/"torso-profiles.json")
        args = parser.parse_args()
        measure(args.blender,args.out)
