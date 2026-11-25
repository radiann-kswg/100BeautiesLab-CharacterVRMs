"""Rebuild Fivens' head, single white bib and printed armband on the editable rig."""
from math import atan2, cos, pi, sin
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parents[1]
sys.path.insert(0,str(NATIVE/"Corefolder-6/Modeling"))
from model_6 import bind, cheek_surface, fit_outfit_skin, join_hair_roots, skin_temples, swept_scalp, temple_guide, map_drawn_eyes, mesh_object, mesh_uv, restore_reference_body, rings_mesh, strand, texture, toon


def grade(mat):
    # The project's linear URP lighting overexposes the warm yellow at a unit base factor.
    surface=mat.vrm_addon_extension.mtoon1
    pbr=surface.pbr_metallic_roughness
    rgba=pbr.base_color_factor
    pbr.base_color_factor=(*(v*.77 for v in rgba[:3]),rgba[3])
    params=surface.extensions.vrmc_materials_mtoon
    params.shade_color_factor=tuple(c*.77 for c in params.shade_color_factor)
    return mat


def make_body(arm,coll):
    obj=restore_reference_body(arm,coll)
    from torso_profile import add_cranial_base
    core=add_cranial_base(arm,bpy.data.objects["Face"],57,coll)
    grade(core.data.materials[0])
    obj.data.materials.clear()
    obj.data.materials.append(grade(texture("Fivens • warm yellow and white fur",HERE/"Fivens-Fur.png",.002)))
    for uv in list(obj.data.uv_layers):obj.data.uv_layers.remove(uv)
    def coordinates(i):
        x,y,z=obj.data.vertices[i].co
        return .5+atan2(x,-(y+.07))/(2*pi),z/.713
    mesh_uv(obj,coordinates,"Mui cylindrical fur")
    obj.data.uv_layers.active.name="Fivens belly"
    bpy.context.view_layer.update()
    return BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get())


def make_face():
    obj=bpy.data.objects["Face"]
    obj.data.materials.clear()
    obj.data.materials.append(grade(texture("Fivens • expression atlas",HERE/"Fivens-Face.png",alpha=True)))
    obj.data.materials.append(toon("Fivens • mouth cavity","#55332e",0))
    for p in obj.data.polygons:
        p.material_index=1 if 144<=p.index<=151 or 397<=p.index<=404 else 0
    map_drawn_eyes(obj,grade(texture("Fivens • drawn left and right irises",HERE/"Fivens-Eyes.png",alpha=True)))
    bpy.context.view_layer.update()


