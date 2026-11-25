"""Round native tail sections through the forks and overlaps of Yochika's rear atlas."""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
from mathutils.bvhtree import BVHTree
from native_tail_profiles import load_tail
from corefolder_springs import add_spring_chain


def fuse_fork(sculpt, main, fork, material):
    """Round the shared crotch of the two source volumes and reproject the atlas."""
    sculpt.items.remove(fork)
    bpy.ops.object.select_all(action='DESELECT')
    main.select_set(True);fork.select_set(True)
    bpy.context.view_layer.objects.active=main
    bpy.ops.object.join()
    mesh=main.data
    mesh.calc_loop_triangles()
    pos=[v.co.copy() for v in mesh.vertices]
    tri=[p.vertices[:] for p in mesh.loop_triangles]
    layer=mesh.uv_layers.active.data
    tex=[[Vector((*layer[l].uv,0)) for l in p.loops] for p in mesh.loop_triangles]
    tree=BVHTree.FromPolygons(pos,tri,all_triangles=True)
    mesh.remesh_voxel_size=.007
    bpy.ops.object.voxel_remesh()
    bm=bmesh.new();bm.from_mesh(main.data)
    for _ in range(4):
        bmesh.ops.smooth_vert(bm,verts=bm.verts[:],factor=.48,use_axis_x=True,use_axis_y=True,use_axis_z=True)
    bm.to_mesh(main.data);bm.free()
    main.data.calc_loop_triangles()
    dense=[v.co.copy() for v in main.data.vertices]
    normals=[v.normal.copy() for v in main.data.vertices]
    facets=[t.vertices[:] for t in main.data.loop_triangles]
    rounded=BVHTree.FromPolygons(dense,facets,all_triangles=True)
    cut=main.modifiers.new('Fork silhouette density','DECIMATE')
    cut.ratio=min(1,920/max(1,len(main.data.loop_triangles)))
    bpy.ops.object.modifier_apply(modifier=cut.name)
    mesh=main.data
    mesh.materials.clear();mesh.materials.append(material)
    for poly in mesh.polygons:poly.use_smooth=True
    for unused in list(mesh.uv_layers):mesh.uv_layers.remove(unused)
    uv=mesh.uv_layers.new(name='49 continuous fork')
    uv.active_render=True
    coords=[];shading=[]
    for v in mesh.vertices:
        hit,_,i,_=tree.find_nearest(v.co)
        a,b,c=tri[i]
        vtx=barycentric_transform(hit,pos[a],pos[b],pos[c],*tex[i])
        # Store once per vertex. All corners here share the projected atlas.
        coords.append(vtx.xy.copy())
        p,_,f,_=rounded.find_nearest(v.co)
        a,b,c=facets[f]
        shading.append(barycentric_transform(p,dense[a],dense[b],dense[c],normals[a],normals[b],normals[c]).normalized())
    for loop in mesh.loops:uv.data[loop.index].uv=coords[loop.vertex_index]
    mesh.normals_split_custom_set_from_vertices(shading)
    return main


