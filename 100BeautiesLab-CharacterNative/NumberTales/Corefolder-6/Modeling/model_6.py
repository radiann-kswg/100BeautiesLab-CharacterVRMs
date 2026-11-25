"""Build Mui's editable corefolder and VRM0 from the verified #6 starter in Blender."""
from argparse import ArgumentParser
import json
from math import atan2, cos, pi, sin
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import delaunay_2d_cdt


HERE = Path(__file__).resolve().parent
TRAINING = HERE.parents[1] / "Corefolder-Training"
ROOT = HERE.parents[3]
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(HERE))
from corefolder_springs import add_collider_group, add_spring_chain, save_character
from modeling_draft import bind, mesh_object
from refine_models import toon
from torso_profile import fit_common_torso


def sampled_ring(outline, samples=4, tension=.78):
    """A closed cardinal spline through hand-traced corners."""
    pts = [Vector(v) for v in outline]
    result = []
    for i, p in enumerate(pts):
        q = pts[(i+1) % len(pts)]
        dp = (q - pts[i-1]) * tension/2
        dq = (pts[(i+2)%len(pts)] - p) * tension/2
        for j in range(samples):
            t = j/samples
            result.append((2*t**3-3*t*t+1)*p + (t**3-2*t*t+t)*dp +
                          (-2*t**3+3*t*t)*q + (t**3-t*t)*dq)
    return result


def closed_mesh(name, verts, faces, material, collection):
    obj = mesh_object(name, verts, faces, [material], collection)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def rings_mesh(name, rings, material, collection):
    n = len(rings[0])
    assert all(len(row) == n for row in rings)
    faces = []
    for i in range(len(rings)-1):
        for j in range(n):
            k = (j+1)%n
            faces.append((i*n+j, i*n+k, (i+1)*n+k, (i+1)*n+j))
    faces.extend([tuple(reversed(range(n))), tuple(range((len(rings)-1)*n,len(rings)*n))])
    return closed_mesh(name, [p for row in rings for p in row], faces, material, collection)


def texture(name, path, outline=0, alpha=False):
    mat = toon(name, "#FFFFFF", outline)
    m = mat.vrm_addon_extension.mtoon1
    img = bpy.data.images.load(str(path), check_existing=True)
    img.pack()
    m.pbr_metallic_roughness.base_color_texture.index.source = img
    t = m.extensions.vrmc_materials_mtoon
    t.shade_multiply_texture.index.source = img
    t.shading_shift_factor = 1 if alpha else -.40
    t.gi_equalization_factor = .861
    if alpha:
        m.alpha_mode = 'MASK'
        m.alpha_cutoff = .49
    return mat


def mesh_uv(obj, mapping, name="UVMap"):
    uv = obj.data.uv_layers.get(name) or obj.data.uv_layers.new(name=name)
    obj.data.uv_layers.active = uv
    for p in obj.data.polygons:
        coords = [mapping(obj.data.loops[i].vertex_index) for i in p.loop_indices]
        if name == "Mui cylindrical fur" and max(u for u,v in coords)-min(u for u,v in coords)>.5:
            coords = [(u+1 if u<.5 else u,v) for u,v in coords]
        for i, co in zip(p.loop_indices, coords):
            uv.data[i].uv = co
    uv.active_render = True


def map_drawn_eyes(face, material):
    """Use a distinct cell per iris while keeping the donor eye weights and expression loops."""
    data=face.data
    uv=data.uv_layers.active
    basis=data.shape_keys.key_blocks['Basis'].data
    data.materials.append(material)
    slot=len(data.materials)-1
    for cell,start in ((0,627),(1,578)):
        indices=set(range(start,start+49))
        coords=np.array([basis[i].co[:] for i in sorted(indices)])
        x0,_,z0=coords.min(axis=0)
        dx,_,dz=np.ptp(coords,axis=0)
        for poly in data.polygons:
            if not indices.issuperset(poly.vertices):continue
            poly.material_index=slot
            for li in poly.loop_indices:
                x,_,z=basis[data.loops[li].vertex_index].co
                uv.data[li].uv=((cell+(x-x0)/dx)/2,(z-z0)/dz)


def restore_reference_body(arm,collection):
    """Read the plain common body again and keep the starter's usable bilateral armature weights."""
    from create_corefolder_base import split_donor_leg_weights
    from foundation import common_body
    source=ROOT/'100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend'
    common_body(source)
    obj=bpy.data.objects['Body']
    if obj.name not in collection.objects:collection.objects.link(obj)
    for current in list(obj.users_collection):
        if current!=collection:current.objects.unlink(obj)
    split_donor_leg_weights(obj,arm)
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.unsubdivide(bm,verts=list(bm.verts),iterations=2)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    fit_common_torso(obj)
    return obj


