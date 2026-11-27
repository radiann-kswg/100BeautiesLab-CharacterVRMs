"""Fit true Corefolder basis tail volumes to the individual official plume landmarks."""
import json
from pathlib import Path

import bmesh
import bpy
import numpy as np

from native_tail_profiles import fork_tip, load_tail, make_plume
from refine_models import toon

HERE = Path(__file__).resolve().parent
TIPS = {
    57: [(163, 9), (382, 9), (18, 122), (527, 125), (211, 169), (31, 443), (515, 443)],
    85: [(263, 6), (107, 58), (422, 56), (11, 256), (518, 254), (63, 370), (466, 367), (262, 490)],
}
# A second tuft belonging to the same continuous plume, measured on the rear atlas.
FORKS = {
    57: {0:(205,10), 1:(342,10), 2:(69,97), 3:(477,98), 4:(332,169)},
    85: {3:(39,158), 4:(489,158), 5:(59,286), 6:(468,286)},
}
# Root height, bulb depth, tip depth, transverse radius (metres).
# Roots sit on the rump; the far and near layers can pass around one another.
SECTIONS = {
    57: [(.42,.39,.30,.209), (.42,.39,.31,.209),
         (.38,.27,.16,.214), (.38,.27,.16,.214),
         (.40,.56,.56,.231), (.30,.40,.19,.224), (.30,.40,.19,.224)],
    85: [(.41,.43,.36,.204), (.40,.30,.21,.202), (.40,.30,.21,.202),
         (.35,.21,.09,.196), (.35,.21,.09,.196), (.31,.42,.12,.216),
         (.31,.42,.12,.216), (.28,.50,.53,.218)],
}


def atlas_material(number, folder):
    image = bpy.data.images.load(str(folder / f"Tails-{number}.png"), check_existing=False)
    image.pack()
    mat = toon(f"{number} • fox-tail rear atlas", "#FFFFFF", .0005 if number == 85 else 0)
    mtoon = mat.vrm_addon_extension.mtoon1
    mtoon.pbr_metallic_roughness.base_color_texture.index.source = image
    mtoon.pbr_metallic_roughness.base_color_factor = (.765, .765, .765, 1)
    style = mtoon.extensions.vrmc_materials_mtoon
    style.shade_multiply_texture.index.source = image
    style.shade_color_factor = (.80, .78, .74)
    style.shading_shift_factor = 1
    style.shading_toony_factor = 1
    style.gi_equalization_factor = .861002743
    style.outline_lighting_mix_factor = 0
    return mat


def fit_outline(painted, faces, lengths, center, outline):
    """Adjust the rear silhouette gradually; preserve the complete depth of each section."""
    pairs = sorted({tuple(sorted((a,b))) for f in faces for a,b in zip(f, (*f[1:],f[0]))})
    source = painted[:,[0,2]] - center
    target = outline-center
    angles = np.arange(180) * (2*np.pi/180)
    directions = np.stack((np.cos(angles),np.sin(angles)), axis=1)

    def radii(segments):
        start, end = segments[:,0], segments[:,1]
        dx, dy = (end-start).T
        denom = directions[:,0,None]*dy - directions[:,1,None]*dx
        denom[np.abs(denom)<1.e-10] = np.nan
        t = (start[:,0]*dy-start[:,1]*dx)/denom
        u = (start[:,0]*directions[:,1,None]-start[:,1]*directions[:,0,None])/denom
        return np.max(np.where((t>=0)&(u>=0)&(u<=1),t,0),axis=1)

    a = radii(source[np.asarray(pairs)])
    b = radii(np.stack((target, np.roll(target,-1,axis=0)),axis=1))
    gain = np.clip(b/np.maximum(a,.001),.74,1.42)-1.
    gain = sum(np.roll(gain,k)*w for k,w in ((-2,.08),(-1,.22),(0,.4),(1,.22),(2,.08)))
    angle = np.arctan2(source[:,1],source[:,0])
    factor = np.interp(angle, angles, gain, period=2*np.pi)
    influence = .86*np.minimum(1.,lengths/.26)
    return source * (factor*influence)[:,None]


