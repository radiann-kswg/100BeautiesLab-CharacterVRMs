import bpy,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fit_reference_models import ROOT,render
for n in (4,16,20,22,25,93):
    bpy.ops.wm.read_homefile(use_empty=True)
    source=next((ROOT/f'Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{n}').glob('*.vrm'))
    bpy.ops.wm.vrm_license_warning(filepath=str(source),import_anyway=True,extract_textures_into_folder=False,enable_mtoon_outline_preview=False)
    scene=bpy.context.scene;scene.world=bpy.data.worlds.new('ReviewWorld')
    coll=bpy.data.collections.new('Reference');scene.collection.children.link(coll)
    for o in list(scene.objects):
        if o.type=='MESH':coll.objects.link(o)
    cam=bpy.data.objects.new('ReviewCamera',bpy.data.cameras.new('ReviewCamera'));scene.collection.objects.link(cam);scene.camera=cam
    out=HERE/'reviews/fit-structure-v2'/f'reference-{n}';out.mkdir(parents=True,exist_ok=False)
    render(scene,coll,out)
