"""Build 57/85 foundations from the common body and #4 rig/face; AI points and references never enter VRM export.
Run with a separate Blender process. Outputs are scaffolds, not finished characters.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from review import point_object


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    shader = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    shader.inputs['Base Color'].default_value = (*rgb, 1)
    mat.diffuse_color = (*rgb, 1)
    mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    return mat


def label(collection, text, location, size=.13):
    curve = bpy.data.curves.new(text, 'FONT')
    curve.body, curve.size = text, size
    obj = bpy.data.objects.new(text, curve)
    collection.objects.link(obj)
    obj.location, obj.rotation_euler = location, (math.pi/2, 0, 0)
    mat = material('Label ink', (.8,.8,.8))
    curve.materials.append(mat)
    return obj


def board(collection, path, location, width):
    image = bpy.data.images.load(str(path), check_existing=True)
    image.pack()
    height = width * image.size[1] / image.size[0]
    mesh = bpy.data.meshes.new(path.stem)
    mesh.from_pydata([(-width/2,0,-height/2),(width/2,0,-height/2),(width/2,0,height/2),(-width/2,0,height/2)], [], [(0,1,2,3)])
    uv = mesh.uv_layers.new()
    for datum, xy in zip(uv.data, ((0,0),(1,0),(1,1),(0,1))): datum.uv = xy
    mat = material(path.stem, (1,1,1))
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    texture = nodes.new('ShaderNodeTexImage'); texture.image = image
    emission = nodes.new('ShaderNodeEmission')
    links.new(texture.outputs['Color'], emission.inputs['Color'])
    links.new(emission.outputs[0], next(n for n in nodes if n.type=='OUTPUT_MATERIAL').inputs['Surface'])
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(path.stem, mesh)
    collection.objects.link(obj); obj.location = location
    return obj


def common_body(source):
    """Use the common body surface; transfer weights only from Mochi's unclothed body."""
    import bmesh
    donor = bpy.data.objects['Body']
    donor.name = 'Temporary weight donor'
    adjacency = [set() for _ in donor.data.vertices]
    for edge in donor.data.edges:
        a, b = edge.vertices
        adjacency[a].add(b); adjacency[b].add(a)
    unseen = set(range(len(adjacency))); components = []
    while unseen:
        todo = [unseen.pop()]; component = set(todo)
        while todo:
            for v in adjacency[todo.pop()] - component:
                component.add(v); unseen.discard(v); todo.append(v)
        components.append(component)
    bare_body = max(components, key=len)
    bm = bmesh.new(); bm.from_mesh(donor.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in bare_body], context='VERTS')
    bm.to_mesh(donor.data); bm.free()
    with bpy.data.libraries.load(str(source), link=False) as (src, dst):
        dst.objects = ['body']
    body, = dst.objects
    body.name = 'Body'; bpy.context.scene.collection.objects.link(body)
    bpy.ops.object.select_all(action='DESELECT'); body.select_set(True)
    bpy.context.view_layer.objects.active = body
    for mod in list(body.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    smooth = body.modifiers.new('Common body subdivision', 'SUBSURF'); smooth.levels = 2
    bpy.ops.object.modifier_apply(modifier=smooth.name)
    for poly in body.data.polygons: poly.use_smooth = True
    for group in donor.vertex_groups: body.vertex_groups.new(name=group.name)
    transfer = body.modifiers.new('Bare body weights', 'DATA_TRANSFER')
    transfer.object = donor; transfer.use_vert_data = True
    transfer.data_types_verts = {'VGROUP_WEIGHTS'}
    transfer.vert_mapping = 'POLYINTERP_NEAREST'
    transfer.layers_vgroup_select_src = 'ALL'; transfer.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.modifier_apply(modifier=transfer.name)
    for vertex in body.data.vertices:
        weights = [(g.group,g.weight) for g in vertex.groups if g.weight > 0]
        total = sum(w for _,w in weights)
        if total <= 0: raise ValueError('Common body has an unweighted vertex')
        for index, weight in weights: body.vertex_groups[index].add([vertex.index],weight/total,'REPLACE')
    arm = bpy.data.objects['Armature']
    body.parent = arm
    skin = body.modifiers.new('Armature', 'ARMATURE'); skin.object = arm
    bpy.data.objects.remove(donor, do_unlink=True)
    body['geometry_source'] = source.relative_to(ROOT).as_posix()
    body['weight_transfer'] = 'Nearest polygon interpolation from largest connected #4 Body surface; garments excluded'
    return {'donor_bare_body_vertices':len(bare_body), 'body_vertices':len(body.data.vertices),
            'common_source':source.relative_to(ROOT).as_posix(), 'common_sha256':sha(source),
            'body_coordinate_sha256':hashlib.sha256(np.array([v.co[:] for v in body.data.vertices],dtype='<f4').tobytes()).hexdigest()}


def build(number, references):
    source = HERE.parent / 'Corefolder-4/VRCModel_CoreFloder-4.blend'
    folder = HERE.parent / f'Corefolder-{number}'
    training = folder / 'Training'
    sheet = training / f'ThreeView-CoreFolder-{number}.png'
    sample = HERE / f'runs/sample{number}-v1/sample.npz'
    checkpoint = HERE / 'runs/all6-v2/checkpoint.pt'
    blend = folder / f'Corefolder-{number}-ModelingFoundation.blend'
    vrm = ROOT / f'Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{number}/ModelingFoundation/Corefolder-{number}-Foundation.vrm'
    vrm.parent.mkdir(parents=True, exist_ok=True)
    original_hash = sha(source)
    sheet_hash = sha(sheet)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.name = f'Corefolder-{number} Modeling Foundation'
    for obj in list(bpy.data.objects):
        if obj.name not in ('Armature','Body','Face'):
            bpy.data.objects.remove(obj, do_unlink=True)
    arm = bpy.data.objects['Armature']
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in list(arm.data.edit_bones):
        if bone.name.startswith('Tail'): arm.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode='OBJECT')
    body_provenance = common_body(ROOT / '100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend')
    ex = arm.data.vrm_addon_extension
    # Original .blend retained legacy VRM0 mappings; use those for this neutral draft.
    ex.spec_version = '0.0'
    ex.vrm0.secondary_animation.bone_groups.clear()
    ex.vrm0.secondary_animation.collider_groups.clear()
    ex.vrm0.meta.title = f'Corefolder-{number} Modeling Foundation (unfinished neutral base)'
    ex.vrm0.meta.version = 'foundation-v2-common-body'
    ex.vrm0.meta.texture = None
    neutral = material('Foundation neutral - character texture pending', (.55,.55,.55))
    for name in ('Body','Face'):
        obj = bpy.data.objects[name]
        obj.data.materials.clear(); obj.data.materials.append(neutral)
        obj.select_set(True)
    # Delete unused source textures/materials only in this derived in-memory copy.
    for mat in list(bpy.data.materials):
        if mat != neutral: bpy.data.materials.remove(mat)
    for image in list(bpy.data.images):
        if image.type == 'IMAGE': bpy.data.images.remove(image)
    base = bpy.data.collections.new('01 Editable neutral base - detail modeling pending')
    scene.collection.children.link(base)
    for obj in (arm,bpy.data.objects['Body'],bpy.data.objects['Face']):
        for coll in list(obj.users_collection): coll.objects.unlink(obj)
        base.objects.link(obj)
    result = bpy.ops.export_scene.vrm(filepath=str(vrm), use_addon_preferences=False,
        export_only_selections=True, export_invisibles=False, armature_object_name=arm.name, ignore_warning=True)
    if result != {'FINISHED'} or not vrm.exists(): raise RuntimeError(f'VRM export failed: {result}')
    # Everything below is reference-only and is added after the scaffold VRM is exported.
    refs = bpy.data.collections.new('02 Official references - DO NOT EXPORT')
    scene.collection.children.link(refs)
    board(refs, sheet, (-2.0,.35,.85), 2.3)
    label(refs, f'{number} | official three-view sheet', (-3.15,.30,1.77), .12)
    extras = bpy.data.collections.new('Additional DB sheets - toggle visibility')
    refs.children.link(extras)
    for i, item in enumerate(references['files']):
        path = HERE / 'targets' / item['file']
        assert sha(path) == item['sha256']
        board(extras, path, (-2+2.5*i,1,3), 2)
    extras.hide_viewport = True; extras.hide_render = True
    guides = bpy.data.collections.new('03 AI coarse points - DO NOT EXPORT')
    scene.collection.children.link(guides)
    local_sample = training / 'AI-ShapeGuide.npz'
    shutil.copyfile(sample, local_sample)
    shutil.copyfile(sample.with_suffix('.ply'), training / 'AI-ShapeGuide.ply')
    points = point_object(local_sample, f'{number} AI rough guide - not a mesh')
    for coll in list(points.users_collection): coll.objects.unlink(points)
    guides.objects.link(points)
    points.location = (1.5,0,.65)
    label(guides, 'AI: 1024 points / unverified', (.85,0,1.35), .1)
    label(refs, 'Common body / rig', (-.55,0,1.35), .11)
    label(refs, f'{number} | MODELING FOUNDATION - unfinished', (-3.15,.3,2.05), .16)
    tail = references['settings']['TailsUnit'][0]
    label(refs, f"Official tail count: {tail['Count']} | tail mesh / rig pending", (-3.15,0,-.38), .12)
    palette = bpy.data.collections.new('04 Official palette swatches - DO NOT EXPORT')
    scene.collection.children.link(palette)
    for i, color in enumerate(references['settings']['ColorPalette']):
        hx = color['Hex']; rgb = np.array([int(hx[j:j+2],16)/255 for j in (1,3,5)])
        linear = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
        mat = material(f'{number} DB {hx}', linear)
        mat['official_palette_entry'] = json.dumps(color, ensure_ascii=False)
        bpy.ops.mesh.primitive_cube_add(size=.13, location=(-2.95+i*.37,0,-.02))
        obj = bpy.context.object; obj.name = hx
        for coll in list(obj.users_collection): coll.objects.unlink(obj)
        palette.objects.link(obj); obj.data.materials.append(mat)
        label(palette, hx, (-3.1+i*.37,0,-.14), .065)
    notes = {'status':'unfinished modeling foundation; not character-complete VRM',
        'body_provenance':body_provenance,
        'source_blend':source.relative_to(ROOT).as_posix(), 'source_sha256':original_hash,
        'three_view_sha256':sheet_hash, 'checkpoint_sha256':sha(checkpoint),
        'sample_image':references['training_images'][0], 'sample_seed':2026,
        'sample_sha256':sha(local_sample), 'ai_use':'image-conditioned inference from all6-v2; no new weight training in this step',
        'settings':references['settings'], 'source_record_sha256':references['record_sha256'],
        'base_bones':len(arm.data.bones), 'mapped_humanoid_bones':sum(bool(b.node.bone_name) for b in ex.vrm0.humanoid.human_bones),
        'face_shape_keys':[k.name for k in bpy.data.objects['Face'].data.shape_keys.key_blocks],
        'pending':['character-specific mesh and textures','tail mesh and chains according to official branches','expression fitting','spring bones','final VRM validation'],
        'vrm':vrm.relative_to(ROOT).as_posix(), 'vrm_sha256':sha(vrm)}
    text = json.dumps(notes,ensure_ascii=False,indent=2)
    (training/'foundation.json').write_text(text,encoding='utf-8')
    bpy.data.texts.new(f'README-{number}-foundation.json').write(text)
    scene['foundation_status'] = notes['status']
    bpy.ops.object.camera_add(location=(-.6,-8,1.9))
    camera = bpy.context.object; camera.name='Foundation Review Camera'
    camera.rotation_euler=(Vector((-.6,0,.9))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'; camera.data.ortho_scale=6.2; scene.camera=camera
    bpy.ops.object.light_add(type='AREA', location=(0,-3,4))
    bpy.context.object.data.energy=500; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
    scene.world = bpy.data.worlds.new('Foundation dark background')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.clear()
    background = scene.world.node_tree.nodes.new('ShaderNodeBackground')
    world_output = scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
    scene.world.node_tree.links.new(background.outputs[0], world_output.inputs['Surface'])
    background.inputs['Color'].default_value = (.025,.03,.04,1)
    background.inputs['Strength'].default_value = .6
    scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
    scene.render.resolution_x=1400; scene.render.resolution_y=750; scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard'
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.region_3d.view_perspective='CAMERA'
    bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active=arm
    scene.render.filepath=str(training/'Foundation-Overview.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.render.render(write_still=True)
    assert sha(source)==original_hash and sha(sheet)==sheet_hash
    print(json.dumps({'id':number,'blend':str(blend),'vrm':str(vrm),'bones':notes['base_bones'],'humanoid':notes['mapped_humanoid_bones']}), flush=True)


if __name__ == '__main__':
    if not bpy.app.background: raise RuntimeError('Use a separate Blender process')
    references=json.loads((HERE/'targets/db-references.json').read_text(encoding='utf-8'))
    for number in (57,85): build(number,references[str(number)])