def prepare_body_and_face(body, face, arm, collection):
    body=restore_reference_body(arm,collection)
    body.data.materials.clear()
    body.data.materials.append(texture("Mui • raspberry and white belly", HERE/"Mui-Fur.png",.0018))
    def body_uv(i):
        x,y,z = body.data.vertices[i].co
        return .5 + atan2(x, -(y+.07))/(2*pi), z/.713
    # Replace the original generic UV with the new parameterization. VRM0 uses TEXCOORD_0.
    for uv in list(body.data.uv_layers):
        body.data.uv_layers.remove(uv)
    mesh_uv(body, body_uv, "Mui cylindrical fur")
    face.data.materials.clear()
    face.data.materials.append(texture("Mui • expression atlas",HERE/"Mui-Face.png",alpha=True))
    face.data.materials.append(toon("Mui • inner lip line","#734E5B",0))
    for polygon in face.data.polygons:
        if 144<=polygon.index<=151 or 397<=polygon.index<=404:
            polygon.material_index=1
    map_drawn_eyes(face,texture("Mui • drawn left and right irises",HERE/"Mui-Eyes.png",alpha=True))
    body["source"] = "Verified Corefolder-6 starter; common naked Body"
    face["source"] = "#4 reference face with two independently illustrated, reference-style irises"


def cheek_surface(name,outline,material,coll,thickness,front_limit=None):
    """A closed fur patch with matched front/back triangles around its concave tips."""
    border=np.array(sampled_ring(outline,2,tension=.70))
    p=border[:,[0,2]]
    points=p.tolist()
    for z in np.arange(p[:,1].min()+.009,p[:,1].max(),.010):
        for x in np.arange(p[:,0].min()+.008,p[:,0].max(),.011):
            inside=False
            for a,b in zip(p,np.roll(p,-1,axis=0)):
                if (a[1]>z)!=(b[1]>z) and x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0]:
                    inside=not inside
            if inside:points.append([x,z])
    edges=[(i,(i+1)%len(p)) for i in range(len(p))]
    elements=delaunay_2d_cdt([Vector(q) for q in points],edges,[list(range(len(p)))],1,1e-8)
    coords,_,triangles,_,_,_=elements
    front=[];back=[];vertices=[]
    edges=np.roll(p,-1,axis=0)-p
    for q in coords:
        delta=np.array(q)-p
        along=np.clip(np.sum(delta*edges,axis=1)/np.sum(edges*edges,axis=1),0,1)
        distance=np.linalg.norm(delta-along[:,None]*edges,axis=1).min()
        # Smoothly interpolated boundary elevations retain the native cheek
        # projection without pulling the two lips of a pointed tuft across one another.
        weight=1/np.maximum(1e-11,np.sum(delta*delta,axis=1))**1.35
        center=float(weight@border[:,1]/weight.sum())
        if front_limit:center=front_limit(q.x,q.y,center)
        depth=thickness*np.sqrt(np.clip(distance/.025,0,1))
        front.append(len(vertices));vertices.append((q.x,center-depth,q.y))
        if distance<1e-6:back.append(front[-1])
        else:back.append(len(vertices));vertices.append((q.x,center+depth,q.y))
    faces=[]
    for a,b,c in triangles:
        if all(front[i]==back[i] for i in (a,b,c)):
            # Three perimeter points at a sharp corner can enclose one small
            # triangle with no interior sample. Give its two faces a real bow.
            tips=np.array([vertices[front[i]] for i in (a,b,c)])
            x,y,z=tips.mean(axis=0)
            relief=min(thickness*.32,float(np.linalg.norm(np.diff(tips[:,[0,2]],axis=0),axis=1).min())*.14)
            f,bk=len(vertices),len(vertices)+1
            vertices.extend(((x,y-relief,z),(x,y+relief,z)))
            for h,k in ((a,b),(b,c),(c,a)):
                faces.extend(((front[h],front[k],f),(back[k],back[h],bk)))
        else:faces.extend([(front[a],front[b],front[c]),(back[c],back[b],back[a])])
    return closed_mesh(name,vertices,faces,material,coll)


def strand(name, controls, material, coll, *, radial_count=9, samples_per_span=3):
    """Volume following (x,y,z,half-width,half-depth) anatomical stations."""
    a = np.asarray(controls,float)
    rows = []
    for i in range(len(a)-1):
        p,q = a[i:i+2]
        m = (q-a[max(0,i-1)])*.43
        n = (a[min(len(a)-1,i+2)]-p)*.43
        for k in range(samples_per_span):
            t = k/samples_per_span
            rows.append((2*t**3-3*t*t+1)*p+(t**3-2*t*t+t)*m+
                        (-2*t**3+3*t*t)*q+(t**3-t*t)*n)
    rows.append(a[-1])
    rings = []
    for i,(x,y,z,w,d) in enumerate(rows):
        tangent = Vector(rows[min(i+1,len(rows)-1)][:3]-rows[max(i-1,0)][:3]).normalized()
        side = tangent.cross(Vector((0,1,0))).normalized()
        normal = tangent.cross(side).normalized()
        rings.append([Vector((x,y,z)) + side*max(.0008,w)*cos(2*pi*j/radial_count) +
                      normal*max(.0006,d)*sin(2*pi*j/radial_count) for j in range(radial_count)])
    return rings_mesh(name,rings,material,coll)


