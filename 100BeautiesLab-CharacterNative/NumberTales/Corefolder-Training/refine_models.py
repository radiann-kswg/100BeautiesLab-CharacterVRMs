"""Refine real 57/85 meshes using official DB contours and canonical MToon/face UVs.
Separate outputs preserve the prior drafts and all six original VRMs.
Run in background Blender; inspect the exported MToon result in Unity.
"""
from pathlib import Path
import sys,json,math
import bpy,numpy as np
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from modeling_draft import mesh_object,bind,lock,hair_cap,bezier,sha
from db_refinement import db_tails,db_details
NATIVE=HERE.parent
BASE=ROOT/'100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend'

def linear(hx):
    a=np.array([int(hx[i:i+2],16)/255 for i in (1,3,5)])
    return tuple(np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4))

def toon(name,hx,outline=.0012):
    m=bpy.data.materials.new(name);m.use_nodes=True
    x=m.vrm_addon_extension.mtoon1;x.enabled=True;x.alpha_mode='OPAQUE';x.double_sided=True
    x.pbr_metallic_roughness.base_color_factor=(*linear(hx),1)
    t=x.extensions.vrmc_materials_mtoon
    t.shade_color_factor=tuple(c*.88 for c in linear(hx));t.shading_toony_factor=1;t.shading_shift_factor=.05;t.gi_equalization_factor=.9
    t.outline_width_mode='worldCoordinates' if outline else 'none';t.outline_width_factor=outline;t.outline_color_factor=linear('#353039');t.outline_lighting_mix_factor=0
    return m

def restore_face(face,n):
    # Fresh MToon node trees avoid stale groups from old Blender material libraries.
    tex=bpy.data.images.load(str(NATIVE/'Corefolder-4/CoreFolder-4.png'),check_existing=False);tex.pack()
    main=toon(f'{n} Face - canonical UV and alpha','#FFFFFF',0)
    iris=toon(f'{n} Iris - canonical texture','#FFFFFF',0)
    for mat in (main,iris):
        x=mat.vrm_addon_extension.mtoon1;x.alpha_mode='MASK';x.alpha_cutoff=.5
        x.pbr_metallic_roughness.base_color_texture.index.source=tex
        x.extensions.vrmc_materials_mtoon.shade_multiply_texture.index.source=tex
        x.extensions.vrmc_materials_mtoon.shading_shift_factor=1
    if n==57:
        eye=bpy.data.images.load(str(NATIVE/'Corefolder-20/CoreFolder-20.png'),check_existing=False);eye.pack()
        iris.vrm_addon_extension.mtoon1.pbr_metallic_roughness.base_color_texture.index.source=eye
        iris.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon.shade_multiply_texture.index.source=eye
    else:
        iris.vrm_addon_extension.mtoon1.pbr_metallic_roughness.base_color_factor=(.5,1,1,1)
    face.data.materials.clear();face.data.materials.append(main);face.data.materials.append(iris)
    face.data.materials.append(toon(f'{n} Neutral face backing MToon','#FFFFFF',0))
    w,h=tex.size;pixels=np.array(tex.pixels[:]).reshape(h,w,4)
    neutralized=0
    for p in face.data.polygons:
        p.material_index=1 if all(578<=v<=675 for v in p.vertices) else 0;p.use_smooth=True
        uv=np.mean([face.data.uv_layers.active.data[l].uv[:] for l in p.loop_indices],0)
        x,y=np.clip((uv*np.array([w,h])).astype(int),[0,0],[w-1,h-1]);rgb=pixels[y,x,:3]
        # Replace Mochi-specific cyan backing faces with neutral skin; retain UVs, blush, alpha eye overlays and all shape keys.
        if p.material_index==0 and rgb[1]>rgb[0]+.035 and rgb[2]>rgb[0]+.035:
            p.material_index=2;neutralized+=1
    face['neutralized_source_color_faces']=neutralized
    return [main,iris]

def normalize(obj,arm):
    for g in list(obj.vertex_groups):
        if g.name not in arm.data.bones:obj.vertex_groups.remove(g)
    for v in obj.data.vertices:
        weights=[(g.group,g.weight) for g in v.groups if g.weight>1e-8];total=sum(w for _,w in weights)
        if total<=0:raise ValueError(f'Unweighted {obj.name}:{v.index}')
        for i,w in weights:obj.vertex_groups[i].add([v.index],w/total,'REPLACE')

