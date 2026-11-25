"""Build and export Blender world-space appendages on a Corefolder VRM 0.x starter."""

from bisect import bisect_right
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import bpy
from mathutils import Matrix, Vector

from prepare import read_vrm


def _bone_name(arm, name):
    if name in arm.data.bones:
        return name
    for slot in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones:
        if slot.bone == name and slot.node.bone_name in arm.data.bones:
            return slot.node.bone_name
    raise ValueError(f"{arm.name} has no bone or humanoid slot {name!r}")


def _meshes(value):
    objects = [value] if isinstance(value, bpy.types.Object) else list(value)
    if not objects or any(obj.type != "MESH" for obj in objects):
        raise ValueError("Expected one or more mesh objects")
    return objects


def add_collider_group(arm, name, parent, spheres):
    """Create bone-local VRM spheres from (world center, world radius) pairs."""
    parent = _bone_name(arm, parent)
    spheres = list(spheres)
    if not spheres or any(radius <= 0 for _, radius in spheres):
        raise ValueError("Each collider needs a positive radius")
    groups = arm.data.vrm_addon_extension.vrm0.secondary_animation.collider_groups
    bpy.ops.vrm.add_vrm0_secondary_animation_collider_group(armature_object_name=arm.name)
    index = len(groups) - 1
    group = groups[index]
    group.node.bone_name = parent
    for i, (center, radius) in enumerate(spheres):
        bpy.ops.vrm.add_vrm0_secondary_animation_collider_group_collider(
            armature_object_name=arm.name, collider_group_index=index, bone_name=parent)
        obj = group.colliders[-1].bpy_object
        obj.name = f"{name}_collider_{i + 1:02d}"
        bpy.context.view_layer.update()
        obj.matrix_world = Matrix.Translation(Vector(center))
        obj.empty_display_size = radius
        obj.hide_render = True
    bpy.context.view_layer.update()
    return group


def bind_to_chain(arm, meshes, bones):
    """Weight each vertex along a curved centerline, preserving object and key geometry."""
    chain = [arm.data.bones[name] for name in bones]
    if len(chain) < 3 or not chain[0].parent:
        raise ValueError("Expected a connected spring with a parent and a terminal bone")
    points = [arm.matrix_world @ bone.head_local for bone in chain]
    vectors = [end - start for start, end in zip(points, points[1:])]
    stations = [0.0]
    for direction in vectors:
        stations.append(stations[-1] + direction.length)
    # The exact attachment stays on the parent. The interiors of neighboring
    # segments share weight, including when a tail makes a tight bend.
    samples = [0.0] + [(a + b) / 2 for a, b in zip(stations, stations[1:])] + [stations[-1]]
    names = [chain[0].parent.name, *bones]
    bpy.context.view_layer.update()
    for obj in _meshes(meshes):
        world = obj.matrix_world.copy()
        obj.parent = arm
        obj.parent_type = "OBJECT"
        obj.parent_bone = ""
        obj.matrix_world = world
        modifiers = [m for m in obj.modifiers if m.type == "ARMATURE"]
        if any(m.object and m.object != arm for m in modifiers) or len(modifiers) > 1:
            raise ValueError(f"Ambiguous armature modifiers on {obj.name}")
        modifier = modifiers[0] if modifiers else obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = arm
        for group in list(obj.vertex_groups):
            if group.name in arm.data.bones:
                obj.vertex_groups.remove(group)
        groups = [obj.vertex_groups.new(name=name) for name in names]
        for vertex in obj.data.vertices:
            pos = world @ vertex.co
            closest = float("inf")
            distance = 0.0
            for i, direction in enumerate(vectors):
                fraction = min(1.0, max(0.0, (pos - points[i]).dot(direction) / direction.length_squared))
                error = (pos - (points[i] + fraction * direction)).length_squared
                if error < closest:
                    closest = error
                    distance = stations[i] + fraction * direction.length
            left = min(len(samples) - 2, max(0, bisect_right(samples, distance) - 1))
            share = (distance - samples[left]) / (samples[left + 1] - samples[left])
            share = max(0.0, min(1.0, share))
            if share < 1.0:
                groups[left].add([vertex.index], 1.0 - share, "REPLACE")
            if share > 0.0:
                groups[left + 1].add([vertex.index], share, "REPLACE")
    bpy.context.view_layer.update()


