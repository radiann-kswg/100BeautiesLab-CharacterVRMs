"""Build #49 from its editable starter. Run in background Blender with the VRM Add-on enabled."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
TRAINING = HERE.parents[1] / 'Corefolder-Training'
ROOT = HERE.parents[3]
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(HERE))
from corefolder_springs import add_collider_group, add_spring_chain, save_character
from face_articulation import finish_face
from modeling_draft import bind, mesh_object
from refine_models import linear


def catmull(points, t, closed=False):
    """Interpolating cubic with clamped end tangents (or a closed contour)."""
    count = len(points)
    u = min(max(t, 0), 1) * (count if closed else count - 1)
    i = min(int(u), count - (1 if closed else 2))
    f = u - i
    def point(j):
        j = j % count if closed else min(max(j, 0), count-1)
        return Vector(points[j])
    a,b,c,d = (point(j) for j in (i-1,i,i+1,i+2))
    return .5*((2*b)+(-a+c)*f+(2*a-5*b+4*c-d)*(f*f)+(-a+3*b-3*c+d)*(f*f*f))


def reverse_if_inward(ob):
    """Orient all surfaces consistently for both glTF and MToon outlines."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def independent_iris_uv(face):
    """Give the second iris its own artwork on the reference face's unchanged topology."""
    mesh = face.data
    uv = mesh.uv_layers.active.data
    for loop in mesh.loops:
        if 627 <= loop.vertex_index <= 675:
            # Top-left PNG coordinates (750,865) move to the unused area (10,500).
            uv[loop.index].uv += Vector((-740/1024,365/1024))


def restore_body_surface(body):
    """Use the real common body's mirrored Subdivision Surface while retaining skin weights."""
    source=ROOT/'100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend'
    with bpy.data.libraries.load(str(source),link=False) as (_,target):
        target.objects=['body']
    base,=target.objects
    bpy.context.scene.collection.objects.link(base)
    original_mesh=base.data
    try:
        subdivision=base.modifiers.new('Reference surface','SUBSURF')
        subdivision.levels=2
        bpy.context.view_layer.update()
        shape=base.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
        source_edges=np.array([e.vertices[:] for e in shape.edges])
        target_edges=np.array([e.vertices[:] for e in body.data.edges])
        if len(body.data.vertices)!=len(shape.vertices) or not np.array_equal(source_edges,target_edges):
            raise ValueError('The editable torso no longer matches the common body vertex order')
        coordinates=np.empty(3*len(shape.vertices),np.float32)
        shape.vertices.foreach_get('co',coordinates)
        body.data.vertices.foreach_set('co',coordinates)
        body.data.update()
    finally:
        bpy.data.objects.remove(base,do_unlink=True)
        if not original_mesh.users:bpy.data.meshes.remove(original_mesh)