def swept_scalp(number,arm,coll,material):
    """One continuous crown, nape and forehead; each tapered tip has a folded underside."""
    from swept_hair import PROFILES, VALLEYS, valley
    anchors=np.array(PROFILES[number])
    angles,hems,drifts=anchors.T
    sampling=[]
    for a,b in zip(angles[:-1],angles[1:]):
        count=max(2 if .058<b-a<.22 else 1,int(np.ceil((b-a)/.125)))
        sampling.extend(np.linspace(a,b,count,endpoint=False))
    azimuth=np.asarray(sampling)
    size=len(azimuth)
    # Shape-preserving cubic interpolation rounds the extrema of each lock.
    def sample(values):
        delta=np.diff(values)/np.diff(angles)
        slope=np.zeros_like(values)
        for j in range(1,len(values)-1):
            if delta[j]*delta[j-1]>0:slope[j]=2/(1/delta[j]+1/delta[j-1])
        k=np.searchsorted(angles,azimuth,side='right')-1
        h=angles[k+1]-angles[k]
        f=(azimuth-angles[k])/h
        return (2*f**3-3*f*f+1)*values[k]+(f**3-2*f*f+f)*h*slope[k]+(-2*f**3+3*f*f)*values[k+1]+(f**3-f*f)*h*slope[k+1]
    hem=sample(hems)
    # Spread the broad directional drift across neighbouring columns. Each
    # height must preserve their order around the skull, even between fine tips.
    kernel=np.exp(-((azimuth[:,None]-azimuth[None,:])/.24)**2)
    drift=(kernel@sample(drifts))/kernel.sum(1)
    mui=number==6
    rz=.205 if mui else .202
    cz=.860
    rx=.288 if mui else .272
    depth=.302 if mui else .299
    cy=-.072
    end=np.arccos(np.clip((hem-cz)/rz,-1,1))
    core=coll.objects.get('Corefolder Cranial Base')
    core_tree=BVHTree.FromObject(core,bpy.context.evaluated_depsgraph_get()) if core else None
    rings=[]
    fractions=np.array([.004,.16,.31,.45,.56,.68,.77,.85,.92,.97,1.])
    for t in fractions:
        # Keep the upper latitudes level across the dome. The differences in
        # lock length develop in the lower third, outside the forehead.
        split=.56
        th=np.full_like(end,t/split*.95) if t<=split else .95+(end-.95)*(t-split)/(1-split)
        shell=np.sin(th)
        front=np.clip(np.cos(azimuth),0,1)
        # Sweep the flow to the part at the crown, then release it at each
        # drawn tip. A slight asymmetry also carries through the back of the bob.
        elevation=np.cos(th)
        a=azimuth+(.17 if mui else .15)*np.maximum(elevation,0)**1.25*(.18+.82*front)
        scoop=np.zeros_like(a)
        for tip,root,start in VALLEYS[number]:
            d,strength=valley(azimuth,t,tip,root,start)
            scoop+=strength*(.0025*np.exp(-(d/.049)**2)-.002*np.exp(-((d-.07)/.10)**2))
        ripple=.0045*np.cos(5*a+th*.9)*np.maximum(-np.cos(a),0)*shell**2
        radial=shell**.90*(1+(ripple-scoop)/rx)
        z=cz+rz*elevation
        shoulder=np.exp(-((np.abs(a)-1.22)/.38)**4)
        sweep=np.clip((.854-z)/.14,0,1)
        radial+=shoulder*sweep*np.maximum(0,(.960+.075*sweep)-radial)
        xx=rx*radial*np.sin(a)+drift*(1-elevation)**2*.40
        yy=cy-(depth+.009*front**2)*radial*np.cos(a)
        zz=cz+rz*elevation
        xx+=.016*np.maximum(elevation,0)**1.5
        row=[]
        for x,y,z in zip(xx,yy,zz):
            # At the temple the canonically round skull extends further
            # forward than the tapered side lock. Seat the full thickness
            # outside that skin and blend the clearance into its neighbours.
            if core_tree:
                center=Vector((0,-.085,z))
                ray=Vector((x,y,z))-center
                radius=ray.length
                ray.normalize()
                hit,_,_,skin=core_tree.ray_cast(center,ray,.58)
                if hit is not None:
                    need=skin+.015-radius
                    extra=.5*(need+np.sqrt(need*need+.002**2))
                    x+=ray.x*extra;y+=ray.y*extra
            row.append((x,y,z))
        rings.append(row)
    # A narrow return follows the outer surface all the way back up. A chord
    # closing across the forehead would pass through the movable lids.
    outside=list(rings)
    for row in reversed(outside):
        rings.append([(x*.985,cy+.985*(y-cy),z-.002*np.clip((z-.96)/.09,0,1)) for x,y,z in row])
    name='Mui hair • continuous swept bob' if mui else 'Hair scalp and swept forelocks'
    # A concave tip has a saddle-shaped quad. Set matching diagonals on
    # front and return so neither tessellator can flip one side independently.
    faces=[]
    def reciprocal(index):
        row,col=divmod(index,size)
        return (len(rings)-1-row)*size+col
    for i in range(len(outside)-1):
        for j in range(size):
            k=(j+1)%size
            a,b,c,d=i*size+j,i*size+k,(i+1)*size+k,(i+1)*size+j
            for tri in ((a,b,c),(a,c,d)):
                faces.extend((tri,tuple(reciprocal(v) for v in reversed(tri))))
    last=(len(outside)-1)*size
    for j in range(size):
        a,b=last+j,last+(j+1)%size
        faces.append((a,b,reciprocal(b),reciprocal(a)))
    faces.extend((tuple(range(size)),tuple(reciprocal(i) for i in reversed(range(size)))))
    obj=closed_mesh(name,[p for row in rings for p in row],faces,material,coll)
    uv=obj.data.uv_layers.new(name='Swept crown')
    for poly in obj.data.polygons:
        data=[]
        for i in poly.loop_indices:
            ring,col=divmod(obj.data.loops[i].vertex_index,size)
            data.append(((azimuth[col]+pi)/(2*pi),fractions[min(ring,len(rings)-1-ring)]))
        seam=max(u for u,_ in data)-min(u for u,_ in data)>.5
        for i,(u,v) in zip(poly.loop_indices,data):
            uv.data[i].uv=(u+1 if seam and u<.5 else u,v)
    bind(obj,arm)
    for sign,side in ((1,'L'),(-1,'R')):
        group=obj.vertex_groups.new(name='Moving temple '+side)
        center=1.12 if mui else 1.27
        nearest=int(np.argmin(abs(azimuth-sign*center)))
        path=[rings[i][nearest] for i in (6,7,8,10)]
        obj['temple path '+side]=json.dumps([list(p) for p in path])
        for i,v in enumerate(obj.data.vertices):
            ring,col=divmod(i,size)
            t=fractions[min(ring,len(rings)-1-ring)]
            span=np.clip((.40-abs(azimuth[col]-sign*center))/.19,0,1)
            f=np.clip((t-.735)/.25,0,1)*span
            if f>0:group.add([i],float(f*f*(3-2*f)),'REPLACE')
    return obj