def revise_tails(n, arm, collection):
    folder = HERE.parent / f"Corefolder-{n}/Modeling"
    atlas = json.loads((folder / f"Tails-{n}.json").read_text())
    width, height = atlas["size"]
    scale = (1.215 if n == 57 else 1.22) / (width - 12)
    upper = 5 if n == 57 else 3
    source = load_tail()
    material = atlas_material(n, folder)
    guides = {}

    def landmark(point, depth):
        return np.array([(point[0] - width / 2) * scale, depth, .014 + (height - 6 - point[1]) * scale])

    for i, (record, tip_px, section) in enumerate(zip(atlas["plumes"], TIPS[n], SECTIONS[n], strict=True)):
        name = f"Tail_{'Upper' if i < upper else 'Lower'}_{i + 1:02}"
        obj = collection.objects[name]
        root_z, bulb_y, tip_y, radius = section
        bulb = landmark(record["center"], bulb_y)
        tip = landmark(tip_px, tip_y)
        root = np.array([bulb[0] * .32, .225, root_z])
        # The two low side plumes on Hakko curl under the outside of the belly.
        # Keep the painted tip attached to its fur as this axis changes.
        bulb_shift = np.zeros(3)
        tip_shift = np.zeros(3)
        if n == 85 and i in (5, 6):
            sign = np.sign(bulb[0])
            bulb_shift = np.array([.055 * sign, 0., -.093])
            tip_shift = np.array([.063 * sign, 0., -.115])
        other = FORKS[n].get(i)
        tip_a = tip + tip_shift
        target = tip_a
        if other:
            tip_b = landmark(other, tip_y + (.033 if i % 2 else -.019)) + tip_shift
            target = (tip_a + tip_b) * .5
        xyz, faces, guide = make_plume(source, root, bulb + bulb_shift, target,
                                       radius, radius * .91, .095)
        if other:
            xyz, faces, distances = fork_tip(source, xyz, faces, tip_a, tip_b)
        else:
            distances = np.empty(len(xyz))
            for ids, s, *_ in source[0]:
                distances[ids] = s
        bulb_weight = np.interp(distances, [0., .49, 1.], [0., 1., 0.])
        tip_weight = np.interp(distances, [0., .49, 1.], [0., 0., 1.])
        painted = xyz - bulb_weight[:,None] * bulb_shift - tip_weight[:,None] * tip_shift
        contour = np.array([landmark(point,0)[[0,2]] for point in record["outline"]])
        correction = fit_outline(painted, faces, distances, bulb[[0,2]], contour)
        xyz[:,[0,2]] += correction
        painted[:,[0,2]] += correction
        for point, band in zip(guide, (0,4,7,10,14)):
            distance = abs(distances-source[0][band][1])
            shift = correction[distance <= distance.min()+1.e-7].mean(axis=0)
            point.x += shift[0]
            point.z += shift[1]
        mesh = bpy.data.meshes.new(name + " • Corefolder basis sections")
        mesh.from_pydata(xyz.tolist(), [], faces)
        mesh.update()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        if any(not edge.is_manifold for edge in bm.edges) or any(face.calc_area() < 1.e-10 for face in bm.faces):
            raise ValueError(f"Open or degenerate surface in {name}")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(material)
        uv = mesh.uv_layers.new(name="Local plume atlas")
        x0, y0, x1, y1 = record["crop"]
        tx, ty = record["tile"]
        px = painted[:, 0] / scale + width / 2
        py = height - 6 - (painted[:, 2] - .014) / scale
        u = (tx + .5 + 251 * np.clip((px - x0) / (x1 - x0), 0, 1)) / 1024
        v = 1 - (ty + .5 + 251 * np.clip((py - y0) / (y1 - y0), 0, 1)) / 1024
        for poly in mesh.polygons:
            poly.use_smooth = True
            for li in poly.loop_indices:
                idx = mesh.loops[li].vertex_index
                uv.data[li].uv = (u[idx], v[idx])
        obj.data = mesh
        # Bake a level of the source subdivision before spring weights are assigned.
        subdiv = obj.modifiers.new("Basis tail smoothing", "SUBSURF")
        subdiv.levels = 1
        with bpy.context.temp_override(object=obj, active_object=obj):
            bpy.ops.object.modifier_move_to_index(modifier=subdiv.name, index=0)
            bpy.ops.object.modifier_apply(modifier=subdiv.name)
        guides[name] = [tuple(point) for point in guide]
    return guides
