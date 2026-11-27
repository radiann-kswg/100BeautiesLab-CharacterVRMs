"""Integration check: source hashes, exported humanoid/morphs, packed references and distinct AI guides."""
import hashlib,json,struct,sys
from pathlib import Path
import bpy
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def gltf(p):
 raw=p.read_bytes(); magic,version,total,length,kind=struct.unpack_from('<5I',raw)
 assert (magic,version,total,kind)==(0x46546c67,2,len(raw),0x4e4f534a)
 return json.loads(raw[20:20+length])
if not bpy.app.background: raise RuntimeError('Use separate Blender process')
results=[]
clouds=[]
common=ROOT/'100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend'
bpy.ops.wm.open_mainfile(filepath=str(common))
body=bpy.data.objects['body']; bpy.context.view_layer.objects.active=body
bpy.ops.object.select_all(action='DESELECT'); body.select_set(True)
for mod in list(body.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
sub=body.modifiers.new('Validation subdivision','SUBSURF'); sub.levels=2
bpy.ops.object.modifier_apply(modifier=sub.name)
common_xyz=np.array([v.co[:] for v in body.data.vertices],dtype='<f4')
for n in (57,85):
 folder=HERE.parent/f'Corefolder-{n}'
 notes=json.loads((folder/'Training/foundation.json').read_text(encoding='utf-8'))
 assert sha(ROOT/notes['source_blend'])==notes['source_sha256']
 assert sha(folder/f'Training/ThreeView-CoreFolder-{n}.png')==notes['three_view_sha256']
 assert sha(HERE/'runs/all6-v2/checkpoint.pt')==notes['checkpoint_sha256']
 point_file=folder/'Training/AI-ShapeGuide.npz'
 assert sha(point_file)==notes['sample_sha256']
 points=np.load(point_file); xyz=points['coords']; rgb=np.stack([points[c] for c in 'RGB'],axis=1)
 assert xyz.shape==(1024,3) and np.isfinite(xyz).all() and np.isfinite(rgb).all()
 assert rgb.min()>=0 and rgb.max()<=1
 clouds.append(xyz)
 vrm=ROOT/notes['vrm']; assert sha(vrm)==notes['vrm_sha256']
 data=gltf(vrm); extension=data['extensions']['VRM']
 assert len(extension['humanoid']['humanBones'])==53
 assert len(data['meshes'])==2
 assert sum(len(m.get('extras',{}).get('targetNames',[])) for m in data['meshes'])==15
 assert not extension['secondaryAnimation']['boneGroups']
 assert all(not x.get('name','').startswith('Tail') for x in data['nodes'])
 bpy.ops.wm.open_mainfile(filepath=str(folder/f'Corefolder-{n}-ModelingFoundation.blend'))
 arm=bpy.data.objects['Armature']
 assert len(arm.data.bones)==58
 body=bpy.data.objects['Body']
 xyz=np.array([v.co[:] for v in body.data.vertices],dtype='<f4')
 assert np.array_equal(xyz,common_xyz), 'Body must match the common source, with no Mochi garment geometry'
 assert sha(common)==notes['body_provenance']['common_sha256']
 assert hashlib.sha256(xyz.tobytes()).hexdigest()==notes['body_provenance']['body_coordinate_sha256']
 for vertex in body.data.vertices:
  weights=[g for g in vertex.groups if g.weight>0]
  assert weights and abs(sum(g.weight for g in weights)-1)<1e-5
  assert all(body.vertex_groups[g.group].name in arm.data.bones for g in weights)
 def deformed():
  bpy.context.view_layer.update()
  obj=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
  return np.array([v.co[:] for v in obj.data.vertices])
 before=deformed(); spine=arm.pose.bones['spine']
 old_mode=spine.rotation_mode; old_quat=spine.rotation_quaternion.copy(); old_euler=spine.rotation_euler.copy()
 spine.rotation_mode='XYZ'; spine.rotation_euler.x=.15
 delta=float(np.linalg.norm(deformed()-before,axis=1).max())
 spine.rotation_euler=old_euler; spine.rotation_quaternion=old_quat; spine.rotation_mode=old_mode
 assert delta>1e-5, 'Transferred body weights must respond to spine rotation'
 assert len(bpy.data.objects['Face'].data.shape_keys.key_blocks)==16
 assert not any(b.name.startswith('Tail') for b in arm.data.bones)
 assert all(b.node.bone_name in arm.data.bones for b in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones if b.node.bone_name)
 packed=[im for im in bpy.data.images if im.type=='IMAGE' and im.packed_file]
 assert len(packed)==5
 assert len(bpy.data.objects[f'{n} AI rough guide - not a mesh'].data.vertices)==1024
 assert str(n) in bpy.context.scene.name
 assert bpy.context.scene.render.filepath==str(folder/'Training/Foundation-Overview.png')
 results.append({'id':n,'humanoid_bones':53,'rig_bones':58,'exported_expressions':15,'packed_reference_images':len(packed),'source_unchanged':True,'common_body_exact_geometry':True,'normalized_skin_weights':True,'spine_pose_max_delta':delta})
assert not np.array_equal(*clouds)
for n in (4,16,20,22,25,93):
 provenance=json.loads((HERE/f'dataset-v1/Corefolder-{n}/provenance.json').read_text())
 # Actual source path and hash keys are recorded by prepare.py.
 source=next((ROOT/f'Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{n}').glob('*.vrm'))
 assert sha(source)==provenance['sha256']
(HERE/'targets/foundation-checks.json').write_text(json.dumps({'checks':results,'distinct_ai_guides':True,'six_source_vrms_unchanged':True},indent=2),encoding='utf-8')
print(json.dumps(results),flush=True)