def temple_guide(cap,name,side,coll):
    # The rig builder weights these samples along its standard spring
    # chain. Their weights are blended onto the continuous scalp below.
    mesh=bpy.data.meshes.new(name+' guide')
    mesh.from_pydata([v.co for v in cap.data.vertices],[],[])
    obj=bpy.data.objects.new(name,mesh)
    coll.objects.link(obj)
    obj['spring_path']=cap['temple path '+side]
    return obj


def skin_temples(cap,guides):
    head=cap.vertex_groups['head']
    for side,obj in guides:
        mask=cap.vertex_groups['Moving temple '+side]
        for v in cap.data.vertices:
            blend=next((g.weight for g in v.groups if g.group==mask.index),0)
            if not blend:continue
            head_weight=1-blend
            for weight in obj.data.vertices[v.index].groups:
                bone=obj.vertex_groups[weight.group].name
                if bone=='head':head_weight+=blend*weight.weight
                else:
                    group=cap.vertex_groups.get(bone) or cap.vertex_groups.new(name=bone)
                    group.add([v.index],blend*weight.weight,'REPLACE')
            head.add([v.index],head_weight,'REPLACE')
        cap.vertex_groups.remove(mask)
        bpy.data.objects.remove(obj,do_unlink=True)


def join_hair_roots(arm,cap,parts):
    """Join the exterior at the ear and temple and ease its spring weights into the scalp."""
    def source(obj):
        mesh=obj.data
        mesh.calc_loop_triangles()
        p=[v.co.copy() for v in mesh.vertices]
        triangles=[t.vertices[:] for t in mesh.loop_triangles]
        surface=BVHTree.FromPolygons(p,triangles,all_triangles=True)
        nearest=KDTree(len(p))
        for i,v in enumerate(p):nearest.insert(v,i)
        nearest.balance()
        weights=[{obj.vertex_groups[g.group].name:g.weight for g in v.groups
                  if g.weight>1e-6 and obj.vertex_groups[g.group].name in arm.data.bones}
                 for v in mesh.vertices]
        return surface,nearest,weights
    for obj in [cap,*parts]:
        if obj.data.uv_layers.active:obj.data.uv_layers.active.name="Hair"
    for part in parts:
        outer,outer_kd,ow=source(cap)
        lobe,lobe_kd,lw=source(part)
        op=cap.modifiers.new("Weld "+part.name,"BOOLEAN")
        op.operation='UNION'
        op.solver='EXACT'
        op.material_mode='TRANSFER'
        op.object=part
        cap.modifiers.move(len(cap.modifiers)-1,0)
        bpy.context.view_layer.objects.active=cap
        bpy.ops.object.modifier_apply(modifier=op.name)
        if not len(cap.data.vertices):raise ValueError("Failed hair junction: "+part.name)
        for group in list(cap.vertex_groups):cap.vertex_groups.remove(group)
        groups={}
        for v in cap.data.vertices:
            pos=v.co
            d0=outer.find_nearest(pos)[3]
            d1=lobe.find_nearest(pos)[3]
            if d0<=d1+.00002:
                weights=ow[outer_kd.find(pos)[1]]
            else:
                # The fixed common seam and its adjacent 16-mm falloff keep a
                # moving ear or strand from tearing away on a head turn.
                factor=min(1.,d0/.016)
                factor=factor*factor*(3-2*factor)
                weights={k:w*factor for k,w in lw[lobe_kd.find(pos)[1]].items()}
                weights['head']=weights.get('head',0)+1-factor
            weights={k:w for k,w in sorted(weights.items(),key=lambda it:-it[1])[:4] if w>1e-7}
            total=sum(weights.values())
            if total<=1e-6:raise ValueError("No hair weight: "+part.name)
            for k,w in weights.items():
                if k not in groups:groups[k]=cap.vertex_groups.new(name=k)
                groups[k].add([v.index],w/total,'REPLACE')
        bpy.data.objects.remove(part,do_unlink=True)
        cap.data.update()
    bpy.context.view_layer.update()