def register_spring(arm, name, root, kind, radius, colliders, drag_force=None):
    # #93's native VRM has a fan of tails and side hair. Its spring groups
    # retain their authored rest silhouette under gravity, like all six references.
    stiffness, drag, gravity = {"tail": (0.8, 0.4, 0.0), "hair": (0.96, 0.4, 0.0)}[kind]
    secondary = arm.data.vrm_addon_extension.vrm0.secondary_animation
    group = secondary.bone_groups.add()
    group.comment = name
    group.stiffiness, group.drag_force, group.gravity_power = stiffness, drag if drag_force is None else drag_force, gravity
    group.gravity_dir = (0.0, 0.0, -1.0)
    group.hit_radius = radius
    group.bones.add().bone_name = root
    for collider in colliders:
        group.collider_groups.add().collider_group_uuid = collider.uuid


def add_spring_chain(arm, mesh, name, points, *, parent="hips", kind="tail",
                     radius=0.025, colliders=(), drag_force=None):
    """Create one independent VRM root per tuft. Points are in Blender world meters."""
    objects = _meshes(mesh)
    points = [arm.matrix_world.inverted() @ Vector(p) for p in points]
    if len(points) < 3 or any((b - a).length < 1e-6 for a, b in zip(points, points[1:])):
        raise ValueError(f"Spring {name} needs distinct root, middle and tip points")
    parent = _bone_name(arm, parent)
    names = [f"{name}_{n:02d}" for n in range(1, len(points))] + [f"{name}_end"]
    if any(n in arm.data.bones or len(n.encode("utf8")) > 63 for n in names):
        raise ValueError(f"Duplicate or overly long bone name in spring {name}")
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        prev = arm.data.edit_bones[parent]
        ends = points[1:] + [points[-1] + 0.15 * (points[-1] - points[-2])]
        for i, (bone_name, start, end) in enumerate(zip(names, points, ends)):
            bone = arm.data.edit_bones.new(bone_name)
            bone.head, bone.tail = start, end
            bone.parent = prev
            bone.use_connect = i > 0
            prev = bone
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    bind_to_chain(arm, objects, names)
    register_spring(arm, name, names[0], kind, radius, colliders, drag_force)
    return names


def _select(arm, meshes):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in [arm, *meshes]:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm


@contextmanager
def export_mesh_groups(arm, meshes):
    """Join export-only copies; keep morph, first-person and modifier targets intact."""
    ext = arm.data.vrm_addon_extension.vrm0
    fixed = {a.mesh.mesh_object_name for a in ext.first_person.mesh_annotations}
    fixed.update(b.mesh.mesh_object_name for g in ext.blend_shape_master.blend_shape_groups for b in g.binds)
    tail_bones = set()
    hips = _bone_name(arm, "hips")
    for group in ext.secondary_animation.bone_groups:
        for entry in group.bones:
            root = arm.data.bones.get(entry.bone_name)
            if root and root.parent and root.parent.name == hips:
                tail_bones.update(b.name for b in [root, *root.children_recursive])
    head = arm.data.bones[_bone_name(arm, "head")]
    head_bones = {b.name for b in [head, *head.children_recursive]}
    batches = {"Body": [], "Hair": [], "Tail": [], "Outfit": []}
    selected = []
    for obj in meshes:
        compatible = all(
            (m.type == "ARMATURE" and m.object == arm) or
            (m.type == "NODES" and m.node_group and m.node_group.name.startswith("VRM Add-on MToon 1.0 Outline"))
            for m in obj.modifiers)
        if obj.name in fixed or obj.data.shape_keys or len(obj.data.uv_layers) > 1 or not compatible:
            if obj.get("corefolder_layer") == "Outfit":
                raise ValueError(f"Clothing {obj.name} needs an independent morph/UV or modifier binding")
            selected.append(obj)
            continue
        used = {g.group for v in obj.data.vertices for g in v.groups if g.weight > 1e-6}
        names = {obj.vertex_groups[i].name for i in used}
        if not names:
            if obj.get("corefolder_layer") == "Outfit":
                raise ValueError(f"Clothing {obj.name} is missing bone weights")
            selected.append(obj)
            continue
        if obj.get("corefolder_layer") == "Outfit":
            key = "Outfit"
        elif obj.get("corefolder_layer") == "Base" or obj.name == "Corefolder Cranial Base":
            key = "Body"
        elif names & tail_bones:
            key = "Tail"
        else:
            key = "Hair" if names <= head_bones else "Body"
        batches[key].append(obj)
    collection = bpy.data.collections.new("Temporary VRM export parts")
    bpy.context.scene.collection.children.link(collection)
    copied_data = []
    renamed = []
    try:
        for label, originals in batches.items():
            if not originals:
                continue
            parts = []
            for obj in originals:
                part = obj.copy()
                part.data = obj.data.copy()
                collection.objects.link(part)
                if part.data.uv_layers.active:
                    part.data.uv_layers.active.name = "UVMap"
                copied_data.append(part.data.name)
                parts.append(part)
            bpy.ops.object.select_all(action="DESELECT")
            for part in parts:
                part.select_set(True)
            active = parts[0]
            bpy.context.view_layer.objects.active = active
            if len(parts) > 1 and bpy.ops.object.join() != {"FINISHED"}:
                raise RuntimeError(f"Cannot join {label} export copies")
            existing = bpy.data.objects.get(label)
            if existing in originals:
                renamed.append((existing, label))
                existing.name = "Editable " + label
            active.name = label
            selected.append(active)
        _select(arm, selected)
        yield selected
    finally:
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)
        for name in copied_data:
            data = bpy.data.meshes.get(name)
            if data and not data.users:
                bpy.data.meshes.remove(data)
        for obj, label in renamed:
            obj.name = label
        _select(arm, meshes)


