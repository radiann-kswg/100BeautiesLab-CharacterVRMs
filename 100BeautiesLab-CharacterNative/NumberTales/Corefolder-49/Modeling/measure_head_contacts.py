"""Count visible contacts among independently authored head meshes on a 2 mm grid."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri


def inspect(path, yaw):
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    graph=bpy.context.evaluated_depsgraph_get()
    heads=[]
    scene_verts=[]
    scene_faces=[]
    for source in bpy.context.scene.objects:
        if source.type!='MESH' or source.hide_render:continue
        ob=source.evaluated_get(graph)
        m=ob.to_mesh()
        verts=[ob.matrix_world@v.co for v in m.vertices]
        m.calc_loop_triangles()
        faces=[tuple(p.vertices) for p in m.loop_triangles]
        offset=len(scene_verts)
        scene_faces.extend(tuple(i+offset for i in p) for p in faces)
        scene_verts.extend(verts)
        ob.to_mesh_clear()
        if source.name.lower().startswith(('hair','fox ear','ice blue ear','ivory ear','cheek','face')):
            heads.append((source.name,verts,faces,BVHTree.FromPolygons(verts,faces,all_triangles=True)))
    scene=BVHTree.FromPolygons(scene_verts,scene_faces,all_triangles=True)
    angles=(0,yaw,90,-90,180)
    directions=[Vector((math.sin(math.radians(a)),-math.cos(math.radians(a)),0)) for a in angles]

    def visible(p):
        for direction in directions:
            depth=scene.ray_cast(p+direction*1.5,-direction,1.501)[3]
            if depth is None or depth>=1.4985:return True
        return False

    def edge_hits(a,b):
        hits=[]
        for i,p in enumerate(a):
            delta=a[(i+1)%3]-p
            if delta.length<1e-7:continue
            hit=intersect_ray_tri(*b,delta.normalized(),p,True)
            if hit is not None and (hit-p).length<=delta.length+.000001:
                hits.append(hit)
        return hits

    results={}
    totals=Counter()
    for k,(an,av,af,at) in enumerate(heads):
        for bn,bv,bf,bt in heads[k+1:]:
            collided=at.overlap(bt)
            cells=set()
            near=set()
            for i,j in collided:
                a=[av[v] for v in af[i]]
                b=[bv[v] for v in bf[j]]
                hits=edge_hits(a,b)+edge_hits(b,a)
                if len(hits)<2:continue
                p=sum(hits,Vector())/len(hits)
                if p.z>.68 and visible(p):
                    cells.add(tuple(round(v/.002) for v in p))
            # Include close surfaces even when no triangle crosses its neighbor.
            for source,tree in ((av,bt),(bv,at)):
                for vertex in source:
                    if vertex.z<=.68:continue
                    hit,normal,j,d=tree.find_nearest(vertex,.0009)
                    if hit is not None and visible(vertex):
                        near.add(tuple(round(v/.002) for v in vertex))
            if collided or near:
                info={'crossing_tri_pairs':len(collided),'visible_crossing_cells':len(cells),
                      'visible_near_cells':len(near)}
                results[f'{an} / {bn}']=info
                totals.update(info)
    return {'source_blend':path.name,'yaw_degrees':angles,'totals':dict(totals),
            'pairs':dict(sorted(results.items(),key=lambda kv:-kv[1]['visible_crossing_cells']))}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('blend',type=Path);p.add_argument('out',type=Path);p.add_argument('yaw',type=float)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    a.out.write_text(json.dumps(inspect(a.blend,a.yaw),indent=2)+'\n',encoding='utf8')