class Sculpt:
    def __init__(self, arm, body, face):
        self.arm, self.collection = arm, body.users_collection[0]
        self.items = [body, face]
        self.skin_template = body.data.materials[0]
        self.face_template = face.data.materials[0]
        self.blue = self.material('Sky fur', '#6AA6D7')
        self.pale = self.material('Inner ear blue', '#9BC1E6', edge=False)
        self.cream = self.material('Ear lining', '#FFFEF4', edge=False)
        self.hair = self.material('Sky hair', '#6AA6D7')
        self.strand = self.material('Hair underlayers', '#609CCF')
        self.throat = self.material('Cheek transition', '#FFFFFF', texture='49-neck.png', edge=False)
        self.plume = self.material('Blue tipped plume', '#FFFFFF', texture='49-tail.png')
        self.belly = self.material('White bib and chest mark', '#FFFFFF', texture='49-body.png')
        self.skin = self.material('Yochika face', '#FFFFFF', face=True, texture='49-face.png', edge=False)

    def material(self, name, hexcolor, *, face=False, texture=None, edge=True):
        mat = (self.face_template if face else self.skin_template).copy()
        mat.name = '49 ' + name
        prop = mat.vrm_addon_extension.mtoon1
        prop.double_sided = True
        prop.alpha_mode = 'MASK' if face and texture else 'OPAQUE'
        prop.alpha_cutoff = .48
        rgb = linear(hexcolor)
        prop.pbr_metallic_roughness.base_color_factor = (*rgb, 1)
        toon = prop.extensions.vrmc_materials_mtoon
        shade = .968 if texture in ('49-body.png','49-face.png','49-neck.png') else .89
        toon.shade_color_factor = tuple(x*shade for x in rgb)
        if not edge:
            toon.outline_width_mode = 'none'
            toon.outline_width_factor = 0
        else:
            toon.outline_color_factor = linear('#314A63')
            toon.outline_lighting_mix_factor = .09
            toon.outline_width_factor = .00115 if name in ('Sky hair','Hair underlayers','Blue tipped plume') else .00065
        if texture:
            img = bpy.data.images.load(str(HERE / texture), check_existing=True)
            prop.pbr_metallic_roughness.base_color_texture.index.source = img
            toon.shade_multiply_texture.index.source = img
        return mat

    def mesh(self, name, verts, faces, material):
        ob = mesh_object(name, verts, faces, [material], self.collection)
        reverse_if_inward(ob)
        self.items.append(ob)
        return ob

    def tube(self, name, path, widths, depths, axis, mat, *, textured=False):
        """Elliptic loft. Independent sections control the swollen and hooked end of each tuft."""
        steps = 25 if 'low wrap' in name else 18 if textured else 14
        sides = 24 if 'low wrap' in name else 12 if textured else 8
        verts, faces, uv = [], [], []
        def frame(t):
            p = catmull(path, t)
            tangent = (catmull(path,min(1,t+.0007))-catmull(path,max(0,t-.0007))).normalized()
            side = Vector(axis)
            side -= tangent * side.dot(tangent)
            if side.length < .03:
                side = tangent.cross(Vector((0,1,0)))
            side.normalize()
            return p,tangent,side,tangent.cross(side).normalized()
        def envelope(samples,t):
            return max(.0005, catmull([(a,0) for a in samples], t).x)
        for i in range(steps):
            t = i / (steps-1)
            p,tangent,side,normal=frame(t)
            w,d=envelope(widths,t),envelope(depths,t)
            for j in range(sides):
                a = math.tau*j/sides
                verts.append(tuple(p + side*(w*math.cos(a)) + normal*(d*math.sin(a))))
                uv.append((j/sides,t))
        for i in range(steps-1):
            for j in range(sides):
                k = (j+1)%sides
                faces.append((i*sides+j,i*sides+k,(i+1)*sides+k,(i+1)*sides+j))
        faces.append(tuple(reversed(range(sides))))
        faces.append(tuple((steps-1)*sides+j for j in range(sides)))
        ob = self.mesh(name, verts, faces, mat)
        if textured:
            layer = ob.data.uv_layers.new(name='Root to light tip')
            for p in ob.data.polygons:
                around = [uv[v][0] for v in p.vertices]
                wrap = max(around)-min(around)>.5
                for li in p.loop_indices:
                    v = ob.data.loops[li].vertex_index
                    u,t=uv[v]
                    t=t**1.22 if 'low wrap' in name else t
                    layer.data[li].uv = (u+1. if wrap and u<.5 else u,t)
        return ob

    def plate(self, name, edge, surface, mat, rise=.006, thickness=.004):
        """Rounded relief with a closed back, for the ear lining and its inner fur."""
        n = 32
        bounds = [catmull(edge,i/n,True) for i in range(n)]
        center = sum(bounds, Vector((0,0))) / n
        verts = [surface(*center, rise)]
        faces = []
        for r in (.65,1.,.99):
            back = len(verts) > 1 + n
            for q in bounds:
                uv = center.lerp(q,r)
                lift = -thickness if back else rise * max(0,1-r*r)
                verts.append(surface(*uv,lift))
        verts.append(surface(*center,-thickness))
        for j in range(n):
            k=(j+1)%n
            faces.append((0,1+j,1+k))
            for row in range(2):
                a=1+row*n
                faces.append((a+j,a+n+j,a+n+k,a+k))
            faces.append((len(verts)-1,1+2*n+k,1+2*n+j))
        ob = self.mesh(name,verts,faces,mat)
        bind(ob,self.arm,'head')
        return ob

    def body(self, body):
        restore_body_surface(body)
        bpy.ops.object.select_all(action='DESELECT')
        body.select_set(True)
        bpy.context.view_layer.objects.active=body
        dec=body.modifiers.new('Restore native quad density','DECIMATE')
        dec.decimate_type='UNSUBDIV'
        dec.iterations=2
        bpy.ops.object.modifier_move_to_index(modifier=dec.name,index=0)
        bpy.ops.object.modifier_apply(modifier=dec.name)
        from torso_profile import fit_common_torso
        fit_common_torso(body)
        body.data.materials.clear()
        body.data.materials.append(self.belly)
        layer = body.data.uv_layers.new(name='49 wrapped belly')
        body.data.uv_layers.active = layer
        layer.active_render = True
        for p in body.data.polygons:
            p.material_index=0
            p.use_smooth=True
            uv = []
            for vi in p.vertices:
                q = body.data.vertices[vi].co
                uv.append((.5+math.atan2(q.x,-(q.y+.07))/math.tau, min(1,q.z/.713)))
            wrap = max(a for a,b in uv)-min(a for a,b in uv)>.5
            for li,(u,v) in zip(p.loop_indices,uv):
                layer.data[li].uv = (u+1 if wrap and u<.5 else u,v)
        # glTF uses TEXCOORD_0 by default; make the authored cylindrical map the only active map.
        for old in list(body.data.uv_layers):
            if old.name != layer.name:
                body.data.uv_layers.remove(old)

    def face(self, face):
        face.data.materials.clear()
        face.data.materials.append(self.skin)
        for p in face.data.polygons:
            p.material_index = 0
            p.use_smooth=True
        independent_iris_uv(face)
        finish_face(49,face,self.arm)

    def close_neck(self, face):
        # Find the starter's outer face loop, then extend its exact edge into
        # a rounded occiput. The coincident rims follow the same head bone.
        edges = {}
        for poly in face.data.polygons:
            for edge in poly.edge_keys:
                edges[edge] = edges.get(edge,0)+1
        neighbors = {}
        for (a,b),count in edges.items():
            if count == 1:
                neighbors.setdefault(a,[]).append(b)
                neighbors.setdefault(b,[]).append(a)
        start=242  # center of the posterior jaw edge on the expression starter
        ids=[start]; prev=None; current=start
        while True:
            following, = [v for v in neighbors[current] if v != prev][:1]
            if following==start:
                break
            if following in ids:
                raise ValueError('Unexpected starter face boundary')
            ids.append(following)
            prev,current=current,following
        points=[face.data.shape_keys.key_blocks[0].data[i].co.copy() for i in ids]
        n=len(points)
        if n<20 or min(p.x for p in points)>-.20:
            raise ValueError('Could not identify the bilateral posterior face boundary')
        verts=[]; polys=[]
        sections=[(0,1.,0),(.020,1.,-.006),(.056,1.,-.020),
                  (.100,.989,-.037),(.148,.963,-.051),(.192,.91,-.060),
                  (.228,.76,-.060),(.247,.52,-.055),(.257,.18,-.047)]
        for forward,scale,drop in sections:
            for p in points:
                verts.append((p.x*scale,p.y+forward,.805+(p.z-.805)*scale+drop))
        for row in range(8):
            for j in range(n):
                k=(j+1)%n; a=row*n
                polys.append((a+j,a+k,a+n+k,a+n+j))
        polys.append(tuple(8*n+j for j in range(n)))
        ob=self.mesh('Cheek to nape | closed throat',verts,polys,self.throat)
        layer=ob.data.uv_layers.new(name='Cheek boundary')
        for li,loop in enumerate(ob.data.loops):
            i,j=divmod(loop.vertex_index,n)
            lateral=np.clip((abs(points[j].x)-.065)/.090,0,1)
            # Match the colored cheek flank at the seam; white continues only
            # below the chin into the bib, where the adjacent face is also white.
            u=sections[i][0]/.257+.55*lateral*lateral*(3-2*lateral)
            layer.data[li].uv=(min(.995,u),max(.01,min(.99,(points[j].z-.62)/.37)))
        bind(ob,self.arm)

    def chin_edge(self,face,body,ink,half_span,*,expressions=(),edge_lift=0):
        """Place a tapered facial boundary on the chin, immediately above the bib."""
        from mathutils.bvhtree import BVHTree
        bpy.context.view_layer.update()
        graph=bpy.context.evaluated_depsgraph_get()
        skin=BVHTree.FromObject(face,graph)
        chest=BVHTree.FromObject(body,graph)
        sampled=[skin,chest]
        for name in expressions:
            key=face.data.shape_keys.key_blocks[name]
            previous=key.value
            try:
                for strength in (.5,1.):
                    key.value=strength
                    bpy.context.view_layer.update()
                    sampled.append(BVHTree.FromObject(face,graph))
            finally:
                key.value=previous
                bpy.context.view_layer.update()
        forward=Vector((0,1,0))
        def hit(tree,x,z):
            return tree.ray_cast(Vector((x,-1.5,z)),forward,3.)[0]
        def front_depth(x,z):
            hits=[hit(tree,x,z) for tree in sampled]
            return min(pt.y for pt in hits if pt is not None)
        def visible(x,z):
            a=hit(skin,x,z);b=hit(chest,x,z)
            return a is not None and (b is None or a.y <= b.y)
        verts=[];polys=[]
        for i in range(37):
            u=i/36
            x=(2*u-1)*half_span
            low,high=.60,.739
            if not visible(x,high):
                raise ValueError(f'No exposed jaw above bib at x={x}')
            for _ in range(15):
                mid=(low+high)*.5
                if visible(x,mid):high=mid
                else:low=mid
            high+=edge_lift*(abs(x)/half_span)**1.7
            # Both edges lie on the exposed facial surface. The bottom edge
            # abuts the measured skin/bib intersection; the ends fade to a point.
            width=.00012+.0050*math.sin(math.pi*u)**.85
            for dz in (.0004,.0004+width):
                verts.append(Vector((x,front_depth(x,high+dz)-.0008,high+dz)))
            if i:polys.append((2*i-2,2*i,2*i+1,2*i-1))
        # These reference skins use comparatively large cheek triangles. At a
        # skin-triangle boundary, the middle of a quad may still cross the skin
        # although its four corners clear it. Correct only the affected quads.
        clearance=[0.]*37
        for i,(a,b,c,d) in enumerate(polys):
            for t in (.2,.5,.8):
                low=verts[a].lerp(verts[b],t)
                high=verts[d].lerp(verts[c],t)
                for s in (.2,.5,.8):
                    p=low.lerp(high,s)
                    extra=p.y-front_depth(p.x,p.z)+.00035
                    clearance[i]=max(clearance[i],extra)
                    clearance[i+1]=max(clearance[i+1],extra)
        for i,extra in enumerate(clearance):
            verts[2*i].y-=extra
            verts[2*i+1].y-=extra
        ob=self.mesh('Cheek and jaw | skin boundary',verts,polys,ink)
        bind(ob,self.arm,'head')

    def scalp(self):
        from crown_surface import make_crown
        # The angular forehead grows from the whole cap. Its points turn
        # toward the eyes while the temples flare into the cheek-side flick.
        outline=[(-math.pi,.690),(-2.48,.689),(-2.23,.723),(-1.91,.686),
                 (-1.72,.738),(-1.53,.766),(-1.34,.783),(-1.20,.854),
                 (-1.00,.870),(-.80,.905),(-.65,.937),(-.49,.917),
                 (-.39,.866),(-.29,.790),(-.21,.860),(-.12,.905),
                 (-.04,.861),(.09,.817),(.17,.881),(.31,.935),
                 (.54,.951),(.75,.920),(.85,.860),(.93,.890),
                 (1.08,.870),(1.21,.824),(1.34,.788),(1.53,.765),
                 (1.72,.740),(1.91,.690),(2.22,.725),(2.49,.692),(math.pi,.690)]
        aa,zz=zip(*outline)
        angles=sorted({round(-math.pi+i*math.tau/72,6) for i in range(72)}
                      | {round(a,6) for a in aa[:-1]})
        def surface(a,t):
            hem=np.interp(a,aa,zz)
            q=np.clip((hem-.86)/.202,-1,1)
            theta=math.acos(math.copysign(abs(q)**(1/.63),q))*t
            st=math.sin(theta);ct=math.cos(theta)
            z=.86+.202*math.copysign(abs(ct)**.63,ct)
            angle=a-.15*math.sin(math.pi*t)*math.exp(-(a/1.1)**2)
            flick=(.065*math.exp(-((abs(a)-1.53)/.25)**2)
                   +.033*math.exp(-((abs(a)-1.91)/.17)**2))*t**5
            x=(.274*st**.82+flick)*math.sin(angle)
            front=max(0,math.cos(angle))
            drop=min(1,max(0,(.955-z)/.14))
            y=-.064-.279*st*math.cos(angle)-.033*front**3*drop
            return Vector((x,y,z))
        crown=self.material('Swept crown','#FFFFFF',texture='49-crown.png')
        make_crown(self,'Hair | continuous swept crown',angles,17,surface,crown,self.strand)

    def ears(self):
        for sign,side in ((-1,'R'),(1,'L')):
            def plane(u,z,offset):
                return (sign*(.210+u*.085+.85*offset),-.208+u*.169+.23*(z-.94)-.52*offset,z)
            # Low swept fox ears sit on the sides of the crown, as in both official drawings.
            outer = [(-.58,.914),(-.66,.986),(-.55,1.041),(.40,1.054),(.90,1.060),
                     (.87,1.012),(.82,.970),(.66,.930),(.24,.880),(-.19,.861)]
            inner = [(-.44,.924),(-.43,.971),(-.13,1.004),(.51,1.032),(.823,1.050),
                     (.79,1.008),(.73,.970),(.53,.930),(.21,.898),(-.13,.879)]
            inner_tuft = [(-.37,.928),(-.38,.965),(-.15,.982),(.14,.988),(.35,.977),
                          (.44,.958),(.58,.951),(.49,.94),(.34,.922),(.12,.913),(-.13,.910)]
            # The white lining and central tuft are adjoining faces of one
            # cupped ear. Each rim ring has the same winding and start corner.
            count=32
            verts=[];faces=[];indices=[]
            for curve,offset in ((outer,-.034),(outer,0),(inner,.013),(inner_tuft,.016)):
                for j in range(count):
                    v=catmull(curve,j/count,True)
                    verts.append(plane(v.x,v.y,offset))
            for row,material in enumerate((0,0,1)):
                for j in range(count):
                    k=(j+1)%count;a=row*count
                    faces.append((a+j,a+k,a+count+k,a+count+j));indices.append(material)
            for ring,offset,material in ((0,-.036,0),(3,.019,2)):
                u=sum(q[0] for q in (outer if ring==0 else inner_tuft))/len(outer if ring==0 else inner_tuft)
                z=sum(q[1] for q in (outer if ring==0 else inner_tuft))/len(outer if ring==0 else inner_tuft)
                hub=len(verts);verts.append(plane(u,z,offset))
                for j in range(count):
                    k=(j+1)%count
                    faces.append((hub,ring*count+k,ring*count+j) if ring==0 else (hub,ring*count+j,ring*count+k))
                    indices.append(material)
            ear=self.mesh('Fox ear | rolled lining '+side,verts,faces,self.blue)
            ear.data.materials.append(self.cream);ear.data.materials.append(self.pale)
            for poly,idx in zip(ear.data.polygons,indices):poly.material_index=idx
            bind(ear,self.arm)

    def locks(self):
        def lock(name, path, widths, depths, *, axis=(1,0,0), swinging=False, mat=None):
            ob=self.tube('Hair | '+name,path,widths,depths,axis,mat or self.hair)
            if swinging:
                add_spring_chain(self.arm,ob,'Hair49_'+name.replace(' ','_'),path,
                                 parent='head', kind='hair', radius=.007)
            else:
                bind(ob,self.arm)
            return ob
        for sign,side in ((-1,'R'),(1,'L')):
            def mirror(points):
                return [(sign*x,y,z) for x,y,z in points]
            # The terminal hook points outward along the cheek in the official artwork.
            cheek=lock('cheek '+side,mirror([(.157,-.192,.979),(.215,-.215,.920),(.252,-.229,.856),(.257,-.256,.797),(.241,-.262,.745),(.251,-.258,.708),(.282,-.233,.716)]),
                       [.022,.043,.052,.044,.037,.021,0],[.016,.029,.033,.030,.021,.012,0],axis=(sign*.78,.51,0),swinging=True)
            cheek.data.materials.append(self.strand)
            for polygon in cheek.data.polygons:
                if polygon.center.z<.87 and polygon.normal.x*sign<-.42 and polygon.normal.y>-.58:
                    polygon.material_index=1
        # Low crown whorl, a shallow crescent rather than an upright antenna.
        curl=[(.021,-.249,1.037),(-.003,-.245,1.061),(-.043,-.250,1.074),(-.075,-.266,1.057),(-.087,-.291,1.030),(-.077,-.315,1.008),(-.053,-.335,.993)]
        fold=self.material('Crown crease','#426783',edge=False)
        whorl=lock('crown curl',curl,[.001,.011,.018,.020,.015,.009,0],[.001,.007,.009,.010,.008,.006,0],axis=(0,0,1))
        whorl.data.materials.append(fold)
        for poly in whorl.data.polygons:
            if poly.normal.z<-.34:poly.material_index=1

    def tails(self):
        from native_plumes_49 import build_rear
        torso=add_collider_group(self.arm,'49 back','hips',[((0,.00,.355),.265)])
        build_rear(self,json.loads((HERE/'Tails-49.json').read_text(encoding='utf8')),torso)
        for sign,side in ((-1,'R'),(1,'L')):
            # Stay narrow beside the hip and swell into two rounded forward-
            # curling lower plumes; the actual body underneath has the basis width.
            path=[(.061,.242,.345),(.241,.239,.288),(.386,.113,.209),(.425,-.075,.146),
                  (.421,-.280,.124),(.350,-.414,.152),(.294,-.493,.215),(.231,-.534,.288),(.208,-.529,.346)]
            points=[]
            for i,(x,y,z) in enumerate(path):
                t=i/(len(path)-1)
                pose=math.sin(math.pi*t*.75)
                points.append((sign*x,y+sign*.038*pose,z+sign*.024*pose))
            widths=[.018,.043,.071,.080,.116,.143,.116,.059,0]
            depths=[.018,.042,.065,.080,.108,.121,.085,.044,0]
            ob=self.tube('Tail | low wrap '+side,points,widths,depths,(sign*.22,0,.976),self.plume,textured=True)
            add_spring_chain(self.arm,ob,'Tail49_low_wrap_'+side,points,radius=.015,colliders=[torso])


