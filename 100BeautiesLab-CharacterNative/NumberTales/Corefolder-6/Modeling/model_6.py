"""Build Mui's editable corefolder and VRM0 from the verified #6 starter in Blender."""
from argparse import ArgumentParser
from math import atan2, cos, pi, sin
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


HERE = Path(__file__).resolve().parent
TRAINING = HERE.parents[1] / "Corefolder-Training"
ROOT = HERE.parents[3]
sys.path.insert(0, str(TRAINING))
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


def volume(name, outline, centre, depth, material, coll, attach=None, samples=2,levels=9):
    edge = sampled_ring(outline,samples)
    c = Vector(centre)
    rings = []
    for n in range(levels):
        lat = -pi/2+.002 + (pi-.004)*n/(levels-1)
        r = cos(lat)
        ring = []
        for p in edge:
            q = c+(p-c)*r+Vector((0,depth*sin(lat),0))
            if attach is not None and lat<0:
                q += (Vector(attach)-(c-Vector((0,depth,0)))) * (-sin(lat))**3
            ring.append(q)
        rings.append(ring)
    return rings_mesh(name,rings,material,coll)


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


def forelock(name,stations,cap_tree,face_tree,material,shade,coll,arm,*,layer=0,edge='right'):
    """Rounded solid fringe lobe draped over the reference cranium with a tapered edge."""
    controls=np.array(stations)
    rows=[]
    for i in range(len(controls)-1):
        a,b,c,d=(controls[min(len(controls)-1,max(0,k))] for k in (i-1,i,i+1,i+2))
        for t in (0,.5):
            rows.append((2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*.32*(c-a)+(-2*t**3+3*t*t)*c+(t**3-t*t)*.32*(d-b))
    rows.append(controls[-1])
    sections=[]
    across=(0,.045,.24,.50,.76,.955,1)
    cols=len(across)
    for i,(z,xl,xr) in enumerate(rows):
        t=i/(len(rows)-1)
        stations=[]
        width=max(.004,xr-xl)
        chart_z=z
        for u in across:
            # Stagger how each lobe emerges from the curved crown. A horizontal
            # row at constant height gives the joined fringe a straight shelf.
            z=chart_z+(.024*(u-.5)*(1 if edge=='left' else -1)+.010*np.sin(pi*u))*max(0,1-t/.55)
            x=xl+width*u
            rz=np.clip((z-.854)/.222,-.985,.985)
            scale=max(.02,1-rz*rz)**.47
            rx=.282*scale
            y=-.072-.289*scale*max(.04,1-(x/rx)**2)**.5
            support=[]
            for tree in (cap_tree,face_tree):
                hit=tree.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)[0]
                if hit is not None:support.append(hit.y)
            if support:
                root_y=min(support)
                emergence=np.clip((t-.30)/.22,0,1)
                y=root_y+emergence*(min(y,root_y)-root_y)
            f=np.clip(t/.34,0,1)
            emerge=f*f*(3-2*f)
            crown=min(.012,width*.13)*np.sin(pi*u)**.7*emerge
            loft=(.0025+layer+.0035*np.sin(pi*t))*emerge-.018*(1-emerge)
            stations.append((x,y-loft-crown,z))
        sections.append(stations)
    front=sum(sections,[])
    nv=len(front)
    verts=front+[(x,y+.004,z) for x,y,z in front]
    polys=[]
    for i in range(len(rows)-1):
        for j in range(cols-1):
            a=i*cols+j
            quad=(a,a+1,a+cols+1,a+cols)
            polys.extend((quad,tuple(nv+q for q in reversed(quad))))
    border=list(range(cols))+[i*cols+cols-1 for i in range(1,len(rows))]+list(range(nv-2,nv-cols-1,-1))+[i*cols for i in range(len(rows)-2,0,-1)]
    for i,a in enumerate(border):
        b=border[(i+1)%len(border)];polys.append((b,a,nv+a,nv+b))
    obj=closed_mesh(name,verts,polys,material,coll)
    obj.data.materials.append(shade)
    for i in range(len(rows)-1):
        if i/(len(rows)-1)<.45:continue
        j=cols-2 if edge=='right' else 0
        obj.data.polygons[2*(i*(cols-1)+j)].material_index=1
    # The tonal material is confined to the narrow exposed side, like the
    # thickness visible on the large central strand of reference #16.
    for i,a in enumerate(border):
        b=border[(i+1)%len(border)]
        if min(a//cols,b//cols)/len(rows)>.28 and a%cols==b%cols==(cols-1 if edge=='right' else 0):
            obj.data.polygons[len(polys)-len(border)+i].material_index=1
    bind(obj,arm)
    return obj


def head(arm, coll, hair, cream, pale, white):
    # The bob wraps behind the cheek and forms a shallow scallop at the nape.
    # Front hairline is defined in angle from the forward axis. Pairs of centre locks part over the eyes.
    angles = [-pi,-2.8,-2.45,-2.16,-1.82,-1.53,-1.29,-1.00,-.78,-.60,-.46,-.31,
              -.24,-.17,-.10,-.069,-.037,.03,.062,.105,.17,.23,.29,.36,.48,.55,.66,.80,
              1.0,1.29,1.53,1.82,2.16,2.45,2.80,pi]
    heights = [.671,.686,.681,.691,.715,.722,.744,.810,.868,.888,.900,.922,
               .901,.875,.858,.911,.928,.880,.870,.914,.938,.909,.863,.846,.880,.912,.898,.855,
               .801,.735,.722,.715,.691,.681,.686,.671]
    rows = []
    # Resolve each drawn hairline inflection exactly, without dense sampling on the rounded nape.
    sections=sorted(set(np.round(np.r_[np.linspace(-pi,pi,29)[:-1],angles[:-1]],4)))
    for i in range(10):
        row = []
        for a in sections:
            bottom = np.interp(a,angles,heights)
            bottom += .005*sin(3*a) + .007*max(0,-cos(a))**2*cos(9*a)
            # A squared bob below the triangular ears with a flatter crown.
            bottom += .022*max(0,cos(a))
            opening=np.clip((.99-abs(a))/.25,0,1)
            bottom=max(bottom,(.947+.010*cos(3*a))*opening+bottom*(1-opening))
            delta=(bottom-.858)/.218
            end = np.arccos(np.clip(np.sign(delta)*abs(delta)**(1/.79),-.999,.999))
            th = .005+(end-.005)*i/9
            shape = sin(th)
            back = max(0,-cos(a))
            ripple = .009*back*cos(7*a+th*.7)*sin(th)**3
            sweep=.050*shape**3*np.exp(-(a/.78)**2)
            x = (.303+ripple)*shape**.80*sin(a)+sweep
            y = -.071-(.295+ripple)*shape**.86*cos(a)
            y -= .006*np.exp(-(a/.8)**2)*shape**2*(.5+.5*cos(12*a+4*th))
            z = .858+.218*np.sign(cos(th))*abs(cos(th))**.79
            row.append((x,y,z))
        rows.append(row)
    hem=rows[-1]
    for inset in (.06,.76):
        rows.append([((1-inset)*x, -.074+(1-inset)*(y+.074), z+inset*(.80-z))
                     for x,y,z in hem])
    cap = rings_mesh("Mui hair • shaped bob and nape",rows,hair,coll)
    bind(cap,arm)
    bpy.context.view_layer.update()
    dep=bpy.context.evaluated_depsgraph_get()
    cap_bvh=BVHTree.FromObject(cap,dep)
    face_bvh=BVHTree.FromObject(bpy.data.objects['Face'],dep)
    front=toon("Mui • rounded fringe", "#FF76A2",0)
    rim=toon("Mui • fringe edge", "#E86694",0)
    # Reference #16 uses a wide sweep and a small number of separate rounded tips.
    # The two middle tips and the direction of the outer locks are specific to Mui.
    locks=[('left outer',[(.990,-.229,-.086),(.947,-.248,-.073),(.903,-.252,-.099),(.859,-.243,-.146),(.809,-.217,-.174),(.776,-.214,-.205)],.001,'right'),
           ('right outer',[(.987,.050,.231),(.947,.058,.242),(.908,.097,.253),(.858,.151,.245),(.807,.183,.226),(.785,.209,.218)],.002,'left'),
           ('flared sweep',[(.983,-.161,.076),(.952,-.173,.072),(.923,-.169,.039),(.901,-.151,-.015),(.880,-.138,-.069),(.868,-.129,-.118)],.004,'right'),
           ('inner left',[(.977,-.076,.045),(.933,-.090,.027),(.896,-.080,.005),(.863,-.062,-.008),(.837,-.041,-.019),(.819,-.016,-.010)],.007,'left'),
           ('inner right',[(.981,-.004,.139),(.941,-.006,.127),(.900,.012,.098),(.865,.033,.077),(.838,.039,.054),(.819,.030,.035)],.010,'right')]
    for label,profile,layer,edge in locks:
        forelock('Mui fringe '+label,profile,cap_bvh,face_bvh,front,rim,coll,arm,layer=layer,edge=edge)
    cheek_ink=toon("Mui • outer cheek line","#544553",0)
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
                new_y=(1-join)*(face_hit.y+.014)+join*new_y
            hit=garment.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)[0]
            if hit is not None and abs(x)>.178:new_y=min(new_y,hit.y-.007)
            return (x,new_y-extra,z)
        cheek = volume("Mui cheek tufts "+side,[cheek_point(x,y,z) for x,y,z in pts],
                       cheek_point(.213,-.283,.738),.025,white,coll,samples=2,levels=6)
        # Interior section rings also cross the collar's convex arc. Wrap them
        # individually, retaining a small thickness between front and rear rows.
        for v in cheek.data.vertices:
            x,y,z=v.co
            hit=garment.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)[0]
            if hit is not None and abs(x)>.179:
                v.co.y=min(y,hit.y-.009+.1*(y+.29))
        cheek.data.update()
        bind(cheek,arm)
        # A short stroke follows only the exposed feather edge. An inverted outline across
        # the cheek root would intersect the deforming Face and leave dots in Unity.
        edge_points=[(.303,-.260,.743,.0007),(.290,-.272,.719,.00165),(.271,-.280,.706,.00165),
                     (.248,-.288,.703,.0007)]
        bpy.context.view_layer.update()
        cheek_tree=BVHTree.FromObject(cheek,bpy.context.evaluated_depsgraph_get())
        contour=[]
        for x,y,z,w in edge_points:
            xx,yy,zz=cheek_point(x,y,z,.0025)
            hit=cheek_tree.ray_cast(Vector((xx,-1,zz)),Vector((0,1,0)),2)[0]
            if hit is not None:yy=hit.y-.0015
            contour.append((xx,yy,zz,w,.0009))
        bind(strand("Mui outer cheek stroke "+side,contour,cheek_ink,coll,radial_count=4,samples_per_span=1),arm)
        # The wide, near-horizontal ear rim is visible between the outer pink edge and the draped side lock.
        edge=[(.324,.120,1.077),(.318,.068,1.037),(.312,-.002,.993),(.304,-.085,.955),
              (.296,-.151,.896),(.278,-.185,.817),(.286,-.110,.847),(.299,.002,.864),
              (.305,.089,.878),(.313,.144,.928),(.321,.154,.991)]
        edge=sampled_ring([(s*(x+.022*np.clip((1.075-z)/.16,0,1)),y,z) for x,y,z in edge],2,tension=.62)
        center=Vector((s*.326,-.025,.949))
        rim=[]
        for scale, dx in ((.04,-.135),(.72,-.092),(.93,-.041),(1,0),(.93,.003),(.69,.006),(.53,.009),(.49,.008),(.02,.005)):
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
        hood=[(.050,-.025,1.037),(.135,.001,1.046),(.233,.057,1.056),(.324,.120,1.077),
              (.318,.078,1.030),(.301,.032,.965),(.284,-.054,.892),(.267,-.126,.834),
              (.226,-.142,.832),(.164,-.130,.890),(.074,-.077,.966)]
        cover=volume("Mui swept outer ear "+side,[(s*x,y+.033,z) for x,y,z in hood],
                     (s*.209,.028,.971),.045,hair,coll,samples=1,levels=6)
        bind(cover,arm,"head_Ear"+side+"_001")

        def mirror(stations): return [(s*x,y,z,w,d) for x,y,z,w,d in stations]
        # In the official front the side bangs form a single broad sweep with long rounded tips.
        path=mirror([(.173,-.20,.973,.020,.012),(.201,-.216,.937,.035,.016),
                     (.232,-.230,.897,.049,.026),(.252,-.209,.846,.045,.027),
                     (.256,-.200,.806,.034,.022),(.272,-.204,.770,.002,.001)])
        side_obj=strand("Mui temple sweep "+side,path,hair,coll)
        add_spring_chain(arm,side_obj,"MuiHair"+side,[p[:3] for p in (path[1],path[2],path[3],path[-1])],
                         parent="head",kind="hair",radius=.010)


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


def collar_and_brooch(arm,coll,database):
    torso=BVHTree.FromObject(bpy.data.objects["Body"],bpy.context.evaluated_depsgraph_get())
    def surface(a,t,off=0):return collar_point(torso,a,t,off)
    blue=toon("Mui collar • sky blue","#6AA6D7",.0017)
    ink=toon("Mui • seam and dark bezel","#242433",0)
    deep=toon("Mui brooch • sapphire edge","#185EBD",.0008)
    rings=[]
    for t,off in ((0,-.008),(0,.001),(.06,.004),(.27,.003),(.60,.002),(.94,.002),
                  (1,0),(1,-.009),(.94,-.013),(.48,-.012),(.04,-.010)):
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
    rings=[[gem_point(x,z,size,d) for x,z in xy] for size,d in ((.88,.023),(1,.014),(1,0),(.935,-.006))]
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
    hair=toon("Mui • raspberry hair", "#FF76A2",.0021)
    white=toon("Mui • white cheek fur","#FFFFFF",0)
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