def head(arm, coll, hair, cream, pale, white):
    face=bpy.data.objects['Face']
    cap_mat=texture("Mui • swept crown and forelocks",HERE/'Mui-Bangs.png',.0015)
    cap=swept_scalp(6,arm,coll,cap_mat)
    parts=[]
    guides=[]
    bpy.context.view_layer.update()
    face_bvh=BVHTree.FromObject(face,bpy.context.evaluated_depsgraph_get())
    garment=BVHTree.FromObject(bpy.data.objects['Mui sky-blue collar'],bpy.context.evaluated_depsgraph_get())
    for s,side in ((1,"L"),(-1,"R")):
        # A rounded white cheek split into two pinched tufts, with integral thickness.
        pts=[(.113,-.298,.753),(.151,-.291,.779),(.190,-.279,.793),(.225,-.264,.789),
             (.251,-.258,.765),(.276,-.256,.747),(.308,-.258,.743),(.291,-.271,.719),
             (.270,-.279,.706),(.248,-.287,.703),(.250,-.292,.684),(.264,-.294,.664),
             (.241,-.299,.664),(.212,-.307,.680),(.193,-.313,.694),(.178,-.316,.682),
             (.164,-.317,.677),(.148,-.313,.700),(.125,-.311,.725)]
        def cheek_x(x):
            root=.035*np.clip((.190-x)/.078,0,1)**2
            return s*(x-.011+root-.010*np.clip((x-.17)/.108,0,1))
        def cheek_point(x,y,z,extra=0):
            x,z=cheek_x(x),.741+(z-.738)*1.17
            # Bury the broad root under the actual cheek skin and allow only
            # the two distal tufts to protrude like the side fur of #16/#93.
            join=np.clip((abs(x)-.147)/.093,0,1)
            face_hit=face_bvh.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)[0]
            new_y=y+.024
            if face_hit is not None:
                new_y=(1-join)*(face_hit.y+.040)+join*new_y
            hit=garment.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)[0]
            if hit is not None and abs(x)>.178:new_y=min(new_y,hit.y-.007)
            return (x,new_y-extra,z)
        def garment_limit(x,z,y):
            hit=garment.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)[0]
            return min(y,hit.y-.010) if hit is not None and abs(x)>.179 else y
        cheek=cheek_surface("Mui cheek tufts "+side,[cheek_point(x,y,z) for x,y,z in pts],
                            white,coll,.018,garment_limit)
        bind(cheek,arm)
        # The wide, near-horizontal ear rim is visible between the outer pink edge and the draped side lock.
        edge=[(.324,.120,1.077),(.318,.068,1.037),(.312,-.002,.993),(.304,-.085,.955),
              (.296,-.151,.896),(.278,-.185,.817),(.286,-.110,.847),(.299,.002,.864),
              (.305,.089,.878),(.313,.144,.928),(.321,.154,.991)]
        edge=sampled_ring([(s*(x+.022*np.clip((1.075-z)/.16,0,1)),y,z) for x,y,z in edge],2,tension=.62)
        center=Vector((s*.326,-.025,.949))
        rim=[]
        for scale, dx in ((.04,-.167),(.53,-.106),(.85,-.048),(1,0),(.93,.003),(.69,.006),(.53,.009),(.49,.008),(.02,.005)):
            rim.append([center+(p-center)*scale+Vector((s*dx,0,0)) for p in edge])
        ear=rings_mesh("Mui fox ear "+side,rim,hair,coll)
        ear.data.materials.append(cream)
        ear.data.materials.append(pale)
        n=len(edge)
        for p in ear.data.polygons:
            ring_index=p.index//n
            if 4<=ring_index<=5:p.material_index=1
            if 6<=ring_index<=7:p.material_index=2
        bind(ear,arm,"head_Ear"+side+"_001")
        parts.append(ear)
        guide=temple_guide(cap,"Mui temple "+side,side,coll)
        add_spring_chain(arm,guide,"MuiHair"+side,json.loads(guide["spring_path"]),
                         parent="head",kind="hair",radius=.010)
        guides.append((side,guide))
    skin_temples(cap,guides)
    join_hair_roots(arm,cap,parts)


