import bpy, json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/'100BeautiesLab-CharacterNative/NumberTales'
records=[]
for n in (4,16,20,22,25,93,57,85):
    path=(NATIVE/f'Corefolder-{n}'/f'Corefolder-{n}-Refined.blend') if n in (57,85) else next((NATIVE/f'Corefolder-{n}').glob('*.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    meshes=[]
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        p=[o.matrix_world@v.co for v in o.data.vertices]
        meshes.append({'name':o.name,'vertices':len(p),'polygons':len(o.data.polygons),'bounds':[[min(v[i] for v in p) for i in range(3)],[max(v[i] for v in p) for i in range(3)]], 'materials':[m.name if m else None for m in o.data.materials], 'shape_keys':list(o.data.shape_keys.key_blocks.keys()) if o.data.shape_keys else []})
    records.append({'id':n,'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'meshes':meshes,'arms':[{'name':o.name,'bones':len(o.data.bones)} for o in bpy.context.scene.objects if o.type=='ARMATURE']})
(ROOT/'Tools/Tripo/native-inspection-20260910.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print('INSPECTED NATIVE',len(records))
