"""A continuous hair cap with an independently editable hem and painted part lines."""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def make_crown(sculpt,name,angles,rows,surface,material,under,ears=(),cups=()):
    from model_49 import bind
    graph=bpy.context.evaluated_depsgraph_get()
    skins=[BVHTree.FromObject(ob,graph) for ob in sculpt.items
           if ob.name=='Face' or ob.name.startswith('Cheek to nape')]
    base=bpy.data.objects.get('Corefolder Cranial Base')
    skull=BVHTree.FromObject(base,graph) if base else None
    verts=[surface(0.,0.)]
    uv=[(.5,0.)]
    faces=[]
    count=len(angles)
    def fitted_surface(a,t):
        p=Vector(surface(a,t))
        outward=Vector((p.x,p.y+.055,0))
        if outward.length>.02 and p.z<1.057:
            outward.normalize()
            # The sockets wrap around each temple. A camera-axis depth
            # alone leaves white triangles exposed beside the eyelashes.
            outside=p+outward*.65
            clearance=.009 if ears else .006
            delta=0.
            for tree in skins:
                hit=tree.ray_cast(outside,-outward,1.)[0]
                if hit is not None:delta=max(delta,(hit-p).dot(outward)+clearance)
            p+=outward*delta
        if skull is not None:
            lower=bool(ears) and p.z<.895
            radial=Vector((p.x,p.y+.055,0 if lower else p.z-.86)).normalized()
            hit=skull.ray_cast(p+radial*.65,-radial,1.)[0]
            if hit is not None:p+=radial*max(0,(hit-p).dot(radial)+(.015 if lower else .004))
        return p

    for i in range(1,rows+1):
        t=i/rows
        for a in angles:
            verts.append(fitted_surface(a,t))
            uv.append((.5+a/math.tau,t))
    openings=[]
    for sign,tip,earmat in tuple(ears)+tuple((s,None,fn) for s,fn in cups):
        limits=(.70,2.55,3,11) if tip is not None else (.76,1.96,5,rows-1)
        cols=[j for j,a in enumerate(angles) if limits[0]<=sign*a<=limits[1]]
        first,last=min(cols),max(cols)
        top,bottom=limits[2:]
        index=lambda i,j:1+(i-1)*count+j
        perimeter=([index(top,j) for j in range(first,last)]
                   +[index(i,last) for i in range(top,bottom)]
                   +[index(bottom,j) for j in range(last,first,-1)]
                   +[index(i,first) for i in range(bottom,top,-1)])
        openings.append((first,last,top,bottom,perimeter,sign,Vector(tip) if tip is not None else None,earmat))
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
        inset=.990 if ears else .976
        p.x*=inset;p.y=-.061+(p.y+.061)*(inset if ears else .973);p.z+=.002 if ears else .004
        verts.append(p);uv.append(uv[rim+j])
    first_inside=len(faces)
    for j in range(count):
        k=(j+1)%count
        faces.append((rim+j,rim+k,rim+count+k,rim+count+j))
    first_ear=len(faces)
    ear_faces=[]
    for first,last,top,bottom,perimeter,sign,tip,earmat in openings:
        base=[verts[k] for k in perimeter]
        center=sum(base,Vector())/len(base)
        if tip is None:
            prev=perimeter
            # The side elevation of a domed scalp is not a single-valued
            # polar outline near the crown. Its own parametric patch is.
            outline=[]
            for vertex in perimeter:
                row,column=divmod(vertex-1,count)
                dx=sign*(2*(column-first)/(last-first)-1)
                dz=1-2*(row+1-top)/(bottom-top)
                outline.append(math.atan2(dz,dx))
            rings,hub,center_mat=earmat(sign,outline)
            def cup_point(q):
                # Lift the colored ear over its own azimuth/elevation patch.
                # A projection onto a fixed side plane can pass back through
                # the curved forehead behind it.
                u,v,lip=q
                s=u if sign>0 else 1-u
                a=angles[first]+(angles[last]-angles[first])*s
                t=(top+(bottom-top)*v)/rows
                p=fitted_surface(a,t)
                outward=Vector((p.x,p.y+.055,0)).normalized()
                point=u**2.8*(1-v)**1.5
                p.z+=.032*point
                return p+outward*(.020+.210*point+lip)
            for points,mat in rings:
                current=[]
                for q in points:
                    current.append(len(verts));verts.append(cup_point(q));uv.append((0,0))
                for j in range(len(prev)):
                    k=(j+1)%len(prev)
                    faces.append((prev[j],prev[k],current[k],current[j]))
                    ear_faces.append((mat,[(.5,.5)]*4))
                prev=current
            tipidx=len(verts);verts.append(cup_point(hub));uv.append((0,0))
            for j in range(len(prev)):
                faces.append((prev[j],prev[(j+1)%len(prev)],tipidx))
                ear_faces.append((center_mat,[(.5,.5)]*3))
            continue
        longitudes=[(.5+math.atan2((p.y-center.y)/.130,sign*(p.x-center.x)/.093)/math.tau)%1 for p in base]
        prev=perimeter
        for level in range(1,10):
            t=level/10
            ring=[]
            for j,p in enumerate(base):
                q=p.lerp(tip,t)
                q.x+=sign*.011*math.sin(math.pi*t)
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
    for mat,_ in ear_faces:
        if ob.data.materials.find(mat.name)<0:ob.data.materials.append(mat)
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