def build(starter, output):
    bpy.ops.wm.open_mainfile(filepath=str(starter.resolve()))
    bpy.context.preferences.filepaths.save_version=0
    arm,body,face = (bpy.data.objects[name] for name in ('Armature','Body','Face'))
    if len(face.data.vertices)!=926 or not face.data.shape_keys:
        raise ValueError('Expected the documented #49 expression starter')
    sculpt = Sculpt(arm,body,face)
    sculpt.body(body)
    sculpt.face(face)
    sculpt.close_neck(face)
    sculpt.chin_edge(face,body,sculpt.material('Chin contour','#43434A',edge=False),.126,
                     expressions=('a','i','u','e','o','Joy','Fun','Sorrow'))
    sculpt.scalp()
    sculpt.locks()
    sculpt.ears()
    sculpt.tails()
    bpy.context.scene.name = 'Corefolder 49 - Yochika'
    output.mkdir(parents=True,exist_ok=True)
    return save_character(arm,sculpt.items,output/'Corefolder-49.blend',output/'Corefolder-49.vrm',
                          title='Corefolder-49 Yochika',version='1.0',character_number=49)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--starter',type=Path,default=ROOT/'.cache/vrm-5.3-tests/verified-20261125/Corefolder-49/Corefolder-49-Starter.blend')
    parser.add_argument('--out',type=Path,default=HERE)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    build(args.starter,args.out)
