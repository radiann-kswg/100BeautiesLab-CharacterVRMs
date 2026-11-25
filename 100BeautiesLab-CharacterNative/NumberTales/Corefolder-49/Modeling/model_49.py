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
from corefolder_springs import add_collider_group, add_spring_chain, save_character
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
        bpy.ops.object.select_all(action='DESELECT')
        body.select_set(True)
        bpy.context.view_layer.objects.active=body
        dec=body.modifiers.new('Restore native quad density','DECIMATE')
        dec.decimate_type='UNSUBDIV'
        dec.iterations=2
        bpy.ops.object.modifier_move_to_index(modifier=dec.name,index=0)
        bpy.ops.object.modifier_apply(modifier=dec.name)
        body.data.materials.clear()
        body.data.materials.append(self.belly)
        layer = body.data.uv_layers.new(name='49 wrapped belly')
        body.data.uv_layers.active = layer
        layer.active_render = True
        for v in body.data.vertices:
            # The illustration fills out below the cheeks, then tapers at the base.
            z = v.co.z
            v.co.x *= 1.223+.082*math.sin(math.pi*min(1,z/.72))**1.3+.058*math.exp(-((z-.59)/.14)**2)
            v.co.y=-.07+(v.co.y+.07)*(1.075+.025*math.exp(-((z-.19)/.17)**2))
            if v.co.y<-.10:
                v.co.y-=.008*math.exp(-((z-.65)/.06)**2-(v.co.x/.12)**2)
        for p in body.data.polygons:
            p.material_index=0
            p.use_smooth=True
            uv = []
            for vi in p.vertices:
                q = body.data.vertices[vi].co
                uv.append((.5+math.atan2(q.x/1.165,-(q.y+.07))/math.tau, min(1,q.z/.713)))
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
        # Apply a continuous affine warp to each key. It changes the resting face and
        # applies the same Jacobian to the lid, eye, lip and phoneme displacements.
        rest = [v.co.copy() for v in face.data.shape_keys.key_blocks[0].data]
        for key in face.data.shape_keys.key_blocks:
            for q,base in zip(key.data,rest):
                x,y,z = base
                ax = abs(x)
                eye = math.exp(-((ax-.117)/.093)**6-((z-.825)/.104)**6)
                q.co.z -= eye*.32*(q.co.z-.797)
                q.co.z -= eye*.040*(ax-.112)
                q.co.x += eye*(math.copysign(.033,x)+.09*(q.co.x-math.copysign(.112,x)))

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
            layer.data[li].uv=(sections[i][0]/.257,max(.01,min(.99,(points[j].z-.62)/.37)))
        bind(ob,self.arm)

    def scalp(self):
        count, rows = 44, 13
        v, f = [(0,-.064,1.062)], []
        for i in range(1,rows+1):
            for j in range(count):
                a = math.tau*j/count
                ang = min(a,math.tau-a)
                # Lower hem follows the temples, then the rounded nape.
                zmin = np.interp(ang,[0,.48,.77,1.01,1.26,1.51,2.05,math.pi],
                                 [.95,.960,.923,.837,.750,.709,.682,.679])
                if ang>1.15:
                    zmin += .012*math.cos(7*a)
                q=np.clip((zmin-.86)/.202,-1,1)
                theta = math.acos(math.copysign(abs(q)**(1/.54),q))*i/rows
                # The crown in both artworks stays high out to the lateral ears.
                s=math.sin(theta); c=math.cos(theta)
                v.append((.274*s**.80*math.sin(a),-.064-.278*s*math.cos(a),
                          .86+.202*math.copysign(abs(c)**.54,c)))
        v.append((0,-.06,.786))
        for j in range(count):
            k=(j+1)%count
            f.append((0,1+j,1+k))
            for i in range(rows-1):
                a=1+i*count
                f.append((a+j,a+k,a+count+k,a+count+j))
            f.append((len(v)-1,1+(rows-1)*count+k,1+(rows-1)*count+j))
        cap=self.mesh('Hair | rounded occiput and nape',v,f,self.hair)
        bind(cap,self.arm)

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
            self.plate('Fox ear shell '+side,outer,plane,self.blue,.027,.043)
            self.plate('Ivory ear rim '+side,inner,lambda u,z,d:plane(u,z,d+.030),self.cream,.003,.002)
            self.plate('Ice blue ear tuft '+side,inner_tuft,lambda u,z,d:plane(u,z,d+.037),self.pale,.005,.002)

    def locks(self):
        def lock(name, path, widths, depths, *, axis=(1,0,0), swinging=False, mat=None):
            ob=self.tube('Hair | '+name,path,widths,depths,axis,mat or self.hair)
            if swinging:
                add_spring_chain(self.arm,ob,'Hair49_'+name.replace(' ','_'),path,
                                 parent='head', kind='hair', radius=.007)
            else:
                bind(ob,self.arm)
            return ob
        # Three interleaving, asymmetrical forelocks. The longest curves past the
        # character's right brow; the middle one turns toward the opposite eye.
        lock('right sweep',[(-.023,-.177,1.044),(-.066,-.268,1.003),(-.083,-.324,.939),(-.087,-.352,.874),(-.085,-.357,.817),(-.064,-.365,.779)],
             [.027,.060,.059,.047,.026,0],[.014,.024,.027,.022,.014,0])
        lock('middle forelock',[(.003,-.189,1.039),(-.010,-.275,.990),(-.033,-.323,.932),(-.049,-.349,.871),(-.042,-.357,.832),(-.015,-.361,.798)],
             [.030,.057,.049,.039,.022,0],[.016,.026,.026,.020,.012,0])
        lock('left brow sweep',[(.005,-.187,1.046),(.065,-.257,1.013),(.133,-.295,.967),(.183,-.281,.921),(.203,-.263,.868)],
             [.033,.076,.069,.054,0],[.016,.024,.027,.018,0],axis=(.8,.32,0))
        for sign,side in ((-1,'R'),(1,'L')):
            def mirror(points):
                return [(sign*x,y,z) for x,y,z in points]
            # The terminal hook points outward along the cheek in the official artwork.
            lock('cheek '+side,mirror([(.172,-.220,.974),(.220,-.220,.920),(.248,-.235,.856),(.251,-.264,.797),(.231,-.273,.745),(.247,-.265,.708),(.282,-.233,.716)]),
                 [.022,.043,.055,.047,.040,.022,0],[.016,.029,.033,.030,.021,.012,0],axis=(sign*.78,.51,0),swinging=True)
            lock('temple flick '+side,mirror([(.214,-.096,.933),(.235,-.141,.873),(.252,-.158,.811),(.277,-.148,.772),(.311,-.123,.755),(.350,-.093,.770)]),
                 [.021,.046,.055,.049,.027,0],[.016,.031,.039,.036,.021,0],axis=(sign*.61,.77,0))
            lock('nape '+side,mirror([(.184,.052,.868),(.228,.066,.827),(.242,.069,.767),(.259,.085,.716),(.300,.121,.702)]),
                 [.032,.055,.059,.038,0],[.020,.039,.043,.026,0],axis=(sign*.62,-.75,0))
            lock('nape undercurl '+side,mirror([(.104,.148,.821),(.161,.130,.782),(.189,.133,.728),(.218,.156,.682),(.261,.180,.676)]),
                 [.027,.051,.054,.036,0],[.014,.036,.038,.021,0],axis=(sign*.7,-.55,0),mat=self.strand)
        # Low crown whorl, a shallow crescent rather than an upright antenna.
        curl=[(.021,-.249,1.037),(-.003,-.245,1.061),(-.043,-.250,1.074),(-.075,-.266,1.057),(-.087,-.291,1.030),(-.077,-.315,1.008),(-.053,-.335,.993)]
        fold=self.material('Crown crease','#426783',edge=False)
        lock('curl crease',[(x,y+.003,z-.002) for x,y,z in curl],
             [.001,.013,.021,.023,.018,.011,0],[.001,.006,.007,.007,.006,.005,0],axis=(0,0,1),mat=fold)
        lock('crown curl',curl,[.001,.011,.018,.020,.015,.009,0],[.001,.007,.009,.010,.008,.006,0],axis=(0,0,1))

    def tails(self):
        torso=add_collider_group(self.arm,'49 back', 'hips', [((0,.00,.355),.265)])
        self.rear_lobes(torso)
        # These two broad hooks sweep around the sides into the foreground.
        # The back unit flattens their distal curvature when viewed in isolation.
        tail_designs = [
           ('low wrap',[(.042,.260,.348),(.310,.268,.259),(.482,.074,.184),(.485,-.150,.157),(.408,-.349,.161),(.312,-.467,.192),(.223,-.539,.254),(.188,-.551,.345)],
             [.018,.066,.126,.161,.180,.169,.112,0],[.018,.064,.108,.136,.158,.138,.092,0],(.17,0,.985)),
        ]
        for name,path,widths,depths,axis in tail_designs:
            for sign,side in ((-1,'R'),(1,'L')):
                def wrap_position(x,y,z):
                    # Narrow the low flank toward its seated rear silhouette.
                    # Keep the pale end above the hips, turned around the bib.
                    amount=max(0.,min(1.,(.36-z)/.22))
                    return (x*(1-.094*amount),y,z+.025*amount)
                points=[(sign*x,y,z) for x,y,z in path]
                ob=self.tube('Tail | '+name+' '+side,points,widths,depths,(sign*axis[0],*axis[1:]),self.plume,textured=True)
                for v in ob.data.vertices:v.co=wrap_position(*v.co)
                points=[wrap_position(*p) for p in points]
                add_spring_chain(self.arm,ob,'Tail49_'+name.replace(' ','_')+'_'+side,points,radius=.015,colliders=[torso])

    def rear_lobes(self,collider):
        source=json.loads((HERE/'Tails-49.json').read_text(encoding='utf-8'))
        w,h=source['size']
        span=1.23
        locations=[('upper inner R',(178,11),.045),('upper inner L',(344,10),.045),
                   ('upper outer R',(75,69),-.032),('upper outer L',(451,69),-.032),
                   ('low outside R',(9,231),.006),('low outside L',(523,231),.006),
                   None,None,('low middle',(268,464),.095)]
        mat=self.material('Rear plume atlas','#FFFFFF',texture='Tails-49.png')
        toon=mat.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon
        toon.outline_width_mode='none';toon.outline_width_factor=0.
        toon.shade_color_factor=(1,1,1)
        frontmat=self.material('Forward facing plume','#FFFFFF',texture='49-tail.png',edge=False)
        for rec,loc in zip(source['plumes'],locations):
            if loc is None:continue
            name,tip,layer=loc
            center=Vector(rec['center'])
            outline=[Vector(p) for p in rec['outline']]
            root=Vector((.04*math.copysign(1,center.x-w/2) if abs(center.x-w/2)>30 else 0,.267,.37))
            def projected(p):
                x=(p.x-w/2)*span/(w-12)
                z=.017+(h-6-p.y)*span/(w-12)
                # Behind the torso, the upper plumage tilts down into the
                # shoulder line; the two lateral fans stay visible in oblique view.
                z-=.36*max(0.,z-.868)
                if name.startswith('upper'):
                    x*=1.-.14*max(0.,min(1.,(z-.74)/.21))
                    z-=.047*max(0.,min(1.,(abs(x)-.18)/.23))*max(0.,min(1.,(z-.65)/.17))
                if name=='low middle':z-=.075*max(0.,1-z/.26)**1.3
                side=abs(x)/(.50*span)
                y=.400-.095*side**1.65+layer
                y-=.20*max(0.,z-.76)/.32
                if name.startswith('low outside'):y+=.245*side**1.35
                return Vector((x,y,z))
            vs=[];fs=[];uvs=[]
            def vert(p,offset=0,root_mix=0):
                xyz=projected(p);xyz.y+=offset
                vs.append(tuple(xyz.lerp(root,root_mix)))
                x0,y0,x1,y1=rec['crop'];tx,ty=rec['tile']
                uvs.append(((tx+.5+(p.x-x0)/(x1-x0)*251)/1024,1-(ty+.5+(p.y-y0)/(y1-y0)*251)/1024))
                return len(vs)-1
            front=vert(center,-.12,1.)
            rings=[]
            for ang in (18,45,72,90,119,150):
                a=math.radians(ang)
                rings.append([vert(center.lerp(q,math.sin(a)),-math.cos(a)*(.152 if ang<90 else .140),
                                   max(0,math.cos(a))**3*.93) for q in outline])
            back=vert(center,.14)
            for j in range(len(outline)):
                k=(j+1)%len(outline)
                fs.append((front,rings[0][j],rings[0][k]))
                for a,b in zip(rings,rings[1:]):fs.append((a[j],a[k],b[k],b[j]))
                fs.append((rings[-1][j],rings[-1][k],back))
            ob=self.mesh('Tail | '+name,vs,fs,mat)
            ob.data.materials.append(frontmat)
            uv=ob.data.uv_layers.new(name='49 official plume')
            for p in ob.data.polygons:
                frontside=max(p.vertices)<=rings[3][-1] and not name.startswith('low middle')
                if frontside:
                    p.material_index=1
                for li in p.loop_indices:
                    vi=ob.data.loops[li].vertex_index
                    coords=uvs[vi]
                    if frontside:
                        vertex=Vector(vs[vi])
                        delta=vertex-root
                        tip_delta=projected(Vector(tip))-root
                        length=max(.08,math.hypot(tip_delta.x,tip_delta.z))
                        progress=min(1,math.hypot(delta.x,delta.z)/length)
                        coords=(min(.99,max(.01,.5+.6*delta.x)),progress**1.90)
                    uv.data[li].uv=coords
            mid=projected(center);end=projected(Vector(tip))
            path=[root,root.lerp(mid,.50),mid,mid.lerp(end,.63),end]
            add_spring_chain(self.arm,ob,'Tail49_'+name.replace(' ','_'),path,radius=.013,colliders=[collider])


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
