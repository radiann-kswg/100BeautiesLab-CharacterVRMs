"""Read-only source inspection and consistent orthographic clay renders in background Blender."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]


def inspect(source, output, vrm=False):
    output.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    if vrm:
        bpy.ops.wm.vrm_license_warning(filepath=str(source), import_anyway=True,
            extract_textures_into_folder=False, enable_mtoon_outline_preview=False)
    else:
        bpy.ops.import_scene.gltf(filepath=str(source))
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        raise ValueError('No mesh')
    points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (lo + hi) / 2
    scale = max(hi - lo)
    stats = {'source': str(source), 'sha256': digest, 'bounds': [list(lo), list(hi)],
        'mesh_objects': len(meshes), 'vertices': sum(len(o.data.vertices) for o in meshes),
        'polygons': sum(len(o.data.polygons) for o in meshes),
        'armatures': sum(o.type == 'ARMATURE' for o in bpy.context.scene.objects),
        'shape_keys': {o.name: len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0 for o in meshes},
        'uv_layers': {o.name: len(o.data.uv_layers) for o in meshes},
        'render': 'Normalized size, orthographic, Blender workbench studio clay; not a material/MToon evaluation'}
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    shade = scene.display.shading
    shade.light = 'STUDIO'
    shade.color_type = 'SINGLE'
    shade.single_color = (.65, .65, .65)
    shade.show_shadows = True
    shade.show_cavity = True
    shade.background_type = 'WORLD'
    scene.world.color = (.12, .12, .12)
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    camera = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = scale * 1.18
    # Observed orientation of these two align_image drafts: face points +X.
    views = [('front', (0,-1,0)), ('side', (1,0,0)), ('back', (0,1,0))] if vrm else [
        ('front', (1,0,0)), ('side', (0,1,0)), ('back', (-1,0,0))]
    stats['camera_directions'] = dict(views)
    for name, direction in views:
        direction = Vector(direction)
        camera.location = center + direction * scale * 3
        camera.rotation_euler = (-direction).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath = str(output / (name + '.png'))
        bpy.ops.render.render(write_still=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    (output / 'inspection.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    print('INSPECTED', output.name, stats['polygons'], flush=True)


if __name__ == '__main__':
    if not bpy.app.background:
        raise RuntimeError('Background process required')
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output = args.output.resolve()
    for item in json.loads(args.manifest.read_text(encoding='utf-8-sig')):
        inspect(Path(item['source']), args.output / item['name'], item.get('vrm', False))