# Tail-tip boundaries in the official 520 x 448 rear TailsUnit swatch (image y, x).
MASKS = {
    "Upper": [(0,140),(54,139),(82,148),(125,152),(170,151),(203,146),(235,134),(450,120)],
    "Middle": [(0,35),(144,49),(174,67),(199,78),(226,89),(260,98),(296,103),(339,110),(450,118)],
    "Lower": [(0,62),(290,87),(315,96),(333,127),(361,144),(395,166),(420,180),(440,185),(450,187)],
}


def tails(arm,coll,body_collider):
    from native_tail_profiles import load_tail, make_plume
    source=load_tail()
    fur=texture("Mui tail • curved pale pink tips",HERE/"Mui-TailBand.png",.002)
    # Root and tip landmarks retain the three DB tiers. The 15 ring sections,
    # their expanding bulb and taper come from the original common fox tail.
    # The upper, middle and low pairs bow to different depths like #16 and #93.
    plumes=(('Upper',(.053,.180,.410),(.173,.461,.790),(.412,.452,1.056),.246,.205,.105),
            ('Middle',(.074,.227,.299),(.311,.574,.453),(.606,.526,.637),.246,.195,.15),
            ('Lower',(.058,.212,.224),(.224,.590,.192),(.528,.691,.287),.219,.182,.105))
    for sign,side in ((1,'L'),(-1,'R')):
        for name,root,bulb,tip,radius,depth,curve in plumes:
            overlap={'Upper':.026,'Middle':-.045,'Lower':.029}[name]
            def mirror(point):return (sign*point[0],point[1]+(sign*overlap if point!=root else 0),point[2])
            xyz,polygons,guides=make_plume(source,mirror(root),mirror(bulb),mirror(tip),radius,depth,curve)
            for ids,s,_,_ in source[0]:
                if len(ids)<2:continue
                # Mui keeps a rounded shoulder behind the little cream point.
                center=xyz[ids].mean(axis=0)
                swell=1+.065*np.exp(-((s-.71)/.16)**2)
                xyz[ids]=center+(xyz[ids]-center)*swell
            obj=closed_mesh('Mui tail '+name+' '+side,xyz,polygons,fur,coll)
            ys,limits=zip(*MASKS[name])
            def uv(index):
                x,y,z=xyz[index]
                px=260-x/(sign*.00240)
                py=(1.048-z)/.00240+6
                boundary=np.interp(py,ys,limits)
                # The cream continues around the physical circumference of the bulb.
                return np.clip(.50+(px-boundary)/470+.045*(y-bulb[1]),.04,.96),np.clip(.23+(y-bulb[1])*.9,.01,.99)
            mesh_uv(obj,uv)
            add_spring_chain(arm,obj,'MuiTail'+name+side,guides,radius=.018,colliders=[body_collider])
            obj['geometry source']='Common Corefolder Base tail, 194 source vertices, 15 cross-sections, #6 tip palette'