def build_rear(sculpt,data,collider):
    profiles,_,polygons=load_tail()
    w,h=data['size']
    root_px=np.array((266.,242.))
    # Distinct depth layers allow the upper and lower branches to read in profile.
    placement=[('upper inner R',(181,10),.075),('upper inner L',(343,8),.067),
               ('upper outer R',(75,62),-.041),('upper outer L',(451,62),-.035),
               ('low outside R',(7,232),.045),('low outside L',(523,232),.061),
               None,None,('low middle',(268,474),.112)]
    material=sculpt.material('Rear plume atlas','#FFFFFF',texture='Tails-49.png',edge=False)
    material.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon.shade_color_factor=(.97,.97,.97)
    stations=[0,.055,.115,.195,.282,.377,.480,.582,.680,.761,.827,.876,.922,.964,1.]
    for rec,loc in zip(data['plumes'],placement):
        if loc is None:continue
        name,end,layer=loc
        delta=np.array(end)-root_px
        side=np.array((-delta[1],delta[0]))/np.linalg.norm(delta)
        outline=np.array(rec['outline'])-root_px
        along=outline@delta/(delta@delta)
        cross=outline@side
        prev=np.roll(along,1);prev_x=np.roll(cross,1)
        def intervals(s):
            passing=(along>s)!=(prev>s)
            z=along[passing];x=cross[passing]
            v=x+(prev_x[passing]-x)*(s-z)/(prev[passing]-z)
            return sorted(np.sort(v).reshape(-1,2),key=lambda interval:abs(np.mean(interval)))
        split=[(s,hits) for s in np.linspace(.68,.985,172) if len(hits:=intervals(s))>=2] if name.startswith('upper') else []
        if split:
            split_at,first=split[0]
            last_at,last=split[-1]
            outer_sign=math.copysign(1,np.mean(first[1])-np.mean(first[0]))
        scale=1.23/(w-12)
        sign=math.copysign(1,rec['center'][0]-w/2) if abs(rec['center'][0]-w/2)>30 else 0.
        root=Vector((.041*sign,.245,.458 if name.startswith('upper') else .392))
        def world(p,s):
            x=(p[0]-w/2)*scale
            z=.019+(h-6-p[1])*scale
            z-=.36*max(0,z-.868)
            if name.startswith('upper'):
                x*=1.-.14*np.clip((z-.74)/.21,0,1)
                z-=.047*np.clip((abs(x)-.18)/.23,0,1)*np.clip((z-.65)/.17,0,1)
            lateral=abs(x)/.615
            y=.42+layer-.105*lateral**1.6-.165*max(0,z-.74)/.31
            if name.startswith('low outside'):y+=.155*lateral**1.35
            if name=='low middle':z-=.040*max(0,1-z/.24)**1.3
            p=Vector((x,y,z))
            return p.lerp(root,max(0,1-s/.47)**2)
        def shape(s,branch):
            hits=intervals(s)
            if not hits:
                return (float(np.mean(last[1])) if branch else 0.),0.
            all_edges=np.asarray(hits)
            lo,hi=all_edges.min(),all_edges.max()
            if branch:
                if s>=last_at:return float(np.mean(last[1])),0.
                if len(hits)>1:return float(np.mean(hits[1])),float(np.ptp(hits[1])*.5)
                k=np.clip((s-.57)/(split_at-.57),0,1)
                width=(hi-lo)*.31*math.sin(math.pi*k*.58)
                edge=hi if outer_sign>0 else lo
                return edge-outer_sign*(width+.15*(hi-lo)*(1-k)),width
            if len(hits)>1:lo,hi=hits[0]
            elif split and split_at-.14<s<split_at:
                k=(s-split_at+.14)/.14
                k=k*k*(3-2*k)
                if outer_sign>0:hi+=(first[0][1]-hi)*k
                else:lo+=(first[0][0]-lo)*k
            return (lo+hi)/2,(hi-lo)/2
        parts=[];guide=[]
        for branch in ([False,True] if split else [False]):
            vertices=[None]*194; texcoords=[None]*194
            for index,((ids,_,a,b),station) in enumerate(zip(profiles,stations)):
                s=.57+(last_at-.57)*station if branch else station
                off,radius=shape(s,branch)
                if not branch and 0<station<.45:
                    radius=max(radius,31*math.sin(math.pi*station/.49)**.75)
                if station in (0.,1.):radius=0.
                center=root_px+s*delta+side*off
                c=world(center,s)
                if not branch and index in (0,4,7,10,14):guide.append(c)
                a=a/max(float(np.max(abs(a))),1e-9)
                b=b/max(float(np.max(abs(b))),1e-9)
                thickness=radius*scale*(.74 if name.startswith('upper') else .84)
                for vi,dx,dy in zip(ids,a,b):
                    original=center+side*(radius*dx)
                    p=world(original,s)
                    p.y+=thickness*dy+(.012*math.sin(station*math.pi) if branch else 0)
                    vertices[vi]=p
                    x0,y0,x1,y1=rec['crop'];tx,ty=rec['tile']
                    uv=np.clip((original-(x0,y0))/np.array((x1-x0,y1-y0)),0,1)
                    texcoords[vi]=((tx+.5+uv[0]*251)/1024,1-(ty+.5+uv[1]*251)/1024)
            ob=sculpt.mesh('Tail | '+name+(' | fork' if branch else ''),vertices,polygons,material)
            uv=ob.data.uv_layers.new(name='49 measured plume')
            for loop in ob.data.loops:uv.data[loop.index].uv=texcoords[loop.vertex_index]
            parts.append(ob)
        if len(parts)==2:parts=[fuse_fork(sculpt,*parts,material)]
        add_spring_chain(sculpt.arm,parts,'Tail49_'+name.replace(' ','_'),guide,radius=.013,colliders=[collider])
