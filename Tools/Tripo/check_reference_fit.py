"""Validate saved hybrid drafts: preserved sources, mesh closure, rig weights and deformation."""
from pathlib import Path
import hashlib,json
import bpy,bmesh,numpy as np
ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/'100BeautiesLab-CharacterNative/NumberTales'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def positions(o):
    bpy.context.view_layer.update()
    e=o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return np.array([v.co[:] for v in e.data.vertices])
def changed(o,arm,bone):
    before=positions(o);b=arm.pose.bones[bone];mode=b.rotation_mode;q=b.rotation_quaternion.copy();r=b.rotation_euler.copy()
    b.rotation_mode='XYZ';b.rotation_euler.x+=.12
    moved=float(np.linalg.norm(positions(o)-before,axis=1).max())
    b.rotation_euler=r;b.rotation_quaternion=q;b.rotation_mode=mode
    assert moved>.001,(o.name,bone,moved)
    return moved
out=[]
for n,count in [(57,7),(85,8)]:
    folder=NATIVE/f'Corefolder-{n}';review=folder/'Training/TripoFit-structure-v4'
    record=json.loads((review/'result.json').read_text(encoding='utf-8-sig'))
    assert sha(Path(record['native_source']))==record['native_sha256']
    assert sha(Path(record['tripo_source']))==record['tripo_sha256']
    bpy.ops.wm.open_mainfile(filepath=record['blend'])
    arm=bpy.data.objects['Armature'];head=bpy.data.objects['Tripo head - static expression pending']
    coll=head.users_collection[0];meshes=[o for o in coll.objects if o.type=='MESH']
    tails=[o for o in meshes if o.name.startswith('Tail_')]
    assert len(tails)==count
    assert sum(o['official_branch']=='upper' for o in tails)==(5 if n==57 else 3)
    weight_checks=[];closure={}
    for o in meshes:
        assert any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers),o.name
        for v in o.data.vertices:
            assert np.isfinite(v.co[:]).all()
            active=[g for g in v.groups if g.weight>1e-8]
            assert active and abs(sum(g.weight for g in active)-1)<1e-4,(o.name,v.index)
            assert all(o.vertex_groups[g.group].name in arm.data.bones for g in active)
        weight_checks.append(o.name)
    for o in tails+[head]:
        bm=bmesh.new();bm.from_mesh(o.data)
        closure[o.name]={'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges)}
        bm.free()
        assert closure[o.name]['nonmanifold_edges']==0,(o.name,closure[o.name])
    moves={o.name:changed(o,arm,o.name+'.002') for o in tails}
    moves[head.name]=changed(head,arm,'head')
    moves['Body']=changed(bpy.data.objects['Body'],arm,'spine')
    assert len(arm.data.vrm_addon_extension.vrm0.blend_shape_master.blend_shape_groups)==0
    row={'id':n,'tail_count':count,'weighted_meshes':len(weight_checks),'weights_normalized':True,'deformation_max_displacement':moves,'closure':closure,
        'face_expression_bindings':0,'source_hashes_unchanged':True,'blend_sha256':sha(Path(record['blend']))}
    (review/'checks.json').write_text(json.dumps(row,indent=2),encoding='utf-8');out.append(row)
native=json.loads((ROOT/'Tools/Tripo/native-inspection-20260910.json').read_text())
for r in native:assert sha(Path(r['source']))==r['sha256']
vrms=json.loads((NATIVE/'Corefolder-Training/style-training/source-vrms.json').read_text(encoding='utf-8-sig'))
for r in vrms:assert sha(ROOT/r['source'])==r['sha256']
print(json.dumps({'results':out,'canonical_native_sources_unchanged':True,'canonical_vrms_unchanged':True}),flush=True)