def build_head(arm,coll,hair,white):
    face=bpy.data.objects["Face"]
    cap_mat=grade(texture("Fivens • swept forelocks",HERE/'Fivens-Fringe.png',.0016))
    cap=swept_scalp(57,arm,coll,cap_mat)
    bpy.context.view_layer.update()
    face_tree=BVHTree.FromObject(face,bpy.context.evaluated_depsgraph_get())
    ear_mat=grade(texture('Fivens • fur and inward ear bowl',HERE/'Fivens-Ear.png',.0018))
    for s,side in ((-1,"R"),(1,"L")):
        # The native fox ears taper from a wide seated base. The front inset,
        # outer rim and rear surface share the same rounded, closed shell.
        sections=[(.852,.171,-.026,.040,.042),(.895,.180,-.026,.073,.073),
                  (.934,.193,-.024,.098,.089),(.977,.207,-.012,.105,.094),
                  (1.032,.223,.001,.091,.079),(1.089,.237,.018,.071,.063),
                  (1.145,.250,.034,.048,.046),(1.187,.261,.048,.023,.027),
                  (1.212,.267,.058,.003,.004)]
        rings=[];n=24
        for z,cx,cy,rx,ry in sections:
            height=np.clip((z-.852)/.360,0,1)
            row=[]
            for j in range(n):
                a=2*pi*j/n
                angle=(a+pi)%(2*pi)-pi
                bowl=ry*.48*np.exp(-((angle-.70)/.55)**2)*np.sin(pi*height)**.70
                row.append((s*(cx+rx*sin(a)),cy-ry*np.sign(cos(a))*abs(cos(a))**.83+bowl,z))
            rings.append(row)
        ear=rings_mesh('Fox ear '+side,rings,ear_mat,coll)
        uv=ear.data.uv_layers.new(name='Fivens fox ear')
        for poly in ear.data.polygons:
            values=[((ear.data.loops[i].vertex_index%n)/n,(sections[ear.data.loops[i].vertex_index//n][0]-.852)/.360) for i in poly.loop_indices]
            seam=max(a for a,h in values)-min(a for a,h in values)>.5
            for i,(a,h) in zip(poly.loop_indices,values):uv.data[i].uv=(a+1 if seam and a<.5 else a,h)
        bind(ear,arm,'head_Ear'+side+'_001')
        cheek=[(.121,-.295,.761),(.175,-.273,.782),(.205,-.249,.788),(.235,-.225,.783),
               (.265,-.203,.793),(.260,-.211,.769),(.245,-.227,.747),(.232,-.242,.737),
               (.259,-.229,.741),(.246,-.245,.721),(.215,-.260,.701),(.184,-.277,.696),(.146,-.29,.720)]
        def cheek_point(x,y,z):
            z-=.015
            xx=s*(x+.022*np.clip((.18-x)/.06,0,1))
            join=np.clip((abs(xx)-.150)/.088,0,1)
            hit=face_tree.ray_cast(Vector((xx,-1,z)),Vector((0,1,0)),2)[0]
            yy=y-.002 if hit is None else (1-join)*(hit.y+.022)+join*(y-.002)
            return (xx,yy,z)
        tuft=cheek_surface("Fivens cheek fluff "+side,[cheek_point(x,y,z) for x,y,z in cheek],white,coll,.014)
        bind(tuft,arm)
        temple_guide(cap,"Hair cheek "+side,side,coll)
    pony=[(-.187,.040,.994,.026,.025),(-.255,.088,1.037,.058,.055),
          (-.331,.141,1.049,.089,.080),(-.398,.166,1.012,.104,.101),
          (-.432,.174,.944,.101,.098),(-.442,.156,.865,.082,.078),
          (-.449,.127,.781,.061,.057),(-.462,.078,.707,.043,.038),
          (-.483,.021,.644,.025,.021),(-.513,-.027,.591,.002,.002)]
    ponytail=strand('Hair ponytail',pony,hair,coll,radial_count=14,samples_per_span=2)
    ponytail['spring_path']=json.dumps([pony[i][:3] for i in (0,2,4,6,9)])
    bind(ponytail,arm)
    forkpath=[(-.398,.165,.990,.020,.020),(-.468,.171,.967,.031,.027),
              (-.491,.151,.929,.020,.017),(-.521,.119,.912,.002,.001)]
    fork=strand("Hair ponytail fork",forkpath,hair,coll)
    bind(fork,arm)


def make_band(arm,coll,torso,ink,gold):
    existing=set(coll.objects)
    def point(u,v,offset=.006):
        a=-1.36+.69*u
        z=.469+.135*v-.118*(u-.5)
        axis=Vector((0,-.065,z))
        direction=Vector((sin(a),-cos(a),0))
        p,n,_,_=torso.ray_cast(axis,direction,1)
        if p is None:raise RuntimeError("Fivens' armband missed the torso")
        return p+n*offset
    mat=grade(texture("Fivens • DB number 57 and piping",HERE/"Fivens-Armband.png",.0015))
    cols,rows=20,6
    vs=[point(j/(cols-1),i/(rows-1)) for i in range(rows) for j in range(cols)]
    faces=[(i*cols+j,i*cols+j+1,(i+1)*cols+j+1,(i+1)*cols+j) for i in range(rows-1) for j in range(cols-1)]
    armband=mesh_object("57 right shoulder armband",vs,faces,[mat],coll)
    mesh_uv(armband,lambda i:(i%cols/(cols-1),i//cols/(rows-1)))
    bind(armband,arm,"chest")
    for name,coords in (("inner",[(1,t) for t in (0,.3,.7,1)]),("outer",[(0,t) for t in (0,.3,.7,1)]),
                        ("top",[(t,1) for t in (0,.17,.34,.5,.67,.84,1)]),
                        ("hem",[(t,0) for t in (0,.17,.34,.5,.67,.84,1)])):
        band_edge=[(*point(u,v,.0075),.0015,.0012) for u,v in coords]
        bind(strand("57 armband "+name+" edge",band_edge,ink,coll,radial_count=4,samples_per_span=1),arm,"chest")
    # One U-shaped clip straddles the upper piping next to the digits in both illustrations.
    loop=[(.29,.89),(.29,1.04),(.32,1.11),(.36,1.13),(.40,1.10),(.42,1.02),(.40,.92),(.38,.90)]
    path=[(*point(u,v,.011),.0034,.0021) for u,v in loop]
    bind(strand("57 armband paperclip",path,ink,coll,radial_count=5,samples_per_span=2),arm,"chest")
    fit_outfit_skin(bpy.data.objects['Body'],set(coll.objects)-existing)


def finish_hair(arm,collection):
    cap=collection.objects["Hair scalp and swept forelocks"]
    skin_temples(cap,[(side,collection.objects["Hair cheek "+side]) for side in ("R","L")])
    parts=[collection.objects[n] for n in ("Fox ear R","Fox ear L",
                                           "Hair ponytail","Hair ponytail fork")]
    join_hair_roots(arm,cap,parts)


def revise(arm,collection):
    from canonical_face import fit_reference_face
    fit_reference_face(bpy.data.objects['Face'],arm)
    for obj in list(collection.objects):
        if obj.type=="MESH" and (obj.name.startswith(("Hair ","Fox ear ","57 armband","57 right shoulder")) or obj.name=="White belly fur"):
            bpy.data.objects.remove(obj,do_unlink=True)
    hair=grade(toon("Fivens • golden fox hair","#FFEE62",.0024))
    white=grade(toon("Fivens • white cheek","#FFFFFF",0))
    white.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon.shade_color_factor=(.74,.735,.74)
    ink=toon("Fivens • dark warm outlines","#36312F",0)
    torso=make_body(arm,collection)
    make_face()
    build_head(arm,collection,hair,white)
    make_band(arm,collection,torso,ink,hair)
    arm.data.vrm_addon_extension.vrm0.meta.title="NumberTales #57 — 57(イズナ) / 57(Fivens)"
