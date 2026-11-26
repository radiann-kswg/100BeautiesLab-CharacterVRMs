"""Hakko's sculpt and UVs, starting from the expression-enabled #85 Refined scene."""
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'Corefolder-49/Modeling'))
from model_49 import Sculpt,catmull,bind,linear,independent_iris_uv,restore_body_surface
from refine_models import toon
from face_articulation import finish_face


class Hakko(Sculpt):
    def __init__(self,arm,collection,body,face):
        self.arm,self.collection=arm,collection
        self.items=[body,face]
        self.hair=self.swatch('Chestnut fur','#C48455',factor=.77)
        self.lockmat=self.swatch('Chestnut strands','#FFFFFF',image='85-hair.png')
        self.under=self.swatch('Chestnut undercoat','#BD7B4D',factor=.77)
        self.skin=self.swatch('Expression atlas','#FFFFFF',image='85-face.png',mask=True)
        self.bodymat=self.swatch('White bib and brown flank','#FFFFFF',image='85-body.png')
        self.throat=self.swatch('Cheek to neck','#FFFFFF',image='85-neck.png',edge=0)
        self.earmats={s:self.swatch('Fur ear '+s,'#FFFFFF',image='85-ear-'+s+'.png') for s in ('R','L')}
        self.cord=self.swatch('Silver necklace','#D1D0CC',edge=.0004)
        self.rim=self.swatch('Petrol pendant rim','#224958',edge=.0006)
        self.stone=self.swatch('Cyan pendant','#00BACB',factor=.83,edge=0)
        self.gloss=self.swatch('Pendant light','#67DBE4',factor=.90,edge=0)

    def swatch(self,name,color,*,image=None,mask=False,edge=.0008,factor=1.):
        m=toon('85 '+name,color,edge)
        p=m.vrm_addon_extension.mtoon1
        rgb=tuple(v*factor for v in linear(color))
        p.pbr_metallic_roughness.base_color_factor=(*rgb,1)
        t=p.extensions.vrmc_materials_mtoon
        t.shade_color_factor=tuple(v*(.96 if image else .9) for v in rgb)
        t.shading_shift_factor=1.
        t.shading_toony_factor=1.
        t.gi_equalization_factor=.86
        t.outline_color_factor=linear('#66513E')
        t.outline_lighting_mix_factor=.12
        if image:
            tex=bpy.data.images.load(str(HERE/image),check_existing=True)
            p.pbr_metallic_roughness.base_color_texture.index.source=tex
            t.shade_multiply_texture.index.source=tex
        if mask: p.alpha_mode='MASK'; p.alpha_cutoff=.49
        return m

    def body_and_face(self,body,face):
        restore_body_surface(body)
        bpy.ops.object.select_all(action='DESELECT')
        body.select_set(True);bpy.context.view_layer.objects.active=body
        dec=body.modifiers.new('Recover common body quad rings','DECIMATE')
        dec.decimate_type='UNSUBDIV';dec.iterations=2
        bpy.ops.object.modifier_move_to_index(modifier=dec.name,index=0)
        bpy.ops.object.modifier_apply(modifier=dec.name)
        from torso_profile import fit_common_torso
        fit_common_torso(body)
        body.data.materials.clear();body.data.materials.append(self.bodymat)
        for layer in list(body.data.uv_layers):body.data.uv_layers.remove(layer)
        uv=body.data.uv_layers.new(name='85 spherical bib')
        for p in body.data.polygons:
            p.material_index=0;p.use_smooth=True
            vals=[]
            for idx in p.vertices:
                x,y,z=body.data.vertices[idx].co
                vals.append((.5+math.atan2(x,-(y+.07))/math.tau,min(1,z/.713)))
            wraps=max(q[0] for q in vals)-min(q[0] for q in vals)>.5
            for li,(u,v) in zip(p.loop_indices,vals):uv.data[li].uv=(u+1 if wraps and u<.5 else u,v)

        face.data.materials.clear()
        face.data.materials.append(self.skin)
        for p in face.data.polygons:
            p.material_index=0
            p.use_smooth=True
        independent_iris_uv(face)
        # Use the final mouth and supporting skin to place the edge in all its
        # real poses. save_character detects the completed articulation pass.
        finish_face(85,face,self.arm)
        from torso_profile import add_cranial_base
        self.items.append(add_cranial_base(self.arm,face,85,self.collection))

    def cranium(self):
        # A continuous fringe grows from the rounded crown. The reference
        # models carry the long bang on the forehead surface down to its hem.
        hem=[(-math.pi,.686),(-2.25,.705),(-1.90,.677),(-1.61,.724),(-1.35,.727),(-1.15,.789),
             (-1.00,.841),(-.83,.814),(-.67,.882),(-.47,.927),(-.30,.937),
             (-.16,.918),(0,.861),(.135,.806),(.225,.767),(.30,.827),
             (.44,.897),(.57,.924),(.73,.903),(.93,.841),(1.045,.812),
             (1.12,.825),(1.35,.738),(1.61,.724),(1.90,.679),(2.25,.705),(math.pi,.686)]
        angles=sorted({round(-math.pi+j*math.tau/54,5) for j in range(54)}
                      | {round(a,5) for a,z in hem[:-1]})
        aa,hh=zip(*hem)
        def surface(angle,progress):
            bottom=float(np.interp(angle,aa,hh))
            theta=math.acos((bottom-.901)/.246)*progress
            st=math.sin(theta)
            nape=.032*math.exp(-((abs(angle)-1.88)/.27)**2)*progress**5
            x=(.252*st+nape)*math.sin(angle)
            z=.901+.246*math.cos(theta)
            y=-.053-.263*st*math.cos(angle)
            front=max(0,math.cos(angle))**2.4
            # Keep the forward hem just over the forehead and continue it into
            # the lateral hair; it never forms a hanging row of separate ovals.
            spread=max(0,min(1,(1.075-z)/.22))
            y-=front*(.047+.026*max(0,(.86-z)/.10))*spread
            return Vector((x,y,z))
        from crown_surface import make_crown
        crown=self.swatch('Swept crown','#FFFFFF',image='85-crown.png')
        ears=[(-1,(-.156,-.033,1.217),self.earmats['R']),
              (1,(.113,.023,1.202),self.earmats['L'])]
        make_crown(self,'Hair crown, ears and swept fringe',angles,16,surface,crown,self.under,ears)

    def hairstyle(self):
        def lock(name,p,w,d,axis=(1,0,0),spring=False,mat=None):
            ob=self.tube(name,p,w,d,axis,mat or self.lockmat,textured=True)
            bind(ob,self.arm,'head')
            if spring:ob['spring_path']=json.dumps(p)
            return ob
        for side,s in [('R',-1),('L',1)]:
            # Its skinning line remains lateral to the reference eyeballs.
            p=[(s*.178,-.150,1.000),(s*.212,-.190,.949),(s*.240,-.213,.881),(s*.254,-.225,.803),
               (s*.242,-.251,.748),(s*.208,-.273,.700)]
            cheek=lock('Hair cheek '+side,p,[.023,.039,.043,.041,.028,0],[.019,.027,.035,.035,.024,0],
                       axis=(s*.80,.52,0),spring=True)
            cheek.data.materials.append(self.under)
            for polygon in cheek.data.polygons:
                if polygon.center.z<.875 and polygon.normal.x*s<-.42 and polygon.normal.y>-.58:
                    polygon.material_index=1
        p=[(-.141,.030,1.049),(-.193,.089,1.082),(-.249,.141,1.069),(-.295,.158,1.011),
           (-.304,.132,.947),(-.292,.096,.888),(-.261,.070,.828),(-.222,.061,.762)]
        lock('Hair ponytail',p,[.039,.072,.082,.085,.077,.064,.041,0],[.034,.059,.073,.076,.070,.057,.035,0],
             axis=(.76,-.38,0),spring=True)
        q=[(-.251,.141,1.056),(-.298,.154,1.029),(-.334,.162,.991),(-.356,.171,.973),(-.379,.183,.983)]
        lock('Hair ponytail fork',q,[.027,.042,.035,.019,0],[.017,.031,.028,.014,0],
             axis=(.73,-.35,.2),spring=True)

    def pendant(self,body,face):
        def surface(x,z):
            hits=[]
            for ob in (body,face):
                ok,v,_,_=ob.ray_cast(Vector((x,-1.5,z)),Vector((0,1,0)),distance=3)
                if ok:hits.append(v.y)
            return min(hits) if hits else -.19
        bpy.context.view_layer.update()
        from mathutils.interpolate import poly_3d_calc
        # The necklace is a separate closed loop over the unadorned character.
        # Cast to the body and skull at each station, then transfer that
        # location's skin weights so the piece can follow the neck and chest.
        supports=[body,face]
        cranium=bpy.data.objects.get('Corefolder Cranial Base')
        if cranium:supports.append(cranium)
        count=96;sides=8;path=[];normals=[];weights=[]
        for i in range(count):
            angle=math.tau*i/count
            theta=min(angle,math.tau-angle)
            z=np.interp(theta,[0,.16,.34,.54,.74,.98,1.24,1.57,2.12,2.65,math.pi],
                              [.506,.527,.565,.614,.647,.669,.683,.690,.695,.698,.699])
            radial=Vector((math.sin(angle),-math.cos(angle),0))
            outside=Vector((0,-.046,z))+radial
            hits=[]
            for ob in supports:
                ok,q,normal,j=ob.ray_cast(outside,-radial,distance=1.30)
                if ok:hits.append(((q-outside).length,ob,q,normal,j))
            if not hits:raise ValueError(f'No nude surface for necklace station {i}')
            _,ob,q,normal,j=min(hits,key=lambda h:h[0])
            normal=normal.normalized()
            if normal.dot(radial)<0:normal=-normal
            path.append(q+normal*.0042);normals.append(normal)
            poly=ob.data.polygons[j]
            corners=[ob.data.vertices[k] for k in poly.vertices]
            blend=poly_3d_calc([v.co for v in corners],q)
            samples={}
            for k,v in enumerate(corners):
                for w in v.groups:
                    name=ob.vertex_groups[w.group].name
                    if self.arm.data.bones.get(name) and blend[k]>0:
                        samples[name]=samples.get(name,0)+w.weight*blend[k]
            weights.append(samples or {'chest':1})
        verts=[];faces=[]
        for i,p in enumerate(path):
            tangent=(path[(i+1)%count]-path[i-1]).normalized()
            side=tangent.cross(normals[i]).normalized()
            away=side.cross(tangent).normalized()
            for j in range(sides):
                a=math.tau*j/sides
                verts.append(p+.0025*(side*math.cos(a)+away*math.sin(a)))
            for j in range(sides):
                k=(j+1)%sides;n=(i+1)%count
                faces.append((i*sides+j,i*sides+k,n*sides+k,n*sides+j))
        # An edge spanning the chest / skull join can touch the neighboring
        # surface before its endpoints do. Clear those segments in their own
        # horizontal section, keeping each round cord section intact.
        for _ in range(3):
            shift=[0.]*count
            for i in range(count):
                n=(i+1)%count
                for j in range(sides):
                    a=verts[i*sides+j];b=verts[n*sides+j]
                    for p in (a,(a+b)*.5):
                        ray=Vector((p.x,p.y+.046,0)).normalized()
                        for ob in supports:
                            ok,hit,_,_=ob.ray_cast(p+ray,-ray,distance=1.4)
                            if ok:
                                extra=(hit-p).dot(ray)+.0005
                                shift[i]=max(shift[i],extra)
                                shift[n]=max(shift[n],extra)
            if max(shift)<.00002:break
            for i,amount in enumerate(shift):
                delta=Vector((path[i].x,path[i].y+.046,0)).normalized()*amount
                for j in range(sides):verts[i*sides+j]+=delta
        chain=self.mesh('Necklace | fitted silver cord',verts,faces,self.cord)
        groups={}
        for i in range(count):
            # Smooth the seam between adjacent head- and chest-weighted areas.
            smooth={}
            for j,f in ((i-1,.2),(i,.6),((i+1)%count,.2)):
                for name,w in weights[j].items():smooth[name]=smooth.get(name,0)+f*w
            total=sum(smooth.values())
            for name,w in smooth.items():
                if name not in groups:groups[name]=chain.vertex_groups.new(name=name)
                groups[name].add(list(range(i*sides,(i+1)*sides)),w/total,'REPLACE')
        chain.parent=self.arm;chain.modifiers.new('Armature','ARMATURE').object=self.arm
        def drop(name,scale,offset,mat):
            zs=[.390,.401,.423,.454,.477,.500]
            ws=[.0007,.025,.038,.031,.017,.0005]
            n,rows=20,17;vs=[];fs=[]
            for i in range(rows):
                t=i/(rows-1);z=.444+(np.interp(t,np.linspace(0,1,len(zs)),zs)-.444)*scale
                w=scale*max(.0004,catmull([(v,0) for v in ws],t).x)
                for j in range(n):
                    a=math.tau*j/n;x=w*math.cos(a)
                    vs.append((x,surface(x,z)-offset+.36*w*math.sin(a),z))
            for i in range(rows-1):
                for j in range(n):
                    k=(j+1)%n;v=i*n;fs.append((v+j,v+k,v+n+k,v+n+j))
            fs.extend((tuple(reversed(range(n))),tuple((rows-1)*n+j for j in range(n))))
            ob=self.mesh(name,vs,fs,mat);bind(ob,self.arm,'chest')
        drop('Teardrop pendant',1,.015,self.rim)
        drop('Pendant inset cyan',.82,.022,self.stone)
        p=[(-.010,surface(0,.471)-.031,.471),(-.015,surface(0,.458)-.033,.458),(-.016,surface(0,.445)-.035,.445)]
        ob=self.tube('Pendant inset highlight',p,[0,.0028,0],[0,.0018,0],(1,0,0),self.gloss);bind(ob,self.arm,'chest')
        # A closed dark metal eyelet physically connects both necklace halves.
        y=surface(0,.506)-.008
        path=[(.006*math.sin(math.tau*i/8),y,.505+.0065*math.cos(math.tau*i/8)) for i in range(9)]
        ob=self.tube('Pendant bail',path,[.0021]*5,[.0021]*5,(0,1,0),self.rim);bind(ob,self.arm,'chest')
        for ob in self.items:
            if ob.name.startswith(('Necklace','Teardrop pendant','Pendant ')):
                ob['corefolder_layer']='Outfit'


def revise(arm,collection):
    body,face=(bpy.data.objects[k] for k in ('Body','Face'))
    prefixes=('Hair','Fox ear','Necklace','Teardrop','Pendant','White belly fur')
    for ob in list(collection.objects):
        if ob.type=='MESH' and ob.name.startswith(prefixes):
            bpy.data.objects.remove(ob,do_unlink=True)
    h=Hakko(arm,collection,body,face)
    h.body_and_face(body,face)
    h.cranium();h.hairstyle();h.pendant(body,face)
    return {ob.name:json.loads(ob['spring_path']) for ob in h.items if 'spring_path' in ob}
