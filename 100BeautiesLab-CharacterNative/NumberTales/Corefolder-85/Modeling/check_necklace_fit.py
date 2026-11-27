"""Measure the silver cord against the bare character surfaces in the editable blend."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def measure(path):
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    graph=bpy.context.evaluated_depsgraph_get()
    supports={n:BVHTree.FromObject(bpy.data.objects[n],graph)
              for n in ('Body','Face','Corefolder Cranial Base') if bpy.data.objects.get(n)}
    cord=bpy.data.objects['Necklace | fitted silver cord'].evaluated_get(graph)
    mesh=cord.data
    samples=[v.co.copy() for v in mesh.vertices]
    samples.extend((mesh.vertices[e.vertices[0]].co+mesh.vertices[e.vertices[1]].co)*.5 for e in mesh.edges)
    gaps=[];rear=[]
    for p in samples:
        radial=Vector((p.x,p.y+.046,0)).normalized()
        hits=[]
        for name,tree in supports.items():
            q,_,_,dist=tree.ray_cast(p+radial,-radial,1.4)
            if q is not None:hits.append((dist,name,q))
        dist,name,q=min(hits,key=lambda h:h[0])
        absolute=min(tree.find_nearest(p)[3] for tree in supports.values())
        gap=1000*absolute*(1 if (p-q).dot(radial)>=0 else -1)
        gaps.append(gap)
        if p.y>0:rear.append(gap)
    def summary(values):
        return {'min_mm':round(float(min(values)),3),'median_mm':round(float(np.median(values)),3),
                'max_mm':round(float(max(values)),3),'inside_over_0.5mm':int(sum(v<-.5 for v in values))}
    return {'support_meshes':list(supports),'cord_rings':96,'samples':len(gaps),'all':summary(gaps),'rear':summary(rear)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('blend',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    d=measure(a.blend);a.out.write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')
    print('NECKLACE',d)
