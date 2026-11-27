"""Fit the common body to the real #4 torso and extend its neutral facial surface."""
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector, kdtree

HERE = Path(__file__).resolve().parent


def reference():
    return json.loads((HERE / "canonical-core-envelope.json").read_text(encoding="utf8"))


def fit_common_torso(body):
    """Copy the positions of the actual reference body while preserving weights and UV topology."""
    points = reference()["body_points"]
    tree = kdtree.KDTree(len(points))
    for i,point in enumerate(points):
        tree.insert(Vector(point),i)
    tree.balance()
    world = body.matrix_world
    local = world.inverted()
    matched = set()
    if len(body.data.vertices) != len(points):
        raise ValueError("Common core torso topology has changed")
    for vertex in body.data.vertices:
        point,index,distance = tree.find(world @ vertex.co)
        if distance>.006 or index in matched:
            raise ValueError(f"Ambiguous common torso point {vertex.index}: {distance}")
        matched.add(index)
        vertex.co = local @ point
    body.data.update()


def add_cranial_base(arm,face,number,collection):
    from modeling_draft import bind
    from refine_models import toon

    info = reference()
    rows = np.asarray(info["head_rows"],dtype=float)
    first = np.asarray([face.matrix_world @ face.data.vertices[i].co for i in info["rim"]])
    if np.max(abs(first-rows[0])) > .0003:
        raise ValueError("Canonical face boundary does not match the reference")
    rows[0] = first
    points = rows.reshape(-1,3).tolist()+[info["head_pole"]]
    count = rows.shape[1]
    faces = []
    for row in range(len(rows)-1):
        for j in range(count):
            i = row*count+j
            k = row*count+(j+1)%count
            faces.append((i,k,k+count,i+count))
    last = (len(rows)-1)*count
    faces.extend((last+j,last+(j+1)%count,len(points)-1) for j in range(count))
    mesh = bpy.data.meshes.new("Canonical posterior cranium")
    mesh.from_pydata(points,[],faces)
    mesh.update()
    # The patch remains open at the 34 vertices shared with the expression face.
    center = Vector((0.,-.09,.81))
    if np.median([p.normal.dot(p.center-center) for p in mesh.polygons]) < 0:
        mesh.flip_normals()
    obj = bpy.data.objects.new("Corefolder Cranial Base",mesh)
    collection.objects.link(obj)
    fur = {6:"#FF76A2",49:"#6AA6D7",57:"#FFEE62",85:"#C48455"}[number]
    mat = toon(f"Corefolder Cranial Base #{number}",fur,0)
    mesh.materials.append(mat)
    uv = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        poly.use_smooth = True
        for loop in poly.loop_indices:
            idx = mesh.loops[loop].vertex_index
            uv.data[loop].uv = ((idx%count)/count, min(1.,(idx//count)/len(rows)))
    obj["corefolder_layer"] = "Base"
    obj["corefolder_sources"] = "VRM #4 facial boundary and torso; #4, #25, #93 posterior envelope"
    bind(obj,arm,"head")
    return obj
