"""A continuous hair cap with an independently editable hem and painted part lines."""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def make_crown(sculpt,name,angles,rows,surface,material,under,ears=()):
    from model_49 import bind
    face=bpy.data.objects['Face']
    tree=BVHTree.FromObject(face,bpy.context.evaluated_depsgraph_get())
    verts=[surface(0.,0.)]
    uv=[(.5,0.)]
    faces=[]
    count=len(angles)
    for i in range(1,rows+1):
        t=i/rows
        for a in angles:
            p=Vector(surface(a,t))
            if abs(a)<1.36 and p.z<1.037:
                hit=tree.ray_cast(Vector((p.x,-1.3,p.z)),Vector((0,1,0)),2)[0]
                if hit is not None:p.y=min(p.y,hit.y-.006)
            verts.append(p)
            uv.append((.5+a/math.tau,t))
    openings=[]
    for sign,tip,earmat in ears:
        cols=[j for j,a in enumerate(angles) if .70<=sign*a<=2.55]
        first,last=min(cols),max(cols)
        top,bottom=3,11
        index=lambda i,j:1+(i-1)*count+j
        perimeter=([index(top,j) for j in range(first,last)]
                   +[index(i,last) for i in range(top,bottom)]
                   +[index(bottom,j) for j in range(last,first,-1)]
                   +[index(i,first) for i in range(bottom,top,-1)])
        openings.append((first,last,top,bottom,perimeter,sign,Vector(tip),earmat))
    for j in range(count):
        k=(j+1)%count
        faces.append((0,1+j,1+k))
        for i in range(rows-1):
            if any(a<=j<b and top<=i+1<bottom for a,b,top,bottom,*_ in openings):continue
            a=1+i*count
            faces.append((a+j,a+k,a+count+k,a+count+j))
    rim=1+(rows-1)*count
    for j in range(count):
        p=verts[rim+j].copy()
        # Roll only the edge into the scalp, without a transverse cap over
        # the forehead or a fan of hidden triangles across the face.
        p.x*=.976;p.y=-.061+(p.y+.061)*.973;p.z+=.004
        verts.append(p);uv.append(uv[rim+j])
    first_inside=len(faces)
    for j in range(count):
        k=(j+1)%count
        faces.append((rim+j,rim+k,rim+count+k,rim+count+j))
    first_ear=len(faces)
    ear_faces=[]
    for _,_,_,_,perimeter,sign,tip,earmat in openings:
        base=[verts[k] for k in perimeter]
        center=sum(base,Vector())/len(base)
        longitudes=[(.5+math.atan2((p.y-center.y)/.130,sign*(p.x-center.x)/.093)/math.tau)%1 for p in base]
        prev=perimeter
        for level in range(1,10):
            t=level/10
            ring=[]
            for j,p in enumerate(base):
                q=p.lerp(tip,t)
                q.x+=sign*.033*math.sin(math.pi*t)
                q.y-=.010*math.sin(math.pi*t)
                ring.append(len(verts));verts.append(q);uv.append((0,0))
            for j,u in enumerate(longitudes):
                k=(j+1)%len(prev);v=longitudes[k]
                faces.append((prev[j],prev[k],ring[k],ring[j]))
                ear_faces.append((earmat,[(u,t-.1),(v,t-.1),(v,t),(u,t)]))
            prev=ring
        apex=len(verts);verts.append(tip);uv.append((0,0))
        for j,u in enumerate(longitudes):
            k=(j+1)%len(prev);v=longitudes[k]
            faces.append((prev[j],prev[k],apex))
            ear_faces.append((earmat,[(u,.9),(v,.9),(u,1)]))
    ob=sculpt.mesh(name,verts,faces,material)
    ob.data.materials.append(under)
    for _,_,earmat in ears:ob.data.materials.append(earmat)
    layer=ob.data.uv_layers.new(name='Crown lay')
    for p in ob.data.polygons:
        coords=[uv[i] for i in p.vertices]
        if p.index>=first_ear:
            mat,ear_uv=ear_faces[p.index-first_ear]
            p.material_index=ob.data.materials.find(mat.name)
            # mesh() may reverse the polygon to fix its winding.
            lookup=dict(zip(faces[p.index],ear_uv))
            coords=[(lookup[i][0],1-lookup[i][1]) for i in p.vertices]
        elif p.index>=first_inside:p.material_index=1
        crosses=max(x for x,t in coords)-min(x for x,t in coords)>.5
        for idx,(x,t) in zip(p.loop_indices,coords):
            layer.data[idx].uv=(x+1 if crosses and x<.5 else x,1-t)
    bind(ob,sculpt.arm)
    return ob
