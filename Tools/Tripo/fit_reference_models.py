"""First editable Tripo/native hybrid pass. Background Blender; never overwrite sources."""
from pathlib import Path
import argparse, hashlib, json, math, sys
import bpy, bmesh, numpy as np
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/'100BeautiesLab-CharacterNative/NumberTales'
sys.path.insert(0,str(NATIVE/'Corefolder-Training'))
from refine_models import toon
from modeling_draft import bind

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def close_small_boundary_loops(mesh):
    bm=bmesh.new();bm.from_mesh(mesh)
    remaining={e for e in bm.edges if e.is_boundary}
    while remaining:
        edge=remaining.pop();start,current=edge.verts;loop=[start,current]
        while current!=start:
            candidates=[e for e in current.link_edges if e in remaining]
            if len(candidates)!=1:break
            edge=candidates[0];remaining.remove(edge);current=edge.other_vert(current)
            if current!=start:loop.append(current)
        if current==start and 3<=len(loop)<=64:
            existing=bm.faces.get(loop)
            if existing is not None:
                if all(len(v.link_faces)==1 for v in loop):
                    bmesh.ops.delete(bm,geom=loop,context='VERTS')
            else:
                face=bm.faces.new(loop)
                bmesh.ops.triangulate(bm,faces=[face])
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()

def render(scene, collection, out):
    meshes=[o for o in collection.objects if o.type=='MESH' and not o.hide_render]
    pts=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
    lo=Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    center=(lo+hi)/2;size=max(hi-lo)
    scene.render.engine='BLENDER_WORKBENCH'
    s=scene.display.shading;s.light='STUDIO';s.color_type='SINGLE';s.single_color=(.65,.65,.65);s.show_cavity=False
    s.show_shadows=True;s.background_type='WORLD';scene.world.color=(.17,.17,.17)
    scene.view_settings.view_transform='Standard'
    scene.render.resolution_x=scene.render.resolution_y=720
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=size*1.18
    for name,direction in [('front',(0,-1,0)),('side',(1,0,0)),('back',(0,1,0))]:
        direction=Vector(direction);scene.camera.location=center+direction*size*3
        scene.camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)