def collar_point(torso,angle,t,offset=0):
    # Broad sky-blue collar, raised at sides/back, following the upper torso rather than the jaw.
    side=sin(angle)**2
    back=(1-cos(angle))*.5
    slit=max(0,1-abs((angle+pi)%(2*pi)-pi)/.16)
    low=.572+.044*side+.026*back+.012*slit
    high=.669+.019*side+.012*back
    z=low+(high-low)*t
    rx=.317-.119*t
    ry=.311-.111*t
    axis=Vector((0,-.061,z))
    tangent=Vector((rx*sin(angle),-ry*cos(angle),0))
    radius=tangent.length
    tangent.normalize()
    hit,_,_,distance=torso.ray_cast(axis,tangent,1)
    if hit is not None:
        radius=distance+.010+.004*(1-t)
    return axis+tangent*(radius+offset)


def fit_outfit_skin(body,objects):
    """Attach the clothing to the same skin as the piece of shoulder it covers."""
    mesh=body.data
    mesh.calc_loop_triangles()
    points=[body.matrix_world@v.co for v in mesh.vertices]
    triangles=[tri.vertices[:] for tri in mesh.loop_triangles]
    tree=BVHTree.FromPolygons(points,triangles,all_triangles=True)
    weights=[{body.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>1e-6}
             for v in mesh.vertices]
    def surface_weights(position):
        point,_,index,_=tree.find_nearest(position)
        ia,ib,ic=triangles[index]
        a,b,c=points[ia],points[ib],points[ic]
        normal=(b-a).cross(c-a)
        if normal.length_squared<1e-16:return weights[ia]
        wb=(point-a).cross(c-a).dot(normal)/normal.length_squared
        wc=(b-a).cross(point-a).dot(normal)/normal.length_squared
        weighted={}
        for vi,ratio in ((ia,1-wb-wc),(ib,wb),(ic,wc)):
            for key,value in weights[vi].items():
                weighted[key]=weighted.get(key,0)+max(0,ratio)*value
        return dict(sorted(weighted.items(),key=lambda row:-row[1])[:4])
    for obj in objects:
        if obj.type!='MESH':continue
        obj['corefolder_layer']='Outfit'
        rigid='six-sided floral brooch' in obj.name
        anchor=max((obj.matrix_world@v.co for v in obj.data.vertices),key=lambda p:p.z) if rigid else None
        fixed=surface_weights(anchor) if rigid else None
        for grp in list(obj.vertex_groups):obj.vertex_groups.remove(grp)
        groups={}
        for v in obj.data.vertices:
            values=fixed if rigid else surface_weights(obj.matrix_world@v.co)
            total=sum(values.values())
            for key,weight in values.items():
                if weight<=1e-7:continue
                if key not in groups:groups[key]=obj.vertex_groups.new(name=key)
                groups[key].add([v.index],weight/total,'REPLACE')


