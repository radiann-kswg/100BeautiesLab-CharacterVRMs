"""Extract the unadorned torso and rear-head profiles from the real reference VRMs."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(HERE/"production-review"))
from check_head_contacts import islands


def primary(obj, torso=False):
    m = obj.data
    m.calc_loop_triangles()
    p = np.array([obj.matrix_world @ v.co for v in m.vertices],dtype=float)
    triangles = np.array([t.vertices[:] for t in m.loop_triangles])
    possible = []
    for faces in islands(p,triangles):
        verts = p[np.unique(faces)]
        if torso and verts[:,2].min()>.04:
            continue
        possible.append((len(faces),faces))
    faces = max(possible,key=lambda i:i[0])[1]
    ids = np.unique(faces)
    return p[ids],np.searchsorted(ids,faces)


def rim_data():
    source = HERE.parent/"Corefolder-4/VRCModel_CoreFloder-4.blend"
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    obj = bpy.data.objects["Face"]
    from collections import Counter, defaultdict
    counts = Counter(edge for poly in obj.data.polygons for edge in poly.edge_keys)
    adj = defaultdict(list)
    for (a,b),count in counts.items():
        if count==1:
            adj[a].append(b)
            adj[b].append(a)
    ring = [242]
    previous = -1
    while True:
        current = ring[-1]
        nxt = next(x for x in adj[current] if x!=previous)
        if nxt==ring[0]:
            break
        previous = current
        ring.append(nxt)
    assert len(ring)==34
    return ring,np.array([obj.matrix_world@obj.data.vertices[i].co for i in ring],dtype=float)


def smooth_crown(rows, pole):
    """Fit the upper dome through the reference samples, excluding individual ear sockets."""
    points = np.array(rows)
    center_z = (points[0,:,2].min() + points[0,:,2].max()) / 2
    # The midline and broadest lateral meridians run between the donor ears.
    # Fit their squared radii as quadratics that close at the measured rear pole.
    crown = np.argmax(points[0,:,2])
    side = np.argmax(points[0,:,0])
    def meridian(column, axis, origin):
        samples = points[2:,column]
        depth = pole[1]-samples[:,1]
        design = np.column_stack((depth, depth*depth))
        return np.linalg.lstsq(design,(samples[:,axis]-origin)**2,rcond=None)[0]
    lateral = meridian(side,0,0)
    vertical = meridian(crown,2,center_z)
    def radius(y,dx,dz):
        depth = pole[1]-y
        squared = np.maximum(np.array((lateral,vertical)) @ [depth,depth*depth],.0001)
        return 1/np.sqrt(dx*dx/squared[0]+dz*dz/squared[1])
    for j,(rx,ry,rz) in enumerate(points[0]):
        length = np.hypot(rx,rz-center_z)
        dx,dz = rx/length,(rz-center_z)/length
        # Leave the fitted temples, lower scalp and chest joint exactly as sampled.
        blend = np.clip((dz-.22)/.35,0,1)
        blend = blend*blend*(3-2*blend)
        if blend==0:
            continue
        start_offset = length-radius(ry,dx,dz)
        for row in points[1:]:
            x,y,z = row[j]
            t = (y-ry)/(pole[1]-ry)
            # Taper the measured facial edge into the dome and keep the measured pole.
            fade = max(0,1-t/.44)**2
            end = np.clip((1-t)/.15,0,1)
            end = end*end*(3-2*end)
            r = radius(y,dx,dz)+start_offset*fade
            row[j,0] += blend*end*(r*dx-x)
            row[j,2] += blend*end*(center_z+r*dz-z)
    return points


def main():
    rim_ids,rim = rim_data()
    ref = json.loads((HERE/"style-training/source-vrms.json").read_text(encoding="utf-8-sig"))
    trees,posterior,hashes = [],[],{}
    body = None
    for n in (4,25,93):
        r = next(r for r in ref if r["id"]==n)
        path = ROOT/r["source"]
        hashes[n] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashes[n]==r["sha256"]
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.ops.wm.vrm_license_warning(import_anyway=True,filepath=str(path),
                        extract_textures_into_folder=False,enable_mtoon_outline_preview=False)
        graph = bpy.context.evaluated_depsgraph_get()
        meshes = [o for o in bpy.context.scene.objects if o.type=="MESH"]
        if n==4:
            torso,faces = primary(next(o for o in meshes if o.name.lower().startswith("body")).evaluated_get(graph),True)
            body = np.unique(np.round(torso,6),axis=0)
            torso_tree = BVHTree.FromPolygons(torso.tolist(),faces.tolist(),all_triangles=True)
            assert len(faces)==2152 and len(body)==1078,(len(faces),len(body))
        node = next(o for o in meshes if o.name.lower().startswith("hair" if n==4 else "face"))
        points,faces = primary(node.evaluated_get(graph))
        posterior.append(points[points[:,1].argmax()])
        trees.append(BVHTree.FromPolygons(points.tolist(),faces.tolist(),all_triangles=True))
    pole = np.median(posterior,axis=0)
    base_z = (rim[:,2].min()+rim[:,2].max())/2
    rows = [rim]
    # From the original 34-point face opening, trace successive sections of
    # the common scalp. The innermost reference surface rejects projecting
    # fringes and ears unique to one reference. Character ears stay independent.
    for t in (.09,.18,.29,.41,.53,.64,.74,.83,.90,.95,.98):
        ring = []
        for x,y,z in rim:
            y += (pole[1]-y)*t
            center = Vector((0,y,base_z*(1-t)+pole[2]*t))
            direction = Vector((x,0,z-base_z)).normalized()
            hits = [tree.ray_cast(center,direction,.55) for tree in trees]
            radii = [dist for hit,_,_,dist in hits if hit is not None]
            if not radii:
                # The reference skull is open on its underside where it enters
                # the body. Seat this hidden bridge against the actual #4 chest.
                hit,_,_,dist = torso_tree.ray_cast(center,direction,.60)
                if hit is None:
                    raise ValueError(f"No reference scalp or torso at {center}, {direction}")
                radii = [dist+.004]
            ref_point = np.array(center+direction*min(radii))
            if t < .19:
                # Meet the exact facial rim smoothly even where the donor's
                # fringe terminates several millimetres above the neutral face.
                h = min(t/.19,1.)
                ref_point[[0,2]] = (1-h)*np.array([x,z])+h*ref_point[[0,2]]
            ring.append(ref_point)
        rows.append(np.asarray(ring))
    rows = smooth_crown(rows,pole)
    data = {"source_vrm_sha256":hashes,"source_native_face":"Corefolder-4/VRCModel_CoreFloder-4.blend",
            "method":"Actual #4 naked body island (2,152 triangles). #4 facial rim, successive transverse "
                     "sections of #4/#25/#93 scalp at their shared neutral pose. A symmetric quadratic fit "
                     "smooths individual sockets on the upper dome while preserving the face boundary. Character ears, fringe, "
                     "clothing and pendants are authored independently.","rim":rim_ids,
            "head_rows":np.round(np.array(rows),6).tolist(),"head_pole":np.round(pole,6).tolist(),
            "body_points":body.tolist()}
    (HERE/"canonical-core-envelope.json").write_text(json.dumps(data,separators=(",",":"))+"\n",encoding="utf8")
    print("Core extracted",len(body),np.min(rows,axis=(0,1)),np.max(rows,axis=(0,1)),pole,flush=True)


if __name__=="__main__":
    main()
