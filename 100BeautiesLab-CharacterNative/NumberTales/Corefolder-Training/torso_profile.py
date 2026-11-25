"""Blend a little of the original cage contour into the common VRM torso."""
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

BASE = Path(__file__).resolve().parents[2] / "Basis/Corefolder/VRCModel_CoreFloder-Base.blend"


def section_bounds(obj, levels):
    points = np.asarray([obj.matrix_world @ v.co for v in obj.data.vertices],dtype=float)
    edges = np.asarray([e.vertices[:] for e in obj.data.edges])
    a,b = points[edges].transpose(1,0,2)
    result = []
    for height in levels:
        select = (a[:,2] <= height) != (b[:,2] <= height)
        start, end = a[select], b[select]
        cross = start+(end-start)*((height-start[:,2])/(end[:,2]-start[:,2]))[:,None]
        result.append([cross[:,0].min(),cross[:,0].max(),cross[:,1].min(),cross[:,1].max()])
    return np.asarray(result)


def fit_common_torso(body):
    """Keep placement and skinning, easing shoulders and hem toward the unsmoothed base."""
    levels = np.arange(.01,.701,.01)
    with bpy.data.libraries.load(str(BASE),link=False) as (_, target):
        target.objects = ["body"]
    original, = target.objects
    source = original.data
    bpy.context.scene.collection.objects.link(original)
    try:
        bpy.context.view_layer.update()
        donor = original.evaluated_get(bpy.context.evaluated_depsgraph_get())
        basis = section_bounds(donor,levels)
    finally:
        bpy.data.objects.remove(original,do_unlink=True)
        if not source.users:
            bpy.data.meshes.remove(source)
    canonical = section_bounds(body,levels)
    widths = canonical[:,[1,3]]-canonical[:,[0,2]]
    basis_widths = basis[:,[1,3]]-basis[:,[0,2]]
    # Limit the change at the low pole, neckline and the belly's widest section.
    # Interpolating the measured sections keeps the upper shoulder round.
    blend = np.interp(levels,[.01,.06,.13,.27,.36,.46,.57,.64,.68,.70],
                      [0.,.36,.42,.28,.24,.30,.42,.42,.22,0.])
    gain = 1 + blend[:,None] * np.clip(basis_widths/widths-1.,-.05,.07)
    center = .5*(canonical[:,[0,2]]+canonical[:,[1,3]])
    to_world = body.matrix_world
    to_local = to_world.inverted()
    for v in body.data.vertices:
        before = to_world @ v.co
        xy = np.asarray(before[:2])
        mid = np.array([np.interp(before.z,levels,col) for col in center.T])
        scale = np.array([np.interp(before.z,levels,col) for col in gain.T])
        x,y = mid+(xy-mid)*scale
        v.co = to_local @ Vector((x,y,before.z))
    body.data.update()