def collar_and_brooch(arm,coll,database):
    existing=set(coll.objects)
    torso=BVHTree.FromObject(bpy.data.objects["Body"],bpy.context.evaluated_depsgraph_get())
    def surface(a,t,off=0):return collar_point(torso,a,t,off)
    blue=toon("Mui collar • sky blue","#6AA6D7",.0017)
    ink=toon("Mui • seam and dark bezel","#242433",0)
    deep=toon("Mui brooch • sapphire edge","#185EBD",.0008)
    rings=[]
    for t,off in ((0,-.005),(0,.001),(.06,.004),(.24,.003),(.43,.003),(.63,.002),
                  (.81,.002),(.94,.002),(1,0),(1,-.003),(.92,-.004),(.77,-.004),
                  (.61,-.005),(.45,-.005),(.29,-.005),(.14,-.005),(.04,-.005)):
        rings.append([surface(2*pi*j/42,t,off) for j in range(42)])
    # A hollow mantle, with an open neck and a stitched thick rim.
    n=len(rings[0])
    faces=[(i*n+j,i*n+(j+1)%n,((i+1)%len(rings))*n+(j+1)%n,((i+1)%len(rings))*n+j)
           for i in range(len(rings)) for j in range(n)]
    garment=closed_mesh("Mui sky-blue collar",sum(rings,[]),faces,blue,coll)
    bind(garment,arm,"chest")
    for label,coords in (("centre seam",[(0,.03),(0,.34),(0,.72),(0,.98)]),
                         ("cross stitch",[(-.047,.63),(-.014,.63),(.014,.63),(.047,.63)])):
        line=[]
        for a,t in coords:
            p=surface(a,t,.006)
            line.append((*p,.0025,.0016))
        bind(strand("Mui collar "+label,line,ink,coll),arm,"chest")
    numeral=texture("Mui • official collar 6",database/"data/Works_NumberTales/Images/DB_Primary/attr/numberMark/attr_numberMarkNTS-6.png",alpha=True)
    rows,cols=7,6
    def numeral_point(i,j):
        height=.25+.60*i/(rows-1)
        x=.067+.049*j/(cols-1)
        lo,hi=0,.55
        for _ in range(12):
            a=(lo+hi)*.5
            if surface(a,height,.0075).x<x:lo=a
            else:hi=a
        return surface((lo+hi)*.5,height,.0075)
    verts=[numeral_point(i,j) for i in range(rows) for j in range(cols)]
    faces=[(i*cols+j,i*cols+j+1,(i+1)*cols+j+1,(i+1)*cols+j) for i in range(rows-1) for j in range(cols-1)]
    mark=mesh_object("Mui • 6 on left collar",verts,faces,[numeral],coll)
    mesh_uv(mark,lambda i:(i%cols/(cols-1),i//cols/(rows-1)))
    bind(mark,arm,"chest")
    paint=texture("Mui • six-petal official brooch",HERE/"Mui-Brooch.png")
    # Each painted petal comes directly from pose 1, perspective-corrected onto a bevelled hexagon.
    # Exterior edge is real depth so the brooch remains visible from the side.
    xy=[(0,1),(.866,.50),(.866,-.50),(0,-1),(-.866,-.50),(-.866,.50)]
    pixel=[(837,597),(899,649),(895,742),(828,787),(758,733),(767,637)]
    def gem_point(x,z,scale,depth):
        height=.511+z*.079*scale
        axis=Vector((x*.076*scale,-1,height))
        hit,_,_,_=torso.ray_cast(axis,Vector((0,1,0)),2)
        y=hit.y if hit is not None else -.462
        return (axis.x,y-.028+depth,height)
    rings=[[gem_point(x,z,size,d) for x,z in xy] for size,d in ((.88,.018),(1,.014),(1,0),(.935,-.006))]
    verts=sum(rings,[])+[gem_point(0,0,1,-.012)]
    faces=[tuple(reversed(range(6)))]
    for i in range(3):
        for j in range(6):
            faces.append((6*i+j,6*i+(j+1)%6,6*i+6+(j+1)%6,6*i+6+j))
    faces.extend([(18+j,18+(j+1)%6,24) for j in range(6)])
    gem=closed_mesh("Mui six-sided floral brooch",verts,faces,deep,coll)
    gem.data.materials.append(ink)
    gem.data.materials.append(paint)
    uv=gem.data.uv_layers.new(name="Official brooch")
    for p in gem.data.polygons:
        p.use_smooth=False
        p.material_index=2 if len(p.vertices)==3 else 1 if 24>max(p.vertices)>=18 else 0
        for li in p.loop_indices:
            vi=gem.data.loops[li].vertex_index
            px,py=pixel[vi%6] if vi<24 else (832,691)
            uv.data[li].uv=((px-753)/156,1-(py-590)/201)
    bind(gem,arm,"chest")
    p0=surface(0,.11,.009)
    top=Vector(gem_point(0,1,1,-.007))
    link=[(*p0.lerp(top,t),.004,.003) for t in (0,.3,.7,1)]
    bind(strand("Mui brooch fastening",link,deep,coll),arm,"chest")
    fit_outfit_skin(bpy.data.objects['Body'],set(coll.objects)-existing)


def main():
    p=ArgumentParser(description=__doc__)
    p.add_argument("--starter",type=Path,default=ROOT/".cache/vrm-5.3-tests/verified-20261125/Corefolder-6/Corefolder-6-Starter.blend")
    p.add_argument("--database",type=Path,default=Path("D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB"))
    p.add_argument("--out",type=Path,default=HERE)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(args.starter.resolve()),use_scripts=False)
    arm=bpy.data.objects["Armature"]
    face=bpy.data.objects["Face"]
    body=bpy.data.objects["Body"]
    coll=body.users_collection[0]
    bpy.context.scene.name="Mui | 6"
    bpy.context.preferences.filepaths.save_version=0
    from canonical_face import fit_reference_face
    fit_reference_face(face,arm)
    prepare_body_and_face(body,face,arm,coll)
    from torso_profile import add_cranial_base
    add_cranial_base(arm,face,6,coll)
    hair=toon("Mui • raspberry hair", "#FF76A2",.0021)
    white=toon("Mui • white cheek fur","#FFFFFF",0)
    white.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon.shade_color_factor=(.96,.95,.96)
    cream=toon("Mui • ivory ear fur","#FFFDF2",0)
    pale=toon("Mui • pink inner ear","#FFCEED",0)
    chest=add_collider_group(arm,"Mui rump","hips",[((0,.05,.34),.23)])
    collar_and_brooch(arm,coll,args.database)
    head(arm,coll,hair,cream,pale,white)
    tails(arm,coll,chest)
    meshes=[obj for obj in bpy.context.scene.objects if obj.type=="MESH"]
    result=save_character(arm,meshes,args.out/"Corefolder-6.blend",args.out/"Corefolder-6.vrm",
                          title="NumberTales #6 — 6(ムイ) / 6(Sics)", version="1.0",character_number=6)
    print("MUI_EXPORT",result)


if __name__=="__main__":
    main()
