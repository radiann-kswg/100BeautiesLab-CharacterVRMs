"""Close small boundary loops on the current derived output; never touch raw Tripo/native sources."""
from pathlib import Path
import sys,json
import bpy
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from fit_reference_models import NATIVE,close_small_boundary_loops,render
from mathutils import Matrix
for n in (57,85):
    out=NATIVE/f'Corefolder-{n}'/'Training/TripoFit-structure-v4'
    record=json.loads((out/'result.json').read_text(encoding='utf-8-sig'))
    path=Path(record['blend'])
    assert path.parent==NATIVE/f'Corefolder-{n}'/'Tripo'
    bpy.ops.wm.open_mainfile(filepath=str(path))
    head=bpy.data.objects['Tripo head - static expression pending']
    close_small_boundary_loops(head.data)
    neck=bpy.data.objects['Neck transition - provisional']
    neck.matrix_parent_inverse=Matrix.Identity(4);neck.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    render(bpy.context.scene,head.users_collection[0],out)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    record['head_polygons']=len(head.data.polygons)
    record['active_polygons']=sum(len(o.data.polygons) for o in head.users_collection[0].objects if o.type=='MESH' and not o.hide_render)
    (out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