def build(n,version):
    folder=NATIVE/f'Corefolder-{n}'
    source=folder/f'Corefolder-{n}-Refined.blend'
    record=json.loads(next((folder/'TripoGenerated/20260910').glob('*/task.json')).read_text(encoding='utf-8'))
    raw=Path(record['files']['base_model']);source_hash=sha(source);raw_hash=sha(raw)
    out=folder/'Training'/f'TripoFit-{version}'
    out.mkdir(exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.preferences.filepaths.save_version=0
    scene=bpy.context.scene;arm=bpy.data.objects['Armature'];body=bpy.data.objects['Body']
    coll=body.users_collection[0];coll.name=f'{n} Tripo fit - provisional head'
    # Existing native body is sourced from the common base; retain official-tail rig and accessories.
    for o in list(coll.objects):
        if o.type=='MESH' and (o.name=='Face' or o.name.startswith(('Hair ','Fox ear'))):
            bpy.data.objects.remove(o,do_unlink=True)
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(raw))
    imported=[o for o in bpy.data.objects if o not in before]
    head=next(o for o in imported if o.type=='MESH')
    bpy.context.view_layer.update()
    world=head.matrix_world.copy();head.parent=None;head.matrix_world=Matrix.Identity(4)
    head.data.transform(world)
    print('RAW_BOUNDS',[[min(v.co[i] for v in head.data.vertices) for i in range(3)],
        [max(v.co[i] for v in head.data.vertices) for i in range(3)]],flush=True)
    bm=bmesh.new();bm.from_mesh(head.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.000001)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,
        plane_co=(0,0,.22 if n==57 else .25),plane_no=(.25 if n==57 else .5,0,1),clear_inner=True,clear_outer=False)
    # Keep the head component after the neck cut, discard separate tail-tip islands.
    unseen=set(bm.verts);parts=[]
    while unseen:
        seed=unseen.pop();todo=[seed];part=[]
        while todo:
            v=todo.pop();part.append(v)
            for edge in v.link_edges:
                other=edge.other_vert(v)
                if other in unseen:unseen.remove(other);todo.append(other)
        parts.append(part)
    main=max(parts,key=lambda p:len(p) if max(v.co.z for v in p)>.3 else 0)
    print('PARTS',sorted([(len(p),[sum(v.co[i] for v in p)/len(p) for i in range(3)]) for p in parts],reverse=True)[:12],flush=True)
    keep=[p for p in parts if p is main or (sum(v.co.x for v in p)/len(p)>.18 and max(v.co.z for v in p)>.12)]
    drop=[v for p in parts if p not in keep for v in p]
    bmesh.ops.delete(bm,geom=drop,context='VERTS')
    boundary=[e for e in bm.edges if e.is_boundary]
    if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(head.data);bm.free()
    head.name='Tripo head - static expression pending'
    # Match native Z-up / -Y-front and the native neck position, preserving the head silhouette.
    for v in head.data.vertices:
        x,y,z=v.co;v.co=(1.25*y,-1.25*x+.07,1.25*z+(.53 if n==57 else .62))
    pre=len(head.data.polygons)
    bpy.context.view_layer.objects.active=head;head.select_set(True)
    remesh=head.modifiers.new('Close imported seam topology','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.002
    remesh.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    head.data.calc_loop_triangles()
    dec=head.modifiers.new('Preview topology reduction','DECIMATE');dec.ratio=min(1,24000/len(head.data.loop_triangles))
    bpy.ops.object.modifier_apply(modifier=dec.name)
    bm=bmesh.new();bm.from_mesh(head.data)
    boundary=[e for e in bm.edges if e.is_boundary]
    if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(head.data);bm.free()
    close_small_boundary_loops(head.data)
    for p in head.data.polygons:p.use_smooth=True
    for c in list(head.users_collection):c.objects.unlink(head)
    coll.objects.link(head)
    bind(head,arm,'head')
    head.data.materials.clear()
    head.data.materials.append(toon(f'{n} Head clay - texture pending','#CCCCCC',.0007))
    for p in head.data.polygons:p.material_index=0
    # The deleted source face must not leave dangling VRM expression bindings.
    arm.data.vrm_addon_extension.vrm0.blend_shape_master.blend_shape_groups.clear()
    for o in imported:
        if o!=head and o.name in bpy.data.objects:bpy.data.objects.remove(o,do_unlink=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1,location=(0,0,0))
    neck=bpy.context.object;neck.name='Neck transition - provisional'
    for v in neck.data.vertices:v.co=(v.co.x*.18,v.co.y*.16-.15,v.co.z*.105+.715)
    for c in list(neck.users_collection):c.objects.unlink(neck)
    coll.objects.link(neck);bind(neck,arm,'head')
    neck.data.materials.append(toon(f'{n} Neck white MToon','#FFFFFF',0))
    for p in neck.data.polygons:p.use_smooth=True
    for mat in bpy.data.materials:
        if hasattr(mat,'vrm_addon_extension') and mat.vrm_addon_extension.mtoon1.enabled:
            mat.diffuse_color=mat.vrm_addon_extension.mtoon1.pbr_metallic_roughness.base_color_factor
    # Separate the inherited belly overlay from the body to prevent z-fighting.
    belly=bpy.data.objects['White belly fur']
    for v in belly.data.vertices:v.co.y-=.004
    for o in coll.objects:
        if o.type=='MESH' and o.name.startswith('Tail_'):
            bpy.context.view_layer.objects.active=o
            mod=o.modifiers.new('Tail surface smoothing','SUBSURF');mod.levels=1
            bpy.ops.object.modifier_move_up(modifier=mod.name)
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for c in scene.collection.children:
        if c!=coll:c.hide_render=True
    head.hide_render=False
    scene['status']='Tripo/native hybrid first fitting pass; static face; not release-ready'
    blend_dir=folder/'Tripo'
    blend_dir.mkdir(parents=True,exist_ok=True)
    blend=blend_dir/f'Corefolder-{n}-TripoFit-{version}.blend'
    if blend.exists():raise FileExistsError(blend)
    render(scene,coll,out)
    bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    info={'id':n,'blend':str(blend),'native_source':str(source),'native_sha256':source_hash,'tripo_source':str(raw),'tripo_sha256':raw_hash,
        'task_id':record['task_id'],'head_polygons_before_decimate':pre,'head_polygons':len(head.data.polygons),
        'source_components_after_cut':len(parts),'tail_count':len([o for o in coll.objects if o.type=='MESH' and o.name.startswith('Tail_')]),
        'active_polygons':sum(len(o.data.polygons) for o in coll.objects if o.type=='MESH' and not o.hide_render),
        'bones':len(arm.data.bones),'pending':['head material and UV painting','expression topology and facial texture','head/body junction under motion','tail contact review','spring bones','VRM export validation']}
    assert sha(source)==source_hash and sha(raw)==raw_hash
    (out/'result.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info),flush=True)

if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background Blender required')
    p=argparse.ArgumentParser();p.add_argument('--version',required=True);p.add_argument('--id',type=int,choices=[57,85],required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);build(args.id,args.version)