def build(n):
    folder=NATIVE/f'Corefolder-{n}';source=folder/f'Corefolder-{n}-ModelingDraft.blend'
    before=sha(source);bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.preferences.filepaths.save_version=0
    scene=bpy.context.scene;scene.name=f'Corefolder-{n} Refined MToon'
    arm=bpy.data.objects['Armature'];body=bpy.data.objects['Body'];face=bpy.data.objects['Face'];collection=body.users_collection[0]
    collection.name=f'Corefolder-{n} refined character'
    for obj in list(collection.objects):
        if obj.type=='MESH' and (obj.name.startswith('Hair ') or obj.name.startswith('Fox ear') or obj.name.startswith('Tail_')):bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT')
    for bone in list(arm.data.edit_bones):
        if bone.name.startswith('Tail_'):arm.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode='OBJECT')
    fur=toon(f'{n} Fur MToon','#FFEE62' if n==57 else '#C48455')
    hair=toon(f'{n} Hair MToon','#FFFF6B' if n==57 else '#C48455',0)
    tip=toon(f'{n} Tail tip MToon','#F7FFB9' if n==57 else '#EF9D46')
    white=toon(f'{n} White fur MToon','#FFFFFF',0);dark=toon(f'{n} Cord MToon','#34313A',0)
    body.data.materials.clear();body.data.materials.append(fur)
    for p in body.data.polygons:p.material_index=0
    belly=bpy.data.objects['White belly fur'];belly.data.materials.clear();belly.data.materials.append(white)
    for obj in (body,belly):
        for v in obj.data.vertices:v.co.x*=1+.12*math.sin(math.pi*max(0,min(1,v.co.z/.716)))
    restore_face(face,n)
    cap=hair_cap(hair,collection);bind(cap,arm)
    paths=[([(-.09,-.18,1.05),(-.12,-.34,1.00),(-.13,-.363,.92),(-.075,-.36,.863)],.065,.007),
           ([(.04,-.18,1.055),(.07,-.33,1.005),(.085,-.36,.93),(.145,-.345,.858)],.065,.007),
           ([(-.185,-.19,1.01),(-.25,-.28,.955),(-.28,-.31,.825),(-.232,-.315,.744)],.049,.008),
           ([(.19,-.19,1.012),(.255,-.28,.958),(.29,-.30,.83),(.24,-.31,.755)],.05,.008)]
    paths.append(([(0,-.18,1.075),(-.015,-.32,1.025),(-.035,-.375,.976),(.018,-.366,.923)],.055,.006))
    for i,(path,w,d) in enumerate(paths):bind(lock(f'Hair fringe {i+1}',path,w,d,[hair],collection),arm)
    for sign in (-1,1):
        for i,z in enumerate((.85,.79)):
            path=[(sign*.245,-.22,z+.07),(sign*.27,-.25,z+.03),(sign*.29,-.27,z),(sign*(.325 if i==0 else .30),-.27,z+.008)]
            bind(lock(f'Hair side tuft {sign} {i}',path,.022,.005,[hair],collection),arm)
    bind(lock('Hair ponytail',[(0,.09,.99),(-.03,.27,1.03),(.135,.29,.9),(.045,.20,.775)],.063,.024,[hair],collection),arm)
    for sign,side in ((-1,'R'),(1,'L')):
        outline=[(.11,-.09,1.0),(.235,-.055,.99),(.306,-.018,1.035),(.295,-.01,1.29),(.235,-.04,1.20),(.172,-.07,1.10)]
        verts=[(sign*x,y,z) for x,y,z in outline]+[(sign*x,y+.03,z-.008) for x,y,z in outline]
        faces=[tuple(range(6)),tuple(reversed(range(6,12)))]+[(i,(i+1)%6,(i+1)%6+6,i+6) for i in range(6)]
        if sign<0:faces=[tuple(reversed(f)) for f in faces]
        ear=mesh_object(f'Fox ear {side}',verts,faces,[hair],collection);bind(ear,arm,f'head_Ear{side}_001')
        inner=[(.177,-.081,1.04),(.27,-.034,1.058),(.281,-.026,1.225),(.238,-.05,1.15),(.206,-.068,1.086)]
        inset=mesh_object(f'Fox ear inset {side}',[(sign*x,y,z) for x,y,z in inner],[tuple(range(5)) if sign>0 else tuple(reversed(range(5)))],[white],collection);bind(inset,arm,f'head_Ear{side}_001')
    specs=db_tails(n,hair,tip,collection)
    upper=5 if n==57 else 3;ends=[p[-1] for _,p,_,_ in specs]
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT')
    for tail,path,name,params in specs:
        previous=arm.data.edit_bones['hips']
        for j in range(3):
            bone=arm.data.edit_bones.new(f'{name}.{j+1:03}');bone.head=bezier(path,j/3);bone.tail=bezier(path,(j+1)/3);bone.parent=previous;bone.use_connect=j>0;previous=bone
    bpy.ops.object.mode_set(mode='OBJECT')
    for tail,path,name,params in specs:
        tail.parent=arm;groups=[tail.vertex_groups.new(name=f'{name}.{j+1:03}') for j in range(3)]
        for v,t in zip(tail.data.vertices,params):
            pos=min(2,max(0,t*3-.5));a=int(pos);b=min(2,a+1);f=pos-a;groups[a].add([v.index],1-f,'REPLACE')
            if a!=b:groups[b].add([v.index],f,'REPLACE')
        tail.modifiers.new('Armature','ARMATURE').object=arm
    db_sources=db_details(n,arm,face,hair,white,collection,toon)
    meshes=[o for o in collection.objects if o.type=='MESH']
    for obj in meshes:normalize(obj,arm)
    for coll in scene.collection.children:
        if coll!=collection:coll.hide_render=True
    for obj in scene.objects:
        if obj.type in ('LIGHT','CAMERA') and collection not in obj.users_collection:collection.objects.link(obj)
    for obj in list(collection.objects):
        if obj.type in ('MESH','ARMATURE'):obj.hide_render=False
    scene.camera.data.ortho_scale=1.62;scene.camera.location=(0,-4,.65);scene.camera.rotation_euler=(Vector((0,0,.65))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.world.color=(.6,.6,.6)
    scene.view_settings.view_transform='Standard'
    for lamp in scene.objects:
        if lamp.type=='LIGHT':lamp.data.energy=150;lamp.location=(-2,-3,4);lamp.rotation_euler=(Vector((0,0,.65))-lamp.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes+[arm]:obj.select_set(True)
    bpy.context.view_layer.objects.active=arm
    arm.data.vrm_addon_extension.vrm0.meta.title=f'Corefolder-{n} Refined MToon - review required';arm.data.vrm_addon_extension.vrm0.meta.version='refined-db-v2'
    target=ROOT/f'Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{n}/Refined/Corefolder-{n}-Refined.vrm';target.parent.mkdir(exist_ok=True)
    result=bpy.ops.export_scene.vrm(filepath=str(target),use_addon_preferences=False,export_only_selections=True,export_invisibles=False,armature_object_name=arm.name,ignore_warning=True)
    if result!={'FINISHED'}:raise RuntimeError(result)
    notes={'id':n,'draft_sha256':before,'vrm_sha256':sha(target),'common_base_sha256':sha(BASE),'db_sources':db_sources,'tail_count':len(ends),'upper_count':upper,'lower_count':len(ends)-upper,'mesh_objects':[o.name for o in meshes],'changes':['canonical #4 face UV and alpha restored','#20 amber iris texture for 57; #4 cyan iris for 85','all exported materials MToon','seven/eight rounded tail volumes traced from official DB diagrams, including forked tips','DB side ponytails, asymmetric 85 ears and swept hair crown','DB eye aperture adjustment propagated to all expression keys','57 original number artwork packed on curved armband with piping and pins; 85 pale cord and cyan pendant','body widened up to 12 percent; belly follows','all deform weights normalized'],'remaining':['secondary tail physics not configured','tail contacts and subtle silhouette need artistic review'],'ai_use':'Image LoRA and generated sheets are visual reference only; actual meshes/materials are edited explicitly.'}
    (folder/'Training/refined-model.json').write_text(json.dumps(notes,indent=2),encoding='utf-8')
    scene['refined_status']='real mesh and MToon refinement; review required'
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/f'Corefolder-{n}-Refined.blend'))
    assert sha(source)==before
    print(json.dumps(notes),flush=True)
if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Run in a separate Blender process')
    for n in (57,85):build(n)
