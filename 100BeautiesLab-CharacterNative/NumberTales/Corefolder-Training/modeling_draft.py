"""Reference-led 57/85 modeling drafts. Separate outputs preserve the neutral foundations.
Coordinates and tail fan placement are provisional modeling choices, not new canon.
"""
from pathlib import Path
import sys,json,math,hashlib
import bpy
import numpy as np
from mathutils import Vector
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from foundation import material,sha


def color(name,hx):
    rgb=np.array([int(hx[i:i+2],16)/255 for i in (1,3,5)])
    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    mat=material(name,linear)
    shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    shader.inputs['Roughness'].default_value=.78
    return mat


def mesh_object(name,verts,faces,mats,collection):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj)
    for mat in mats:mesh.materials.append(mat)
    for poly in mesh.polygons:poly.use_smooth=True
    return obj


def bind(obj,arm,bone='head'):
    obj.parent=arm
    group=obj.vertex_groups.new(name=bone);group.add(list(range(len(obj.data.vertices))),1,'REPLACE')
    mod=obj.modifiers.new('Armature','ARMATURE');mod.object=arm


def bezier(points,t):
    a,b,c,d=map(Vector,points)
    return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d


def lock(name,path,width,depth,mats,collection,tip_start=.72):
    rings,sides=25,16;verts=[];faces=[]
    for i in range(rings):
        t=i/(rings-1);p=bezier(path,t)
        tangent=(bezier(path,min(1,t+.002))-bezier(path,max(0,t-.002))).normalized()
        side=tangent.cross(Vector((0,1,0)))
        if side.length<.01:side=tangent.cross(Vector((1,0,0)))
        side.normalize();normal=tangent.cross(side).normalized()
        radius=max(.001,(1-t)**.65 if name.startswith('Hair') else math.sin(math.pi*t)**.7)
        for j in range(sides):
            angle=2*math.pi*j/sides
            verts.append(tuple(p+radius*(width*math.cos(angle)*side+depth*math.sin(angle)*normal)))
    for i in range(rings-1):
        for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    faces.extend([tuple(reversed(range(sides))),tuple((rings-1)*sides+j for j in range(sides))])
    obj=mesh_object(name,verts,faces,mats,collection)
    if len(mats)>1:
        for p in obj.data.polygons:
            if sum(v//sides for v in p.vertices)/len(p.vertices)/(rings-1)>tip_start:p.material_index=1
    return obj


def hair_cap(mat,collection):
    verts=[];faces=[];rings=16;sides=48
    for i in range(rings):
        for j in range(sides):
            phi=2*math.pi*j/sides
            front=max(0,-math.sin(phi));end=2.6-1.5*front**3
            theta=.015+(end-.015)*i/(rings-1)
            verts.append((.283*math.sin(theta)*math.cos(phi),-.07+.278*math.sin(theta)*math.sin(phi),.865+.235*math.cos(theta)))
    for i in range(rings-1):
        for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    return mesh_object('Hair scalp',verts,faces,[mat],collection)


def face_colors(face,mats):
    # Assign the existing eyelid/iris/sclera mesh islands, keeping every expression vertex.
    adjacency=[set() for _ in face.data.vertices]
    for e in face.data.edges:
        a,b=e.vertices;adjacency[a].add(b);adjacency[b].add(a)
    unseen=set(range(len(adjacency)));components=[]
    while unseen:
        todo=[min(unseen)];unseen.remove(todo[0]);found=set(todo)
        while todo:
            for v in adjacency[todo.pop()]-found:found.add(v);unseen.discard(v);todo.append(v)
        components.append(found)
    assert [len(c) for c in components[:7]]==[396,43,43,48,48,49,49]
    face.data.materials.clear()
    for mat in mats:face.data.materials.append(mat)
    for i,component in enumerate(components):
        for poly in face.data.polygons:
            if poly.vertices[0] not in component:continue
            poly.material_index=1 if i in (1,2,8,9,10,11) else 3 if i in (7,14) else 0
            if i in (3,4):
                x,y,z=poly.center; x=abs(x)
                pupil=((x-.100)/.017)**2+((z-.805)/.036)**2<1
                highlight=(x<.095 and z>.832)
                poly.material_index=0 if highlight else 1 if pupil else 2


def belly_patch(body,arm,white,collection):
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    tree=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
    verts=[];faces=[];rows=49;cols=33
    for i in range(rows):
        z=.006+.697*i/(rows-1)
        width=.267*math.sin(math.pi*z/.716)**.55
        for j in range(cols):
            x=width*(2*j/(cols-1)-1)
            point,normal,index,distance=tree.ray_cast(Vector((x,-2,z)),Vector((0,1,0)))
            if point is None:raise ValueError('Belly patch missed body')
            verts.append(tuple(point+normal*.0015))
    for i in range(rows-1):
        for j in range(cols-1):faces.append((i*cols+j,i*cols+j+1,(i+1)*cols+j+1,(i+1)*cols+j))
    patch=mesh_object('White belly fur',verts,faces,[white],collection)
    for group in body.vertex_groups:patch.vertex_groups.new(name=group.name)
    bpy.ops.object.select_all(action='DESELECT');patch.select_set(True);bpy.context.view_layer.objects.active=patch
    transfer=patch.modifiers.new('Follow body weights','DATA_TRANSFER');transfer.object=body
    transfer.use_vert_data=True;transfer.data_types_verts={'VGROUP_WEIGHTS'};transfer.vert_mapping='POLYINTERP_NEAREST'
    transfer.layers_vgroup_select_src='ALL';transfer.layers_vgroup_select_dst='NAME'
    bpy.ops.object.modifier_apply(modifier=transfer.name)
    patch.parent=arm;mod=patch.modifiers.new('Armature','ARMATURE');mod.object=arm
    return patch


def build(n):
    folder=HERE.parent/f'Corefolder-{n}';source=folder/f'Corefolder-{n}-ModelingFoundation.blend'
    source_hash=sha(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.preferences.filepaths.save_version=0
    scene=bpy.context.scene;scene.name=f'Corefolder-{n} Modeling Draft'
    for lamp in scene.objects:
        if lamp.type=='LIGHT':lamp.data.energy=200
    arm=bpy.data.objects['Armature'];body=bpy.data.objects['Body'];face=bpy.data.objects['Face']
    collection=body.users_collection[0];collection.name='01 Character draft - export selection'
    fur=color(f'{n} Fur','#FFEE62' if n==57 else '#C48455')
    hair=color(f'{n} Hair','#FFFF6B' if n==57 else '#C48455')
    tip=color(f'{n} Tail tips','#F7FFB9' if n==57 else '#EF9D46')
    white=color('White fur','#FFFFFF');dark=color('Eye and mouth outlines','#242329')
    iris=color(f'{n} Iris draft','#BBA51C' if n==57 else '#00BACB')
    pink=color('Mouth interior','#D79085')
    body.data.materials.clear();body.data.materials.append(fur);body.data.materials.append(white)
    for poly in body.data.polygons:poly.material_index=0
    belly_patch(body,arm,white,collection)
    face_colors(face,[white,dark,iris,pink])
    cap=hair_cap(hair,collection);bind(cap,arm)
    # A central fringe and longer side locks follow the source sheet's silhouette.
    paths=[([(-.10,-.23,1.065),(-.08,-.34,1.02),(-.04,-.375,.93),(.025,-.368,.865)],.075,.018),
           ([(.08,-.22,1.07),(.12,-.34,1.02),(.19,-.37,.91),(.21,-.32,.82)],.09,.025),
           ([(-.21,-.15,1.015),(-.29,-.26,.96),(-.30,-.31,.86),(-.23,-.32,.73)],.077,.03),
           ([(.22,-.14,1.01),(.29,-.24,.97),(.31,-.29,.84),(.24,-.31,.73)],.076,.03)]
    for i,(path,w,d) in enumerate(paths):bind(lock(f'Hair fringe {i+1}',path,w,d,[hair],collection),arm)
    pony=lock('Hair ponytail',[(0,.10,.96),(-.03,.32,1.02),(.14,.38,.88),(.08,.26,.73)],.08,.06,[hair],collection);bind(pony,arm)
    for sign,side in ((-1,'R'),(1,'L')):
        # Wedge-shaped fox ears, white inset on the front.
        outline=[(.105,-.09,.997),(.315,-.04,.985),(.29,.015,1.305)]
        verts=[(sign*x,y,z) for x,y,z in outline]+[(sign*x,y+.045,z-.015) for x,y,z in outline]
        ear_faces=[(0,1,2),(5,4,3),(0,3,4,1),(1,4,5,2),(2,5,3,0)]
        if sign<0:ear_faces=[tuple(reversed(f)) for f in ear_faces]
        ear=mesh_object(f'Fox ear {side}',verts,ear_faces,[hair],collection)
        bind(ear,arm,f'head_Ear{side}_001')
        inner=mesh_object(f'Fox ear inset {side}',[(sign*.153,-.103,1.023),(sign*.282,-.055,1.025),(sign*.278,-.005,1.247)],[(0,1,2) if sign>0 else (2,1,0)],[white],collection)
        bind(inner,arm,f'head_Ear{side}_001')
    # TailCount follows DB. Spatial arrangement is a reviewable initial fan, not a measured reconstruction.
    endpoints=([(0,.73,1.06),(-.37,.62,.98),(.37,.62,.98),(-.60,.50,.74),(.60,.50,.74),(-.63,.43,.19),(.63,.43,.19)] if n==57 else
               [(0,.73,1.10),(-.43,.62,.98),(.43,.62,.98),(-.63,.51,.69),(.63,.51,.69),(-.61,.44,.19),(.61,.44,.19),(0,.78,.025)])
    upper=5 if n==57 else 3
    tail_specs=[]
    for i,end in enumerate(endpoints):
        ex,ey,ez=end;root=(ex*.17,.12,.37)
        path=[root,(ex*.45,.40,.39+(ez-.4)*.1),(ex*.95,ey+.025,ez-.10 if ez>.5 else ez+.12),end]
        name=f'Tail_{"Upper" if i<upper else "Lower"}_{i+1:02}'
        tail=lock(name,path,.185 if abs(ex)>.1 else .19,.11,[hair,tip],collection)
        tail['official_branch']='upper' if i<upper else 'lower';tail_specs.append((tail,path,name))
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    for tail,path,name in tail_specs:
        previous=arm.data.edit_bones['hips']
        for j in range(3):
            bone=arm.data.edit_bones.new(f'{name}.{j+1:03}');bone.head=bezier(path,j/3);bone.tail=bezier(path,(j+1)/3)
            bone.parent=previous;bone.use_connect=j>0;previous=bone
    bpy.ops.object.mode_set(mode='OBJECT')
    for tail,path,name in tail_specs:
        tail.parent=arm
        groups=[tail.vertex_groups.new(name=f'{name}.{j+1:03}') for j in range(3)]
        for v in tail.data.vertices:
            t=(v.index//16)/24;pos=min(2,max(0,t*3-.5));a=int(pos);b=min(2,a+1);fraction=pos-a
            groups[a].add([v.index],1-fraction,'REPLACE')
            if b!=a:groups[b].add([v.index],fraction,'REPLACE')
        mod=tail.modifiers.new('Armature','ARMATURE');mod.object=arm
    if n==85:
        gem=color('85 Pendant cyan','#00BACB')
        pendant=lock('Teardrop pendant',[(0,-.468,.48),(0,-.484,.49),(0,-.457,.55),(0,-.441,.59)],.041,.016,[gem],collection)
        bind(pendant,arm,'chest')
        # Thin necklace segments meet at the pendant attachment point.
        for sign in (-1,1):
            necklace=lock(f'Necklace {sign}',[(sign*.12,-.29,.69),(sign*.10,-.39,.64),(sign*.04,-.445,.60),(0,-.446,.59)],.003,.003,[dark],collection)
            bind(necklace,arm,'chest')
    else:
        trim=color('57 Armband trim','#A6BC40')
        # Character right is negative X in this rig (front view left).
        plaque=mesh_object('57 right shoulder armband',[(-.42,-.22,.57),(-.255,-.315,.57),(-.255,-.30,.685),(-.42,-.21,.685)],[(0,1,2,3)],[white],collection)
        bind(plaque,arm,'chest')
        curve=bpy.data.curves.new('57 number','FONT');curve.body='57';curve.size=.095;curve.align_x='CENTER';curve.extrude=.0006
        obj=bpy.data.objects.new('57 armband number',curve);collection.objects.link(obj);obj.location=(-.343,-.284,.588);obj.rotation_euler=(math.pi/2,0,-.46)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.object.convert(target='MESH');obj=bpy.context.object;obj.data.materials.append(trim);bind(obj,arm,'chest')
    # Export only character meshes/armature. Foundation reference boards and points remain in the .blend.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in collection.objects:obj.select_set(obj.type in ('MESH','ARMATURE'))
    arm.select_set(True);bpy.context.view_layer.objects.active=arm
    arm.data.vrm_addon_extension.vrm0.meta.title=f'Corefolder-{n} Modeling Draft - review required'
    arm.data.vrm_addon_extension.vrm0.meta.version='draft-v1'
    target=ROOT/f'Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{n}/ModelingDraft/Corefolder-{n}-Draft.vrm';target.parent.mkdir(exist_ok=True)
    outcome=bpy.ops.export_scene.vrm(filepath=str(target),use_addon_preferences=False,export_only_selections=True,export_invisibles=False,armature_object_name=arm.name,ignore_warning=True)
    if outcome!={'FINISHED'}:raise RuntimeError(outcome)
    for obj in bpy.data.objects:
        if obj.type=='FONT':
            if 'MODELING FOUNDATION' in obj.data.body:obj.data.body=f'{n} | MODELING DRAFT - review required'
            elif obj.data.body=='Common body / rig':obj.data.body='Character modeling draft'
            elif obj.data.body.startswith('Official tail count:'):obj.data.body=f'{len(endpoints)} tails / 3 bones each / physics pending'
    notes={'id':n,'status':'reference-led modeling draft; not final','foundation_sha256':source_hash,'vrm_sha256':sha(target),
           'tail_count':len(endpoints),'upper_count':upper,'lower_count':len(endpoints)-upper,'tail_bones_per_tail':3,
           'mesh_objects':[o.name for o in collection.objects if o.type=='MESH'],
           'provisional':['tail fan placement and intersections','hair silhouette and ear thickness','57 eye hue sampled approximately' if n==57 else 'pendant fitting','inherited facial shape and expression fitting','spring bones/colliders not configured'],
           'ai_use':'previous all6-v2 point cloud retained as reference; these meshes are built from the official sheets, not output directly by the generative model'}
    text=json.dumps(notes,indent=2,ensure_ascii=False);(folder/'Training/modeling-draft.json').write_text(text,encoding='utf-8');bpy.data.texts.new(f'README-{n}-draft.json').write(text)
    scene['foundation_status']=notes['status']
    scene.render.filepath=str(folder/'Training/Modeling-Draft-Overview.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/f'Corefolder-{n}-ModelingDraft.blend'))
    bpy.ops.render.render(write_still=True)
    # Orthographic model-only views expose front/side/back silhouette and tail placement.
    for coll in scene.collection.children:
        if coll!=collection:coll.hide_render=True
    camera=scene.camera;camera.data.ortho_scale=1.7
    # Keep the camera and light visible even if they belonged to an old collection.
    for obj in (camera,):
        if not any(c==collection for c in obj.users_collection):collection.objects.link(obj)
    for obj in scene.objects:
        if obj.type=='LIGHT' and collection not in obj.users_collection:collection.objects.link(obj)
    for name,pos in [('front',(0,-4,.68)),('side',(4,0,.68)),('back',(0,4,.68))]:
        for lamp in scene.objects:
            if lamp.type=='LIGHT':
                lamp.location=(pos[0]*.7,pos[1]*.7,3)
                lamp.rotation_euler=(Vector((0,0,.6))-lamp.location).to_track_quat('-Z','Y').to_euler()
        camera.location=pos;camera.rotation_euler=(Vector((0,0,.68))-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.resolution_x=800;scene.render.resolution_y=800
        scene.render.filepath=str(folder/f'Training/Modeling-Draft-{name}.png');bpy.ops.render.render(write_still=True)
    assert sha(source)==source_hash
    print(json.dumps(notes),flush=True)


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Use a separate Blender process')
    for number in (57,85):build(number)
