"""Bend the actual 194-vertex Corefolder basis tail along an individual plume."""
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

BASE = Path(__file__).resolve().parents[2] / "Basis/Corefolder/VRCModel_CoreFloder-Base.blend"


def load_tail():
    with bpy.data.libraries.load(str(BASE), link=False) as (_, data):
        data.objects = ["tail"]
    donor, = data.objects
    mesh = donor.data
    xyz = np.array([donor.matrix_world @ v.co for v in mesh.vertices])
    if len(xyz) != 194 or len(mesh.polygons) != 224:
        raise ValueError("Expected the original 194-point Corefolder basis tail")
    adj = [set() for _ in xyz]
    for e in mesh.edges:
        a, b = e.vertices
        adj[a].add(b)
        adj[b].add(a)
    # Poles of the source mesh; the maximum-height pole is the curled tip.
    ring, seen, bands = {9}, set(), []
    while ring:
        bands.append(sorted(ring))
        seen.update(ring)
        ring = set.union(*(adj[i] for i in ring))-seen
    if len(seen) != 194 or bands[-1] != [int(np.argmax(xyz[:, 2]))]:
        raise ValueError("Unexpected basis tail connectivity")
    centers = np.array([xyz[g].mean(axis=0) for g in bands])
    lengths = np.r_[0., np.linalg.norm(np.diff(centers, axis=0), axis=1).cumsum()]
    lengths /= lengths[-1]
    profiles = []
    across_yz = np.array([0., 1.])
    for ids, center, distance in zip(bands, centers, lengths):
        local = xyz[ids]-center
        if len(ids) > 1:
            _, _, axes = np.linalg.svd(local[:, 1:], full_matrices=False)
            axis = axes[0]
            if axis @ across_yz < 0: axis = -axis
            across_yz = axis
        profiles.append((ids, float(distance), local[:, 0], local[:, 1:]@across_yz))
    radius = max(np.max(abs(band[2])) for band in profiles)
    polygons = [p.vertices[:] for p in mesh.polygons]
    bpy.data.objects.remove(donor, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    return profiles, radius, polygons


def unit(v):
    return v / max(np.linalg.norm(v), 1.e-10)


def fork_tip(source, xyz, faces, tip_a, tip_b):
    """Split one distal section into two closed tufts with a shared saddle."""
    profiles = source[0]
    keep = {i for band in profiles[:9] for i in band[0]}
    rim = set(profiles[8][0])
    kept_faces = [f for f in faces if keep.issuperset(f)]
    neighbors = {i: set() for i in rim}
    for f in kept_faces:
        for a, b in zip(f, (*f[1:], f[0])):
            if a in rim and b in rim:
                neighbors[a].add(b)
                neighbors[b].add(a)
    order = [min(rim)]
    while len(order) < len(rim):
        order.append(min(neighbors[order[-1]] - set(order)))
    ring_center = xyz[order].mean(axis=0)
    split_axis = unit(tip_a - tip_b)
    midpoint = len(order) // 2
    cut = min(range(midpoint), key=lambda j:
              abs((xyz[order[j]]-xyz[order[j+midpoint]]) @ split_axis))
    order = order[cut:]+order[:cut]
    paths = [order[:midpoint+1], order[midpoint:]+order[:1]]
    paths.sort(key=lambda half: (xyz[half].mean(axis=0)-ring_center) @ split_axis, reverse=True)
    ids = sorted(keep)
    points = list(xyz[ids])
    remap = {i:j for j,i in enumerate(ids)}
    faces = [[remap[i] for i in f] for f in kept_faces]
    position = {i:s for band,s,*_ in profiles for i in band}
    distances = [position[i] for i in ids]
    start = profiles[8][1]

    def vertex(p, s):
        points.append(p)
        distances.append(s)
        return len(points)-1

    # Both tuft openings share this cross-rim edge, making a single manifold.
    seam = vertex(ring_center + .60 * ((tip_a+tip_b)*.5-ring_center), start)
    for half, tip, sign in zip(paths, (tip_a, tip_b), (1, -1)):
        previous = [remap[i] for i in half] + [seam]
        opening = np.array([points[i] for i in previous])
        origin = opening.mean(axis=0)
        relative = opening-origin
        outward = split_axis * sign
        # The edges bow out before curling back toward each painted tip.
        for t, width in ((.19,.99),(.42,.84),(.65,.57),(.83,.29),(.94,.12)):
            bow = 4*t*(1-t)
            center = origin*(1-t) + tip*t + bow*(outward*.018 + np.array([0,.036,0]))
            ring = [vertex(center+d*width, start+(1-start)*t) for d in relative]
            for j in range(len(ring)):
                k = (j+1) % len(ring)
                faces.append((previous[j],previous[k],ring[k],ring[j]))
            previous = ring
        end = vertex(tip, 1.)
        faces.extend((previous[j-1],i,end) for j,i in enumerate(previous))
    return np.array(points), faces, np.array(distances)


def make_plume(source, root, bulb, tip, radius, depth, curve):
    """Keep the source ring sequence, round sections, taper and connectivity."""
    profiles, donor_radius, polygons = source
    root, bulb, tip = map(np.asarray, (root, bulb, tip))
    # The two Bézier spans meet with the same derivative at the broad section.
    # The rearward bow makes a three-dimensional plume even when projected tips overlap.
    bend = np.array([0.,curve,0.])
    tangent = (tip-root)*.21
    controls = [[root,root+(bulb-root)*.35+bend*.28,bulb-tangent,bulb],
                [bulb,bulb+tangent,tip-(tip-bulb)*.30+bend*.55,tip]]
    def frame(s):
        k = 0 if s < .49 else 1
        u = s/.49 if k==0 else (s-.49)/.51
        a,b,c,d = controls[k]
        v = 1-u
        center = v**3*a+3*v*v*u*b+3*v*u*u*c+u**3*d
        forward = unit(v*v*(b-a)+2*v*u*(c-b)+u*u*(d-c))
        return center, forward

    # A transverse axis orthogonal to the projected overall direction supplies
    # a stable frame, including places where the tangent points at the back camera.
    screen_axis = unit(np.array([tip[2]-root[2],0.,root[0]-tip[0]]))
    xyz = np.empty((194,3))
    guides=[]
    for ids, s, across, normal in profiles:
        center, forward = frame(s)
        side = unit(screen_axis-forward*float(screen_axis @ forward))
        height = unit(np.cross(forward,side))
        offsets = across[:,None]*side*(radius/donor_radius)+normal[:,None]*height*(depth/donor_radius)
        ring = center+offsets
        # Lift a whole low section without pressing the underside into a flat cap.
        lift = max(0., .008-ring[:,2].min())
        ring[:,2] += lift
        xyz[ids] = ring
        guides.append(Vector((center[0],center[1],center[2]+lift)))
    return xyz, polygons, [guides[i] for i in (0,4,7,10,14)]
