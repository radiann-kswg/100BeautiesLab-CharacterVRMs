"""Rebuild Fivens' head, single white bib and printed armband on the editable rig."""
from math import atan2, cos, pi, sin
import json
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parents[1]
sys.path.insert(0,str(NATIVE/"Corefolder-6/Modeling"))
from model_6 import bind, mesh_object, mesh_uv, rings_mesh, sampled_ring, strand, texture, toon, volume


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
    obj=bpy.data.objects["Body"]
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    if len(bm.verts)>2000:
        bmesh.ops.unsubdivide(bm,verts=list(bm.verts),iterations=2)
    bm.to_mesh(obj.data)
    bm.free()
    for v in obj.data.vertices:
        t=v.co.z/.713
        v.co.x*=1.066+.142*np.exp(-((t-.32)/.36)**2)
        v.co.z*=1.10
    obj.data.update()
    obj.data.materials.clear()
    obj.data.materials.append(grade(texture("Fivens • warm yellow and white fur",HERE/"Fivens-Fur.png",.002)))
    for uv in list(obj.data.uv_layers):obj.data.uv_layers.remove(uv)
    def coordinates(i):
        x,y,z=obj.data.vertices[i].co
        return .5+atan2(x/1.15,-(y+.065))/(2*pi),z/.784
    mesh_uv(obj,coordinates,"Mui cylindrical fur")
    obj.data.uv_layers.active.name="Fivens belly"
    bpy.context.view_layer.update()
    return BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get())


def make_face(arm,coll,ink):
    obj=bpy.data.objects["Face"]
    obj.data.materials.clear()
    obj.data.materials.append(grade(texture("Fivens • expression atlas",HERE/"Fivens-Face.png",alpha=True)))
    obj.data.materials.append(toon("Fivens • mouth cavity","#55332e",0))
    for p in obj.data.polygons:
        p.material_index=1 if 144<=p.index<=151 or 397<=p.index<=404 else 0
    keys=obj.data.shape_keys.key_blocks
    original=np.array([p.co[:] for p in keys["Basis"].data])
    opened=np.array([p.co[:] for p in keys["a"].data])
    for i,(x,y,z) in enumerate(original):
        ax=abs(x)
        eyelid=(185<=i<=227 or 439<=i<=481)
        iris=482<=i<=675
        eye=np.clip((ax-.035)/.028,0,1)*np.clip((.222-ax)/.040,0,1)
        eye*=np.clip((z-.745)/.018,0,1)*np.clip((.916-z)/.03,0,1) if y<-.25 else 0
        mouth=np.clip((.081-ax)/.025,0,1)*np.clip((z-.695)/.027,0,1)*np.clip((.771-z)/.014,0,1)
        mouth*=np.clip((-.256-y)/.026,0,1)
        delta=opened[i]-original[i]
        for key in keys:
            co=key.data[i].co
            co.z+=.019+(co.z-.780)*eye*.19
            if eye:co.x+=np.sign(x)*(ax-.106)*eye*.09
            if iris:co.z+=.009*np.clip((.799-co.z)/.019,0,1)
            if eyelid:
                co.z+=.0015-.006*np.clip((ax-.098)/.067,0,1)
                co.y-=.0022
            if 756<=i<=771:
                co.x-=np.sign(x)*.016
                co.z-=.019+.008*np.clip((.133-ax)/.060,0,1)
                co.y-=.004
            if mouth:
                co.x*=1-.40*mouth
                co.z+=mouth*(.13*delta[2]-.004*(ax/.055)**2)
    bpy.context.view_layer.update()
    # Dark chin separation above the contiguous white bib in both official corefolder drawings.
    mesh=BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get())
    torso=BVHTree.FromObject(bpy.data.objects["Body"],bpy.context.evaluated_depsgraph_get())
    controls=[]
    for x,z,w in ((-.134,.683,.0008),(-.089,.670,.0024),(-.03,.663,.0026),
                  (.031,.663,.0026),(.091,.673,.0023),(.133,.686,.0008)):
        origin=Vector((x,-1,z))
        points=[tree.ray_cast(origin,Vector((0,1,0)),2)[0] for tree in (mesh,torso)]
        ys=[p.y for p in points if p is not None]
        if ys:controls.append((x,min(ys)-.005,z,w,.0011))
    if len(controls)>2:bind(strand("Fivens chin line",controls,ink,coll,radial_count=4,samples_per_span=2),arm)


