"""Measure transverse intersection lines between separate exterior head islands in actual VRMs.

Run inside Blender with -- --out file.json [--candidates directory]. A candidates
directory contains Corefolder-N/Corefolder-N.vrm. All measurements are in rest pose.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ANGLES = (0, -30, 30, -90, 90, 180)


def islands(points, triangles):
    _, weld = np.unique(np.round(points,5),axis=0,return_inverse=True)
    edges = np.concatenate((triangles[:,[0,1]],triangles[:,[1,2]],triangles[:,[2,0]]))
    neighbors = [set() for _ in range(weld.max()+1)]
    for a,b in weld[edges]:
        neighbors[a].add(b)
        neighbors[b].add(a)
    labels = np.full(len(neighbors),-1)
    for seed in range(len(neighbors)):
        if labels[seed] >= 0:
            continue
        labels[seed] = seed
        todo = [seed]
        while todo:
            for i in neighbors[todo.pop()]:
                if labels[i] < 0:
                    labels[i] = seed
                    todo.append(i)
    component = labels[weld[triangles[:,0]]]
    for label in np.unique(component):
        yield triangles[component==label]


def cut_segments(a, b):
    """Intersection of each pair of non-coplanar triangles, with positive interior overlap."""
    def planes(tri):
        n = np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1.e-15)
    na, nb = planes(a), planes(b)
    line = np.cross(na,nb)
    sine = np.linalg.norm(line,axis=1)
    line /= np.maximum(sine[:,None],1.e-15)
    da = np.einsum("nki,ni->nk",a-b[:,:1],nb)
    db = np.einsum("nki,ni->nk",b-a[:,:1],na)
    # Require vertices on both sides of each plane. Touching edges and shallow tangencies are excluded.
    keep = ((sine>.10)&(da.max(1)>.00002)&(da.min(1)<-.00002)&
            (db.max(1)>.00002)&(db.min(1)<-.00002))
    if not keep.any():
        return []
    a,b,da,db,line = a[keep],b[keep],da[keep],db[keep],line[keep]
    def interval(tri, distances):
        q = np.roll(tri,-1,axis=1)
        end = np.roll(distances,-1,axis=1)
        valid = distances*end <= 0
        denom = distances-end
        denom[np.abs(denom)<1.e-15] = 1.
        cross = tri+(q-tri)*(distances/denom)[:,:,None]
        loc = np.einsum("nki,ni->nk",cross,line)
        low = np.argmin(np.where(valid,loc,np.inf),axis=1)
        return loc[np.arange(len(loc)),low],np.max(np.where(valid,loc,-np.inf),axis=1),cross[np.arange(len(loc)),low]
    alo,ahi,origin = interval(a,da)
    blo,bhi,_ = interval(b,db)
    low,high = np.maximum(alo,blo),np.minimum(ahi,bhi)
    ok = high-low > .00012
    start = origin+(low-alo)[:,None]*line
    return zip(start[ok],line[ok],(high-low)[ok])


def head_masks(parts, destination):
    triangles = np.concatenate([part[2] for part in parts])
    points = triangles.reshape(-1,3)
    tree = BVHTree.FromPolygons(points.tolist(),np.arange(len(points)).reshape(-1,3).tolist(),all_triangles=True)
    # One world origin and pixel scale for all ten characters. Remove the tails
    # and body, which otherwise enter the head silhouette from behind.
    width,height,pitch = 284,228,.0045
    masks = {}
    for angle in (0,30,90):
        theta = math.radians(angle)
        ray = np.array([math.sin(theta),-math.cos(theta),0.])
        right = np.array([-ray[1],ray[0],0.])
        forward = Vector(-ray)
        u = (np.arange(width)+.5-width/2)*pitch
        columns = u[:,None]*right+np.array([0.,-.10,0.])+2*ray
        mask = np.zeros((height,width),dtype=bool)
        for row in range(height):
            z = .97+(height/2-row-.5)*pitch
            for col,(x,y,_) in enumerate(columns):
                mask[row,col] = tree.ray_cast(Vector((x,y,z)),forward,3.)[0] is not None
        masks[str(angle)] = mask
    destination.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(destination,**masks)


def inspect(path,mask_path=None,masks_only=False):
    bpy.ops.wm.read_homefile(use_empty=True)
    result = bpy.ops.wm.vrm_license_warning(import_anyway=True, filepath=str(path),
                  extract_textures_into_folder=False,enable_mtoon_outline_preview=False)
    if result != {"FINISHED"}:
        raise ValueError(path)
    graph = bpy.context.evaluated_depsgraph_get()
    parts, all_points, all_faces = [], [], []
    offset = 0
    for obj in sorted(bpy.context.scene.objects,key=lambda o:o.name):
        if obj.type != "MESH" or obj.hide_render:
            continue
        obj = obj.evaluated_get(graph)
        mesh = obj.data
        mesh.calc_loop_triangles()
        vertices = np.asarray([obj.matrix_world@v.co for v in mesh.vertices])
        faces = np.asarray([t.vertices[:] for t in mesh.loop_triangles])
        all_points.append(vertices)
        all_faces.append(faces+offset)
        offset += len(vertices)
        if obj.name.lower().startswith("tail"):
            continue
        eye_groups = {g.index for g in obj.vertex_groups if "eye" in g.name.lower()}
        eye = np.array([any(g.group in eye_groups and g.weight>.4 for g in v.groups) for v in mesh.vertices])
        for subset in islands(vertices,faces):
            ids = np.unique(subset)
            p = vertices[ids]
            size = np.ptp(p,axis=0)
            if (len(ids)<12 or max(size)<.055 or min(size)<.003 or np.mean(eye[ids])>.45 or
                    p[:,2].max()<.80 or p[:,2].mean()<.72 or p[:,2].min()<.35):
                continue
            index = np.searchsorted(ids,subset)
            tree = BVHTree.FromPolygons(p.tolist(),index.tolist(),all_triangles=True)
            materials = sorted({mesh.materials[mesh.loop_triangles[j].material_index].name
                                for j in [int(np.flatnonzero((faces==subset[0]).all(1))[0])] if mesh.materials})
            parts.append((f"{obj.name}/{len(parts)}",",".join(materials),p[index],tree))
    if mask_path:
        head_masks(parts,mask_path)
    if masks_only:
        return {}
    occluder = BVHTree.FromPolygons(np.concatenate(all_points).tolist(),np.concatenate(all_faces).tolist(),all_triangles=True)
    directions = [np.array([math.sin(math.radians(y)),-math.cos(math.radians(y)),0.]) for y in ANGLES]
    pairs = []
    lengths = np.zeros(len(ANGLES))
    self_lengths = np.zeros(len(ANGLES))
    for i,(name,mat,a,ta) in enumerate(parts):
        for other,mat2,b,tb in parts[i:]:
            hits = ta.overlap(tb)
            if not hits:
                continue
            x,y = np.asarray(hits).T
            same = name == other
            if same:
                # A welded crown can still turn into itself. Test non-neighbours
                # as well as disconnected hair/ear/face islands on identical terms.
                chosen = x<y
                x,y = x[chosen],y[chosen]
                aa,bb = a[x],b[y]
                shared = np.any(np.max(np.abs(aa[:,:,None,:]-bb[:,None,:,:]),axis=3)<.00001,axis=(1,2))
                x,y = x[~shared],y[~shared]
                if not len(x):
                    continue
            contact = 0.
            visible = np.zeros(len(ANGLES))
            for start,direction,length in cut_segments(a[x],b[y]):
                contact += length
                # Short, equally spaced pieces remove the long-triangle bias at hairline occlusion boundaries.
                count = max(1,int(np.ceil(length/.003)))
                for t in (np.arange(count)+.5)/count:
                    location = start+direction*(length*t)
                    for k,ray in enumerate(directions):
                        hit,_,_,dist = occluder.ray_cast(Vector(location+ray*2),Vector(-ray),2.002)
                        if hit is not None and abs(dist-2.)<=.001:
                            visible[k] += length/count * math.sqrt(max(0.,1-(direction@ray)**2))
            if contact:
                if same:
                    self_lengths += visible
                else:
                    lengths += visible
                pairs.append({"parts":[name,other],"same_island":same,"first_materials":[mat,mat2],
                              "line_mm":round(float(contact)*1000,2),"projected_visible_mm":(visible*1000).round(2).tolist()})
    return {"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"islands":len(parts),
            "pairs":sorted(pairs,key=lambda row:max(row["projected_visible_mm"]),reverse=True),
            "visible_mm":(lengths*1000).round(2).tolist(),"self_visible_mm":(self_lengths*1000).round(2).tolist(),
            "total_visible_mm":((lengths+self_lengths)*1000).round(2).tolist()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--mask-dir",type=Path,help="Also render head-only orthographic masks at 4.5 mm/px.")
    parser.add_argument("--masks-only",action="store_true")
    parser.add_argument("--candidates",type=Path)
    parser.add_argument("--references",type=Path,help="Reuse independently measured canonical records by SHA.")
    parser.add_argument("--only",nargs=2,metavar=("NUMBER","VRM"),help="Inspect one temporary candidate.")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    if args.masks_only and not args.mask_dir:
        parser.error("--masks-only needs --mask-dir")
    if not args.masks_only and not args.out:
        parser.error("Supply --out for the intersection report")
    refs = json.loads((HERE.parent/"style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    paths = {str(ref["id"]):ROOT/ref["source"] for ref in refs}
    targets = (6,49,57,85)
    paths.update({str(n):(args.candidates/f"Corefolder-{n}/Corefolder-{n}.vrm" if args.candidates else
                       HERE.parents[1]/f"Corefolder-{n}/Modeling/Corefolder-{n}.vrm") for n in targets})
    if args.only:
        paths = {args.only[0]:Path(args.only[1])}
    saved = json.loads(args.references.read_text())["models"] if args.references else {}
    models = {}
    for key,path in paths.items():
        mask = args.mask_dir/f"{key}.npz" if args.mask_dir else None
        if (not args.masks_only and (not mask or mask.exists()) and int(key) not in targets and key in saved and "self_visible_mm" in saved[key] and
                saved[key]["sha256"]==hashlib.sha256(path.read_bytes()).hexdigest()):
            models[key] = saved[key]
        else:
            models[key] = inspect(path.resolve(),mask,args.masks_only)
        if not args.masks_only:
            print("HEAD CONTACTS",key,models[key]["visible_mm"],flush=True)
    if args.masks_only:
        return
    args.out.write_text(json.dumps({"yaw_degrees":ANGLES,"units":"millimetres of projected intersection line",
        "method":"Neutral reimport. Independent welded head-region islands, min extent 3 mm, max extent >=55 mm. "
                 "Exclude eye-weighted components, tails, small decals, exact contacts and grazing angles <5.7 degrees. "
                 "For true triangle crossings, sample every 3 mm or less. Visible if the first two-sided scene ray "
                 "is within 1 mm. Materials and alpha clipping are ignored. Internal seams are retained separately. "
                 "Non-neighbour triangle crossings inside each selected island are reported separately and in the total. "
                 "Shared-vertex neighbours, very small facial components and alpha visibility are outside this measure.",
        "models":models},indent=2,ensure_ascii=False)+"\n",encoding="utf8")


if __name__ == "__main__":
    main()