def save_character(arm, meshes, blend_path, vrm_path, *, title, version="1.0", character_number=None):
    """Pack the editable scene and export only the specified character meshes and rig."""
    meshes = _meshes(meshes)
    blend_path, vrm_path = Path(blend_path).resolve(), Path(vrm_path).resolve()
    if Path(bpy.data.filepath).resolve() == blend_path:
        raise ValueError("Write to an output path separate from the source blend")
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    vrm_path.parent.mkdir(parents=True, exist_ok=True)
    ext = arm.data.vrm_addon_extension
    if ext.spec_version != "0.0":
        raise ValueError("Expected a VRM 0.x editable starter")
    ext.vrm0.meta.title, ext.vrm0.meta.version = title, str(version)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if character_number is not None:
        from face_articulation import finish_face
        face, = [o for o in meshes if o.name == "Face"]
        finish_face(character_number, face, arm)
    _select(arm, meshes)
    bpy.context.scene["corefolder_stage"] = "Individual character with expressions and secondary animation"
    bpy.context.scene["corefolder_export_meshes"] = json.dumps([o.name for o in meshes], ensure_ascii=False)
    bpy.context.view_layer.update()
    # Pack resources before saving the blend in a different directory.
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.file_preview_type = "NONE"
    with TemporaryDirectory(dir=vrm_path.parent, prefix=".rig-") as vrm_stage, TemporaryDirectory(
            dir=blend_path.parent, prefix=".rig-") as blend_stage:
        staged_vrm = Path(vrm_stage) / vrm_path.name
        with export_mesh_groups(arm, meshes):
            result = bpy.ops.export_scene.vrm(filepath=str(staged_vrm), use_addon_preferences=False,
                        export_only_selections=True, armature_object_name=arm.name, ignore_warning=True)
        if result != {"FINISHED"}:
            raise RuntimeError(f"VRM export failed: {result}")
        doc, digest = read_vrm(staged_vrm)
        if any(obj.get("corefolder_layer") == "Outfit" for obj in meshes):
            outfit_nodes = [n for n in doc["nodes"] if n.get("name") == "Outfit" and "mesh" in n]
            if len(outfit_nodes) != 1 or "skin" not in outfit_nodes[0]:
                raise ValueError("Expected an independently skinned Outfit node for the tagged clothing")
        vrm = doc["extensions"]["VRM"]
        animation = vrm["secondaryAnimation"]
        exported = [[doc["nodes"][i]["name"] for i in g["bones"]] for g in animation["boneGroups"]]
        expected = [[b.bone_name for b in g.bones] for g in ext.vrm0.secondary_animation.bone_groups]
        if exported != expected or not exported:
            raise ValueError(f"Exported spring roots differ: {exported!r} / {expected!r}")
        expressions = vrm["blendShapeMaster"]["blendShapeGroups"]
        if not any(b["weight"] > 0 for group in expressions for b in group.get("binds", [])):
            raise ValueError("Missing bound facial expressions")
        staged_blend = Path(blend_stage) / blend_path.name
        result = bpy.ops.wm.save_as_mainfile(filepath=str(staged_blend), copy=True, relative_remap=False)
        if result != {"FINISHED"}:
            raise RuntimeError(f"Blend save failed: {result}")
        # A VRM opened by a viewer can be locked on Windows. Restore the
        # preceding editable revision if the second file cannot be published.
        previous = Path(blend_stage) / "previous.blend"
        if blend_path.is_file():
            shutil.copy2(blend_path, previous)
        staged_blend.replace(blend_path)
        try:
            staged_vrm.replace(vrm_path)
        except OSError:
            if previous.is_file():
                previous.replace(blend_path)
            else:
                blend_path.unlink()
            raise
    return {"sha256": digest, "roots": exported, "blend": str(blend_path), "vrm": str(vrm_path)}