def build_head(arm,coll,hair,ivory,inner,white):
    rings=[]
    n=46
    for i in range(10):
        row=[]
        for j in range(n):
            a=2*pi*j/n
            front=max(0,cos(a))
            bottom=.689+.274*front**2.4+.008*cos(7*a)
            th=.008+(np.arccos(np.clip((bottom-.859)/.210,-1,1))-.008)*i/9
            x=.273*sin(th)**.90*sin(a)
            y=-.073-.288*sin(th)**.92*cos(a)
            z=.859+.210*cos(th)
            row.append((x,y,z))
        rings.append(row)
    edge=rings[-1]
    for inset in (.045,.76):
        rings.append([((1-inset)*x,-.073+(1-inset)*(y+.073),z+inset*(.81-z)) for x,y,z in edge])
    cap=rings_mesh("Hair scalp",rings,hair,coll)
    bind(cap,arm)
    bpy.context.view_layer.update()
    tree=BVHTree.FromObject(cap,bpy.context.evaluated_depsgraph_get())
    face_tree=BVHTree.FromObject(bpy.data.objects["Face"],bpy.context.evaluated_depsgraph_get())
    fringe=grade(texture("Fivens • swept forelock",HERE/"Fivens-Fringe.png",alpha=True))
    vs=[]
    cols=27
    for i in range(14):
        z=.754+.294*i/13
        slat=max(.018,1-((z-.859)/.210)**2)**.5
        rx=.275*slat**.90
        for j in range(cols):
            x=(2*j/(cols-1)-1)*min(.256,.95*rx)
            y=-.074-.29*slat**.92*max(.05,1-(x/rx)**2)**.5
            hit,_,_,_=tree.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)
            if hit:y=min(y,hit.y)
            hit,_,_,_=face_tree.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)
            if hit:y=min(y,hit.y)
            vs.append((x,y-.005,z))
    quads=[(i*cols+j,i*cols+j+1,(i+1)*cols+j+1,(i+1)*cols+j) for i in range(13) for j in range(cols-1)]
    f=mesh_object("Hair central swept fringe",vs,quads,[fringe],coll)
    mesh_uv(f,lambda i:((vs[i][0]+.31)/.62,(vs[i][2]-.75)/.33))
    bind(f,arm)
    cheek_ink=toon("Fivens • outer cheek stroke","#4c443c",0)
    for s,side in ((-1,"R"),(1,"L")):
        # The pale inset is on the outward plane of the very tall fox ear.
        outline=[(.103,-.073,1.002),(.141,-.066,1.076),(.211,-.026,1.176),
                 (.287,.038,1.283),(.293,.053,1.299),(.303,.060,1.233),
                 (.313,.053,1.125),(.311,.026,1.020),(.292,-.028,.932),(.267,-.073,.881),
                 (.223,-.087,.949),(.166,-.083,.982)]
        def ear_point(x,y,z):
            t=np.clip((z-.968)/.331,0,1)
            spread=.021*np.clip((x-.21)/.08,-1,1)*(1-t)
            return (s*(x-.052*t+spread),y,z-.079*t)
        edge=sampled_ring([ear_point(*v) for v in outline],2,tension=.54)
        c=Vector(ear_point(.262,.004,1.064))
        layers=[]
        for scale,displace in ((.04,.092),(.74,.068),(1,.010),(.97,-.001),(.035,-.005)):
            layers.append([c+(p-c)*scale+Vector((0,displace,0)) for p in edge])
        ear=rings_mesh("Fox ear "+side,layers,hair,coll)
        bind(ear,arm,"head_Ear"+side+"_001")
        # Near-white wedge goes along the outside edge, leaving the main triangular plane yellow.
        patch=[(.285,.024,1.271),(.292,.023,1.219),(.303,.015,1.124),(.302,-.014,1.041),
               (.286,-.050,.967),(.270,-.071,.921),(.262,-.077,.944),(.246,-.079,.980),
               (.229,-.073,1.001),(.245,-.049,1.040),(.260,-.024,1.109),(.275,.001,1.190)]
        shell=volume("Fox ear ivory rim "+side,[ear_point(x,y-.014,z) for x,y,z in patch],
                     ear_point(.274,-.045,1.068),.012,ivory,coll,samples=1,levels=5)
        bind(shell,arm,"head_Ear"+side+"_001")
        inset=[(.249,-.073,1.015),(.241,-.077,1.032),(.249,-.062,1.077),(.266,-.054,1.089),
               (.286,-.047,1.071),(.294,-.050,1.067),(.284,-.065,1.033),(.267,-.074,1.008)]
        inside=volume("Fox ear inner fur "+side,[ear_point(x,y-.016,z) for x,y,z in inset],
                     ear_point(.267,-.080,1.047),.005,inner,coll,samples=1,levels=5)
        bind(inside,arm,"head_Ear"+side+"_001")
        cheek=[(.121,-.295,.761),(.175,-.273,.782),(.205,-.249,.788),(.235,-.225,.783),
               (.265,-.203,.793),(.260,-.211,.769),(.245,-.227,.747),(.232,-.242,.737),
               (.259,-.229,.741),(.246,-.245,.721),(.215,-.260,.701),(.184,-.277,.696),(.146,-.29,.720)]
        tuft=volume("Fivens cheek fluff "+side,[(s*x,y-.009,z) for x,y,z in cheek],
                    (s*.204,-.260,.746),.018,white,coll,samples=2,levels=6)
        bind(tuft,arm)
        contour=[(.263,-.219,.791,.0008),(.258,-.229,.774,.0020),(.246,-.240,.753,.0018),
                 (.237,-.252,.742,.0013),(.257,-.243,.742,.0012),(.247,-.254,.727,.0018),
                 (.229,-.266,.712,.0018),(.211,-.273,.703,.0007)]
        stroke=strand("Fivens outer cheek "+side,[(s*x,y-.004,z,w,.0012) for x,y,z,w in contour],cheek_ink,coll,radial_count=4,samples_per_span=1)
        bind(stroke,arm)
        lock=[(.180,-.195,.963),(.220,-.217,.893),(.242,-.213,.810),(.244,-.180,.746),
              (.268,-.151,.698),(.300,-.133,.673),(.267,-.134,.673),(.233,-.151,.690),
              (.206,-.191,.723),(.196,-.219,.792),(.158,-.244,.882)]
        sidehair=volume("Hair cheek "+side,[(s*x,y,z) for x,y,z in lock],
                       (s*.222,-.206,.806),.035,hair,coll,samples=2,levels=7)
        sidehair["spring_path"]=json.dumps([[s*.188,-.199,.931],[s*.225,-.210,.855],[s*.240,-.18,.756],[s*.293,-.139,.677]])
        bind(sidehair,arm)
    pony=[(-.183,.058,1.025),(-.236,.097,1.069),(-.303,.114,1.091),(-.370,.133,1.083),
          (-.424,.137,1.054),(-.460,.124,1.012),(-.483,.106,.951),(-.490,.073,.884),
          (-.478,.035,.825),(-.463,-.001,.765),(-.468,-.052,.692),(-.488,-.091,.625),
          (-.501,-.12,.581),(-.464,-.111,.608),(-.427,-.071,.654),(-.397,-.038,.705),
          (-.378,-.009,.778),(-.367,.011,.838),(-.345,.031,.897),(-.309,.052,.937),(-.250,.055,.957)]
    def pony_point(p):
        x,y,z=p
        t=float(np.clip((-.183-x)/.31,0,1))
        return (x-.047*t,y+.152*t,z)
    ponytail=volume("Hair ponytail",[pony_point(p) for p in pony],pony_point((-.384,.065,.875)),
                    .113,hair,coll,samples=2,levels=8)
    guide=[(-.196,.064,1.024),(-.311,.105,1.020),(-.422,.083,.914),(-.441,.01,.77),(-.496,-.113,.591)]
    ponytail["spring_path"]=json.dumps([pony_point(v) for v in guide])
    bind(ponytail,arm)
    forkpath=[(-.435,.098,1.003,.027,.017),(-.474,.088,.964,.028,.018),
              (-.496,.075,.932,.019,.013),(-.525,.068,.918,.002,.001)]
    fork=strand("Hair ponytail fork",[(*pony_point(q[:3]),q[3],q[4]) for q in forkpath],hair,coll)
    bind(fork,arm)


def make_band(arm,coll,torso,ink,gold):
    def point(u,v,offset=.006):
        a=-1.36+.69*u
        z=.532+.153*v-.137*(u-.5)
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


def revise(arm,collection):
    for obj in list(collection.objects):
        if obj.type=="MESH" and (obj.name.startswith(("Hair ","Fox ear ","57 armband","57 right shoulder")) or obj.name=="White belly fur"):
            bpy.data.objects.remove(obj,do_unlink=True)
    hair=grade(toon("Fivens • golden fox hair","#FFEE62",.0024))
    cream=grade(toon("Fivens • ivory ear rim","#FFFDF2",.0012))
    inner=grade(toon("Fivens • soft yellow ear inset","#F7FFB9",.0010))
    white=grade(toon("Fivens • white cheek","#FFFFFF",0))
    ink=toon("Fivens • dark warm outlines","#36312F",0)
    torso=make_body(arm,collection)
    make_face(arm,collection,ink)
    build_head(arm,collection,hair,cream,inner,white)
    make_band(arm,collection,torso,ink,hair)
    arm.data.vrm_addon_extension.vrm0.meta.title="NumberTales #57 — 57(イズナ) / 57(Fivens)"
