"""Fit the animated lips and oral cavity of a documented Corefolder face to its character."""
import json
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
UPPER = (374, 373, 372, 371, 370, 129, 130, 131, 132)
LOWER = (374, 375, 376, 369, 368, 128, 134, 133, 132)
RIM = tuple(dict.fromkeys(UPPER + LOWER))
# The closed rim separates the contiguous inner wall from the cheeks. The next
# disconnected island carries the internal oral surface, including the tongue.
ORAL = np.array((*RIM, *range(135, 185), *range(377, 439), *range(676, 740)))
PROFILES = {
    # native source, native mesh, horizontal scale, fraction of the painted upper lip
    6:  (16, "Cube.005", .96, .76),
    49: (25, "Cube.009", 1.05, .56),
    57: (93, "Cube.003", 1.08, .73),
    85: (93, "Cube.003", .92, .63),
}


def coordinates(key):
    arr = np.empty(len(key.data) * 3, dtype=np.float32)
    key.data.foreach_get("co", arr)
    return arr.reshape(-1, 3)


def source_indices(target, reference, basis):
    def uv_vertices(mesh):
        loops, uv = mesh.loops, mesh.uv_layers.active.data
        return np.array([l.vertex_index for l in loops]), np.array([c.uv[:] for c in uv])

    dst_indices, dst_uv = uv_vertices(target)
    ref_indices, ref_uv = uv_vertices(reference)
    ref_basis = coordinates(reference.shape_keys.key_blocks[0])
    indices = []
    for i in ORAL:
        uvs = np.unique(dst_uv[dst_indices == i], axis=0)
        if i in RIM:
            # The pale outer face atlas differs by character. The interior seam
            # is identical in these three native references, including split UV loops.
            uvs = uvs[uvs[:, 0] > .6]
        hits = np.unique(np.concatenate([ref_indices[np.max(abs(ref_uv - uv), axis=1) < .000016] for uv in uvs]))
        if abs(basis[i, 0]) > .00015:
            hits = hits[ref_basis[hits, 0] * basis[i, 0] > 0]
        if not len(hits):
            raise ValueError(f"No corresponding native mouth UV for vertex {i}")
        indices.append(int(hits[np.argmin(np.linalg.norm(ref_basis[hits] - basis[i], axis=1))]))
    if len(set(indices)) != len(indices):
        raise ValueError("Native lip, tongue and cavity correspondence is not one-to-one")
    return indices


def paint_lip(face, number, fraction):
    """Paint only the tiny upper-rim UV island; the mark follows the expression mesh."""
    ext = face.data.materials[0].vrm_addon_extension.mtoon1
    src = ext.pbr_metallic_roughness.base_color_texture.index.source
    if src is None or tuple(src.size) != (1024, 1024):
        raise ValueError("Expected the shared 1024px editable face atlas")
    pixels = np.empty(1024 * 1024 * 4, dtype=np.float32)
    src.pixels.foreach_get(pixels)
    data = pixels.reshape(1024, 1024, 4)
    # Source atlas coordinates measured from the #4 upper lip UVs, in bottom-left origin.
    region = data[849:870, 15:49]
    region[:, :, :3] = 1
    xx, yy = np.meshgrid(np.arange(15, 49) + .5, np.arange(849, 870) + .5)
    u = np.clip((xx - 20.85) / 22.65, 0, 1)
    arc = np.interp(xx, [20.85, 27.5, 35.2, 41.2, 43.5], [856.58, 857.40, 859.8, 863.1, 862.3])
    fade = np.clip((fraction - u) / .22, 0, 1)
    coverage = np.clip(1.14 - np.abs(yy - (arc + .20)) / (.64 + .23 * fade), 0, 1) * fade
    coverage *= (xx >= 19.5)
    # Linear-light tint sampled in the same warm brown family as the source line work.
    ink = np.array([.100, .054, .065])
    region[:, :, :3] = 1 - coverage[:, :, None] * (1 - ink)
    out = bpy.data.images.new(f"Corefolder-{number} expression atlas", 1024, 1024, alpha=True)
    out.colorspace_settings.name = src.colorspace_settings.name
    out.alpha_mode = src.alpha_mode
    out.pixels.foreach_set(pixels)
    out.update()
    out.pack()
    ext.pbr_metallic_roughness.base_color_texture.index.source = out
    ext.extensions.vrmc_materials_mtoon.shade_multiply_texture.index.source = out


def finish_face(number, face, arm):
    if face.get("corefolder_mouth_revision") == 1:
        return
    source, mesh_name, x_scale, stroke = PROFILES[number]
    mesh = face.data
    keys = mesh.shape_keys.key_blocks
    if len(mesh.vertices) != 926 or "a" not in keys:
        raise ValueError("Expected the documented #4-derived editable face")
    with np.load(HERE / "mouth-profiles.npz") as measured:
        basis = coordinates(keys[0])
        if not np.array_equal(measured["target_indices"], ORAL):
            raise ValueError("Unexpected mouth landmark order")
        source_basis = measured[f"{source}_Basis"]
        z_offset = float(np.median(basis[[59, 298, 10, 238], 2] - [.7511, .7511, .729, .729]))
        ai = [int(np.flatnonzero(ORAL == i)[0]) for i in UPPER[1:-1]]
        bi = [int(np.flatnonzero(ORAL == i)[0]) for i in LOWER[1:-1]]
        gap = source_basis[ai, 2] - source_basis[bi, 2]
        arc = 1 - np.abs(source_basis[ai, 0] / max(abs(source_basis[0, 0]), 1e-5)) ** 2
        closed = .00042 * np.clip(arc, .05, 1)
        for key in keys:
            coords = coordinates(key)
            profile = measured[f"{source}_{key.name}"].copy()
            profile[:, 0] *= x_scale
            profile[:, 2] += z_offset
            middle = .5 * (profile[ai, 2] + profile[bi, 2])
            opening = closed + np.maximum(0, profile[ai, 2] - profile[bi, 2] - gap)
            profile[ai, 2], profile[bi, 2] = middle + opening / 2, middle - opening / 2
            coords[ORAL] = profile
            key.data.foreach_set("co", coords.ravel())
    # In the #4 source, the entire detached oral island also has spine weights.
    # Lip, cavity, cheek and posterior face borders move with the rigid cranium.
    # Preserve the existing eye-bone weighting on the actual ocular geometry.
    slots = {h.bone: h.node.bone_name for h in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    head = face.vertex_groups.get(slots["head"]) or face.vertex_groups.new(name=slots["head"])
    eyes = {slots.get("leftEye"), slots.get("rightEye")}
    for v in mesh.vertices:
        retained = [(g.group, g.weight) for g in v.groups if face.vertex_groups[g.group].name in eyes and g.weight > 0]
        for index in [g.group for g in v.groups]:
            face.vertex_groups[index].remove([v.index])
        eye_sum = sum(w for _, w in retained)
        for index, weight in retained:
            face.vertex_groups[index].add([v.index], weight / max(1.0, eye_sum), "REPLACE")
        if eye_sum < 1:
            head.add([v.index], 1.0 - eye_sum, "REPLACE")
    # Restore the reference oral surfaces to their textured lip and cavity islands.
    inner = set(ORAL)
    for poly in mesh.polygons:
        if all(v in inner for v in poly.vertices):
            poly.material_index = 0
    paint_lip(face, number, stroke)
    mesh.update()
    face["corefolder_mouth_revision"] = 1
    face["corefolder_mouth_source"] = json.dumps({"reference": source, "mapped_vertices": len(ORAL),
             "mouth_width_m": float(abs(keys[0].data[374].co.x - keys[0].data[132].co.x))})
