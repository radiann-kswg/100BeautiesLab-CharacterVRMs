"""Fit the animated lips and oral cavity of a documented Corefolder face to its character."""
import json
from pathlib import Path

import bpy
import numpy as np
from canonical_face import fit_reference_face

HERE = Path(__file__).resolve().parent
UPPER = (374, 373, 372, 371, 370, 129, 130, 131, 132)
LOWER = (374, 375, 376, 369, 368, 128, 134, 133, 132)
RIM = tuple(dict.fromkeys(UPPER + LOWER))
# The closed rim separates the contiguous inner wall from the cheeks. The next
# disconnected island carries the internal oral surface, including the tongue.
ORAL = np.array((*RIM, *range(135, 185), *range(377, 439), *range(676, 740)))
PROFILES = {
    # Native Corefolder number, horizontal scale, fraction of the upper lip to ink.
    6:  (16, .96, .76),
    49: (25, 1.05, .76),
    57: (93, 1.08, .73),
    85: (93, .92, .50),
}


def fit_surround(coords, triangles):
    """Keep the coarse cheek fans facing forward as the much smaller lip articulates."""
    supports = {10, 30, 59, 238, 263, 268, 292, 298}
    extent = np.max(abs(coords[list(RIM), 0]))
    flank = max(.024, extent * 1.55)
    for i in (10, 30, 59, 238, 263, 298):
        x = coords[i, 0]
        new_x = np.sign(x) * min(abs(x), flank)
        coords[i, 1] -= (abs(x) - abs(new_x)) * .17
        coords[i, 0] = new_x
    # In front projection, the signed area must stay positive. Move only the
    # starter's coarse support vertices along the local area gradient.
    points = coords[:, [0, 2]].copy()
    for _ in range(50):
        worst = 0.
        for tri in triangles:
            a, b, c = points[tri]
            area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            clearance = .0000012 - area
            if clearance <= 0:
                continue
            gradient = np.array([[b[1] - c[1], c[0] - b[0]], [c[1] - a[1], a[0] - c[0]],
                                 [a[1] - b[1], b[0] - a[0]]])
            gradient[[vertex not in supports for vertex in tri]] = 0
            norm = np.sum(gradient * gradient)
            if norm > 1e-14:
                points[tri] += gradient * (clearance / norm)
                worst = max(worst, clearance)
        if worst < 1e-9:
            break
    coords[:, [0, 2]] = points


def coordinates(key):
    arr = np.empty(len(key.data) * 3, dtype=np.float32)
    key.data.foreach_get("co", arr)
    return arr.reshape(-1, 3)


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
    radius, strength, offset = {49: (1.65, 1.22, .45), 85: (1.50, 1.24, .46)}.get(number, (.64, 1.14, .20))
    coverage = np.clip(strength - np.abs(yy - (arc + offset)) / (radius + .23 * fade), 0, 1) * fade
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
    if face.get("corefolder_mouth_revision") == 1 and face.get("corefolder_canonical_face") == 4:
        return
    fit_reference_face(face, arm)
    source, x_scale, stroke = PROFILES[number]
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
        if number in (49, 85):
            # Maintain clearance beneath the sparse philtrum triangles of the
            # starter after fitting the narrower native lip. Their projection
            # otherwise crosses the closed edge of #25's small frown.
            z_offset = min(z_offset, float(basis[292, 2] - .013 - source_basis[ai[3], 2]))
        gap = source_basis[ai, 2] - source_basis[bi, 2]
        arc = 1 - np.abs(source_basis[ai, 0] / max(abs(source_basis[0, 0]), 1e-5)) ** 2
        closed = .00042 * np.clip(arc, .05, 1)
        mesh.calc_loop_triangles()
        outer = {10, 30, 59, 238, 263, 268, 292, 298}
        triangles = [np.array(t.vertices[:]) for t in mesh.loop_triangles if outer.intersection(t.vertices)
                     and max(t.vertices) < 439]
        for key in keys:
            coords = coordinates(key)
            profile = measured[f"{source}_{key.name}"].copy()
            profile[:, 0] *= x_scale
            profile[:, 2] += z_offset
            if number in (49, 85):
                profile[:, 1] -= .0038
            middle = .5 * (profile[ai, 2] + profile[bi, 2])
            opening = closed + np.maximum(0, profile[ai, 2] - profile[bi, 2] - gap)
            profile[ai, 2], profile[bi, 2] = middle + opening / 2, middle - opening / 2
            coords[ORAL] = profile
            if number in (49, 57, 85):
                # The #25/#93 lip rings have extra supporting loops. Redistribute
                # their samples across the eight segments of each starter rim;
                # clustered samples next to a vertical corner fold its broad cheek fan.
                for upper_side, lower_side in ((UPPER[4:], LOWER[4:]), (UPPER[4::-1], LOWER[4::-1])):
                    corner = coords[upper_side[-1]].copy()
                    if number != 57 and key.name in ("Joy", "Fun"):
                        corner[0] *= 1.6 if number == 49 else 1.16
                        corner[2] += .002
                    for side in (upper_side, lower_side):
                        center = coords[side[0]].copy()
                        for index, t in zip(side[1:], (.30, .60, .83, 1.)):
                            coords[index, 0] = center[0] + t * (corner[0] - center[0])
                            coords[index, 2] = center[2] + t**1.27 * (corner[2] - center[2])
                if number == 85:
                    # Artwork 1 has a short rising stroke. Its open-mouth expression
                    # in artwork 2 is level. Tilt the actual rim and inner wall at rest.
                    tilt = 0 if key.name in ("a", "i", "u", "e", "o") else .38
                    coords[ORAL, 2] += np.clip(coords[ORAL, 0], -.012, .012) * tilt
                fit_surround(coords, triangles)
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
    if number == 85:
        toon = face.data.materials[0].vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon
        toon.outline_width_mode = "none"
        toon.outline_width_factor = 0
    mesh.update()
    face["corefolder_mouth_revision"] = 1
    face["corefolder_mouth_source"] = json.dumps({"reference": source, "mapped_vertices": len(ORAL),
             "mouth_width_m": float(abs(keys[0].data[374].co.x - keys[0].data[132].co.x))})
