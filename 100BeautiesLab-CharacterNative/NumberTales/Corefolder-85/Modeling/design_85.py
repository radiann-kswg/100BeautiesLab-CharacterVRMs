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
from model_49 import Sculpt,catmull,bind,linear
from refine_models import toon


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
        bpy.ops.object.select_all(action='DESELECT')
        body.select_set(True);bpy.context.view_layer.objects.active=body
        dec=body.modifiers.new('Recover common body quad rings','DECIMATE')
        dec.decimate_type='UNSUBDIV';dec.iterations=2
        bpy.ops.object.modifier_move_to_index(modifier=dec.name,index=0)
        bpy.ops.object.modifier_apply(modifier=dec.name)
        body.data.materials.clear();body.data.materials.append(self.bodymat)
        for layer in list(body.data.uv_layers):body.data.uv_layers.remove(layer)
        uv=body.data.uv_layers.new(name='85 spherical bib')
        for v in body.data.vertices:
            x,y,z=v.co
            v.co.x *= 1.218+.046*math.exp(-((z-.14)/.15)**2)+.036*math.exp(-((z-.60)/.13)**2)
            v.co.y=-.07+(y+.07)*(1.083+.043*math.exp(-((z-.15)/.19)**2))
            profile=min(1,max(0,(z-.35)/.36))**1.35
            around=min(1,max(0,(y+.25)/.44+abs(x)*1.9))
            v.co.z+=profile*(.015+.113*around)
        for p in body.data.polygons:
            p.material_index=0;p.use_smooth=True
            vals=[]
            for idx in p.vertices:
                x,y,z=body.data.vertices[idx].co
                vals.append((.5+math.atan2(x/1.16,-(y+.07))/math.tau,min(1,z/.84)))
            wraps=max(q[0] for q in vals)-min(q[0] for q in vals)>.5
            for li,(u,v) in zip(p.loop_indices,vals):uv.data[li].uv=(u+1 if wraps and u<.5 else u,v)

        face.data.materials.clear()
        face.data.materials.append(self.skin)
        for p in face.data.polygons:
            p.material_index=0
            p.use_smooth=True
        rest=[v.co.copy() for v in face.data.shape_keys.key_blocks[0].data]
        keys=face.data.shape_keys.key_blocks
        for key in keys:
            for q,r in zip(key.data,rest):
                x,y,z=r;ax=abs(x)
                eye=math.exp(-((ax-.105)/.096)**6-((z-.805)/.083)**6)
                q.co.x+=math.copysign(.019,x)*eye
                # Restore the recognizable turquoise eyes below their straight
                # upper lids while retaining the original blink displacement.
                q.co.z+=eye*.19*(q.co.z-.774)
        self.close_neck(face)

    def cranium(self):
        n,rows=48,15
        vs=[(0,-.037,1.163)];fs=[]
        for i in range(1,rows+1):
            for j in range(n):
                a=math.tau*j/n; ang=min(a,math.tau-a)
                hem=np.interp(ang,[0,.5,.83,1.08,1.39,1.65,2.07,math.pi],
                               [.938,.925,.865,.785,.730,.703,.696,.686])
                z0=.909
                theta=math.acos(np.clip((hem-z0)/.254,-1,1))*i/rows
                vs.append((.251*math.sin(theta)*math.sin(a),-.053-.263*math.sin(theta)*math.cos(a),
                           z0+.254*math.cos(theta)))
        vs.append((0,-.04,.74))
        for j in range(n):
            k=(j+1)%n;fs.append((0,1+j,1+k))
            for i in range(rows-1):
                p=1+i*n;fs.append((p+j,p+k,p+n+k,p+n+j))
            fs.append((len(vs)-1,1+(rows-1)*n+k,1+(rows-1)*n+j))
        ob=self.mesh('Hair rounded cranium',vs,fs,self.hair);bind(ob,self.arm)

    def ears(self):
        # Asymmetric, broad-based lobes continue the triangular crown seen in
        # the official front-right view; their bases lie inside the hair mass.
        for side,sgn in [('R',-1),('L',1)]:
            rings,sides=17,24
            if side=='R':
                path=[(.175,-.045,.857),(.201,-.046,.962),(.209,-.044,1.059),(.185,-.036,1.165),(.137,-.022,1.263)]
                widths=[.039,.093,.090,.052,0];depths=[.046,.139,.131,.080,0]
            else:
                path=[(.139,-.030,.895),(.158,-.030,.987),(.159,-.011,1.073),(.124,.010,1.164),(.088,.025,1.252)]
                widths=[.053,.117,.102,.057,0];depths=[.051,.140,.130,.073,0]
            vs=[];fs=[];uvs=[]
            for i in range(rings):
                t=i/(rings-1);p=catmull(path,t)
                w=max(.0004,catmull([(a,0) for a in widths],t).x)
                d=max(.0004,catmull([(a,0) for a in depths],t).x)
                for j in range(sides):
                    a=(j/sides-.5)*math.tau
                    vs.append((sgn*(p.x+w*math.cos(a)),p.y+d*math.sin(a),p.z))
                    uvs.append((j/sides,t))
            for i in range(rings-1):
                for j in range(sides):
                    k=(j+1)%sides;u=i*sides;fs.append((u+j,u+k,u+sides+k,u+sides+j))
            fs.extend((tuple(reversed(range(sides))),tuple((rings-1)*sides+j for j in range(sides))))
            ob=self.mesh('Fox ear '+side,vs,fs,self.earmats[side]);bind(ob,self.arm)
            uv=ob.data.uv_layers.new(name='Copper inner ear')
            for p in ob.data.polygons:
                wrap=0 in [v%sides for v in p.vertices] and sides-1 in [v%sides for v in p.vertices]
                for li in p.loop_indices:
                    u,v=uvs[ob.data.loops[li].vertex_index];uv.data[li].uv=(u+1 if wrap and u==0 else u,v)

    def hairstyle(self):
        def lock(name,p,w,d,axis=(1,0,0),spring=False,mat=None):
            ob=self.tube(name,p,w,d,axis,mat or self.lockmat,textured=True)
            bind(ob,self.arm,'head')
            if spring:ob['spring_path']=json.dumps(p)
            return ob
        # A single long central point breaks the brow line. Adjacent fringe
        # panels sweep outwards, clearing the full near iris in the DB pose.
        lock('Hair central tapered fringe',[(-.011,-.117,1.145),(-.020,-.214,1.075),(-.020,-.286,.996),(.008,-.332,.914),(.039,-.355,.849),(.069,-.352,.767)],
             [.024,.086,.090,.077,.048,0],[.016,.044,.048,.041,.028,0])
        lock('Hair fringe R',[(-.047,-.127,1.142),(-.104,-.221,1.062),(-.145,-.276,.990),(-.171,-.300,.910),(-.192,-.296,.837)],
             [.036,.076,.075,.053,0],[.015,.033,.039,.030,0],axis=(.88,-.27,0))
        lock('Hair fringe L',[(.043,-.116,1.146),(.093,-.202,1.086),(.147,-.266,1.008),(.199,-.279,.921),(.209,-.268,.836)],
             [.037,.081,.080,.047,0],[.018,.037,.043,.029,0],axis=(.85,.33,0))
        for side,s in [('R',-1),('L',1)]:
            p=[(s*.173,-.199,1.005),(s*.207,-.228,.938),(s*.231,-.249,.870),(s*.226,-.270,.795),
               (s*.205,-.294,.736),(s*.160,-.308,.696)]
            lock('Hair cheek '+side,p,[.031,.056,.061,.054,.033,0],[.016,.033,.038,.035,.019,0],
                 axis=(s*.80,.52,0),spring=True)
            p=[(s*.206,.023,.956),(s*.245,.038,.895),(s*.250,.045,.823),(s*.240,.067,.757),(s*.273,.099,.720)]
            lock('Hair nape '+side,p,[.029,.051,.054,.033,0],[.022,.032,.035,.021,0],axis=(s*.76,-.62,0),mat=self.under)
        p=[(-.153,.092,1.049),(-.205,.151,1.088),(-.264,.149,1.071),(-.305,.116,1.007),
           (-.313,.099,.936),(-.291,.102,.856),(-.255,.125,.802),(-.222,.153,.758)]
        lock('Hair ponytail',p,[.033,.063,.075,.082,.075,.065,.039,0],[.028,.046,.056,.064,.057,.044,.025,0],
             axis=(.76,-.38,0),spring=True)
        q=[(-.260,.142,1.050),(-.311,.152,1.026),(-.340,.158,.985),(-.360,.172,.971),(-.384,.187,.983)]
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
        for s in (-1,1):
            path=[]
            for x,z in [(0,.532),(.060,.548),(.125,.582),(.179,.633),(.205,.695),(.208,.750),(.182,.811)]:
                path.append((s*x,surface(s*x,z)-.004,z))
            ob=self.tube('Necklace '+str(s),path,[.0025]*7,[.0025]*7,(0,0,1),self.cord)
            bind(ob,self.arm,'chest')
        def drop(name,scale,offset,mat):
            zs=[.414,.427,.451,.480,.500,.524]
            ws=[.0007,.022,.035,.031,.018,.0005]
            n,rows=20,17;vs=[];fs=[]
            for i in range(rows):
                t=i/(rows-1);z=.468+(np.interp(t,np.linspace(0,1,len(zs)),zs)-.468)*scale
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
        p=[(-.010,surface(0,.495)-.031,.495),(-.015,surface(0,.482)-.033,.482),(-.016,surface(0,.469)-.035,.469)]
        ob=self.tube('Pendant inset highlight',p,[0,.0028,0],[0,.0018,0],(1,0,0),self.gloss);bind(ob,self.arm,'chest')
        # A closed dark metal eyelet physically connects both necklace halves.
        y=surface(0,.53)-.008
        path=[(.006*math.sin(math.tau*i/8),y,.529+.0065*math.cos(math.tau*i/8)) for i in range(9)]
        ob=self.tube('Pendant bail',path,[.0021]*5,[.0021]*5,(0,1,0),self.rim);bind(ob,self.arm,'chest')


def revise(arm,collection):
    body,face=(bpy.data.objects[k] for k in ('Body','Face'))
    prefixes=('Hair','Fox ear','Necklace','Teardrop','Pendant','White belly fur')
    for ob in list(collection.objects):
        if ob.type=='MESH' and ob.name.startswith(prefixes):
            bpy.data.objects.remove(ob,do_unlink=True)
    h=Hakko(arm,collection,body,face)
    h.body_and_face(body,face)
    h.cranium();h.ears();h.hairstyle();h.pendant(body,face)
    return {ob.name:json.loads(ob['spring_path']) for ob in h.items if 'spring_path' in ob}
