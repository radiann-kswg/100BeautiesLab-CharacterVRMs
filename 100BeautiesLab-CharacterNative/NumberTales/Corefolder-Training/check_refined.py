"""Validate refined VRMs, canonical source preservation, closed tail meshes and deformation."""
from pathlib import Path
import json,hashlib,struct
import bpy,bmesh,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def positions(obj):
 bpy.context.view_layer.update()
 evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
 return np.array([v.co[:] for v in evaluated.data.vertices])
if not bpy.app.background:raise RuntimeError('Use a separate Blender process')
canonical=json.loads((HERE/'style-training/source-vrms.json').read_text(encoding='utf-8-sig'))
for source in canonical:assert sha(ROOT/source['source'])==source['sha256']
results=[]
for n,count in ((57,7),(85,8)):
 folder=HERE.parent/f'Corefolder-{n}'
 info=json.loads((folder/'Training/refined-model.json').read_text(encoding='utf-8'))
 assert sha(folder/f'Corefolder-{n}-ModelingDraft.blend')==info['draft_sha256']
 assert sha(ROOT/'100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend')==info['common_base_sha256']
 for record in info['db_sources']:assert sha(Path(record['path']))==record['sha256']
 vrm=ROOT/f'Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{n}/Refined/Corefolder-{n}-Refined.vrm'
 assert sha(vrm)==info['vrm_sha256']
 raw=vrm.read_bytes();length=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+length]);ext=gltf['extensions']['VRM']
 assert len(ext['humanoid']['humanBones'])==53
 assert all(m['shader']=='VRM/MToon' for m in ext['materialProperties'])
 face_mats=[m for m in ext['materialProperties'] if 'canonical' in m['name']]
 assert len(face_mats)==2 and all('_MainTex' in m['textureProperties'] for m in face_mats)
 assert 'review required' in ext['meta']['title']
 assert len([x for x in gltf['nodes'] if x.get('name','').startswith('Tail_') and '.' in x['name']])==count*3
 assert sum(len(m.get('extras',{}).get('targetNames',[])) for m in gltf['meshes'])==15
 bpy.ops.wm.open_mainfile(filepath=str(folder/f'Corefolder-{n}-Refined.blend'))
 arm=bpy.data.objects['Armature'];face=bpy.data.objects['Face']
 assert len(arm.data.bones)==58+count*3
 tails=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('Tail_')]
 assert len(tails)==count
 for tail in tails:
  bm=bmesh.new();bm.from_mesh(tail.data)
  assert all(e.is_manifold for e in bm.edges),tail.name
  bm.free()
 expected_upper=5 if n==57 else 3
 assert sum(o['official_branch']=='upper' for o in tails)==expected_upper
 meshes=[o for o in bpy.context.scene.objects if o.name in info['mesh_objects']]
 assert len(meshes)==len(info['mesh_objects'])
 for obj in meshes:
  assert obj.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers)
  assert all(np.isfinite(v.co[:]).all() for v in obj.data.vertices)
  for v in obj.data.vertices:
   weights=[g for g in v.groups if g.weight>1e-7]
   assert weights and abs(sum(g.weight for g in weights)-1)<1e-4,(obj.name,v.index)
   assert all(obj.vertex_groups[g.group].name in arm.data.bones for g in weights)
 pose_checks=[]
 for tail in tails:
  before=positions(tail);bone=arm.pose.bones[tail.name+'.002'];oldmode=bone.rotation_mode;oldeuler=bone.rotation_euler.copy();oldquat=bone.rotation_quaternion.copy()
  bone.rotation_mode='XYZ';bone.rotation_euler.x=.12
  delta=float(np.linalg.norm(positions(tail)-before,axis=1).max())
  bone.rotation_euler=oldeuler;bone.rotation_quaternion=oldquat;bone.rotation_mode=oldmode
  assert delta>.001
  pose_checks.append({'tail':tail.name,'max_delta':delta})
 expression_checks=[]
 for key in ('a','EyeClose','Joy'):
  before=positions(face);shape=face.data.shape_keys.key_blocks[key];shape.value=1
  delta=float(np.linalg.norm(positions(face)-before,axis=1).max());shape.value=0
  assert delta>.001
  expression_checks.append({'key':key,'max_delta':delta})
 assert bpy.data.objects['White belly fur'].data.materials[0].name.endswith('White fur MToon')
 if n==57:assert bpy.data.objects.get('57 armband number') and bpy.data.objects.get('57 right shoulder armband')
 else:assert bpy.data.objects.get('Teardrop pendant')
 results.append({'id':n,'tail_count':count,'rig_bones':len(arm.data.bones),'humanoid_bones':53,'mesh_objects':len(meshes),'weights_normalized':True,'tail_pose_checks':pose_checks,'expression_checks':expression_checks,'draft_and_common_base_unchanged':True,'db_sources_unchanged':True,'all_materials_mtoon':True,'tail_meshes_closed':True,'vrm_sha256':sha(vrm)})
(HERE/'targets/refined-model-checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results),flush=True)
