"""Compare every oriented, material-assigned triangle of two Corefolder skinned exports."""
import hashlib

import numpy as np
from scipy.spatial import cKDTree


def _skin_matrices(glb, tol):
    nodes = glb.doc["nodes"]
    result = {}
    for skin in glb.doc["skins"]:
        for i, matrix in zip(skin["joints"], glb.array(skin["inverseBindMatrices"])):
            name = nodes[i]["name"]
            if name in result and not np.allclose(result[name], matrix, rtol=0, atol=tol):
                raise ValueError(f"Inconsistent inverse bind matrix for {name}")
            result[name] = matrix
    parents = {child: n["name"] for n in nodes for child in n.get("children", [])}
    rest = {n["name"]: (parents.get(i), {k: n[k] for k in ("translation", "scale", "rotation", "matrix") if k in n})
            for i,n in enumerate(nodes) if n["name"] in result}
    return result, rest


def _materials(glb):
    # VRM's texture slots address glTF indices; material merging can renumber these.
    doc = glb.doc
    result = {}
    for mat in glb.vrm["materialProperties"]:
        bound = {}
        for slot, index in mat["textureProperties"].items():
            texture = doc["textures"][index]
            image = doc["images"][texture["source"]]
            bound[slot] = (hashlib.sha256(glb.buffer(image["bufferView"])).hexdigest(),
                           doc["samplers"][texture["sampler"]] if "sampler" in texture else None)
        result[mat["name"]] = {**mat, "textureProperties": bound}
    return result


def _triangles(glb, bone_index):
    doc = glb.doc
    result = {}
    for node in doc["nodes"]:
        if "mesh" not in node:
            continue
        if any(k in node for k in ("translation", "scale", "rotation", "matrix")):
            raise ValueError(f"Expected baked rest coordinates for {node['name']}")
        joints = np.array([bone_index[doc["nodes"][i]["name"]] for i in doc["skins"][node["skin"]]["joints"]])
        for prim in doc["meshes"][node["mesh"]]["primitives"]:
            idx = prim["material"]
            mat = glb.vrm["materialProperties"][idx]
            attr = prim["attributes"]
            xyz = glb.array(attr["POSITION"])
            uv = glb.array(attr["TEXCOORD_0"]) if mat["textureProperties"] else np.zeros((len(xyz), 2))
            weights = glb.array(attr["WEIGHTS_0"])
            assignments = np.where(weights > 0, joints[glb.array(attr["JOINTS_0"])], -1)
            order = np.argsort(assignments, axis=1)
            components = [xyz, glb.array(attr["NORMAL"]), uv, np.take_along_axis(assignments, order, 1),
                          np.take_along_axis(weights, order, 1)]
            optional = sorted(set(attr) - {"POSITION", "NORMAL", "TEXCOORD_0", "WEIGHTS_0", "JOINTS_0"})
            components.extend(glb.array(attr[key]) for key in optional)
            # Keep shape-key pose and normal offsets attached to the same oriented face corners.
            targets = []
            for target in prim.get("targets", []):
                targets.append(tuple(sorted(target)))
                components.extend(glb.array(target[k]) for k in sorted(target))
            key = mat["name"], tuple(optional), tuple(targets)
            indices = glb.array(prim["indices"]).ravel()
            corners = np.concatenate(components, axis=1)[indices]
            result.setdefault(key, []).append(corners.reshape(-1, 3, corners.shape[1]))
    return {k: np.concatenate(v) for k, v in result.items()}


def compare_triangles(original, grouped, tol=2e-5, normal_degrees=.01):
    binds, rest = _skin_matrices(original, tol)
    grouped_binds, grouped_rest = _skin_matrices(grouped, tol)
    if rest != grouped_rest or binds.keys() != grouped_binds.keys():
        raise ValueError("Rest-pose bone hierarchy differs in grouped export")
    bind_error = max(float(np.abs(m - grouped_binds[k]).max()) for k,m in binds.items())
    if bind_error > tol or _materials(original) != _materials(grouped):
        raise ValueError("Inverse bind matrices, MToon parameters or texture content differ in grouped export")
    names = {d.doc["nodes"][i]["name"] for d in (original, grouped) for s in d.doc["skins"] for i in s["joints"]}
    bone_index = {n: i for i, n in enumerate(sorted(names))}
    before, after = (_triangles(g, bone_index) for g in (original, grouped))
    if before.keys() != after.keys():
        raise ValueError("Materials, UV/skin attributes or morph targets differ in the grouped export")
    total, peak, peak_non_normal, peak_normal_chord = 0, 0.0, 0.0, 0.0
    normal_chord = 2 * np.sin(np.deg2rad(normal_degrees) / 2)
    for key, src in before.items():
        dst = after[key]
        if src.shape != dst.shape:
            raise ValueError(f"Triangle count differs on {key[0]}: {len(src)} / {len(dst)}")
        centroids = dst[:, :, :3].mean(axis=1)
        tree = cKDTree(src[:, :, :3].mean(axis=1))
        _, near = tree.query(centroids)
        def difference(a, b):
            # A different first corner is valid, reversed winding is significant.
            # A baked split-normal direction has units of angle; coordinate, UV,
            # weight and morph data retain the original absolute tolerance.
            readings = []
            for turn in range(3):
                d = abs(a - np.roll(b, turn, axis=1))
                other = np.maximum(d[:,:,:3].max((1,2)),d[:,:,6:].max((1,2)))
                chord = np.linalg.norm(d[:,:,3:6],axis=2).max(1)
                score = np.maximum(other / tol, chord / normal_chord)
                readings.append(np.stack((score, d.max((1,2)), other, chord),axis=1))
            readings = np.stack(readings)
            return readings[np.argmin(readings[:,:,0],axis=0), np.arange(a.shape[0])]
        delta = difference(src[near], dst)
        counts = np.bincount(near, minlength=len(src))
        single = (counts[near] == 1) & (delta[:,0] <= 1)
        used = set(near[single])
        for i in np.flatnonzero(~single):
            matches = [j for j in tree.query_ball_point(centroids[i], tol * 2) if j not in used]
            if not matches:
                raise ValueError(f"No corresponding triangle on {key[0]}, row {i}")
            errors = difference(src[matches], dst[i:i+1])
            best = int(np.argmin(errors[:,0]))
            if errors[best,0] > 1:
                raise ValueError(f"Triangle attributes differ on {key[0]}, row {i}: {errors[best]}")
            delta[i] = errors[best]
            used.add(matches[best])
        total += len(delta)
        peak = max(peak, float(delta[:,1].max()))
        peak_non_normal = max(peak_non_normal,float(delta[:,2].max()))
        peak_normal_chord = max(peak_normal_chord,float(delta[:,3].max()))
    return {"triangles_compared_one_to_one": total, "max_absolute_attribute_delta": peak,
            "material_definitions_and_embedded_textures_match": True, "skin_joints_compared": len(rest),
            "max_inverse_bind_matrix_delta": bind_error,
            "max_non_normal_attribute_delta":peak_non_normal,
            "max_vertex_normal_angle_degrees":float(np.rad2deg(2*np.arcsin(peak_normal_chord/2))),
            "vertex_normal_tolerance_degrees":normal_degrees,
            "absolute_tolerance": tol, "ungrouped_meshes": len(original.doc["meshes"]),
            "exported_meshes": len(grouped.doc["meshes"]),
            "ungrouped_primitives": sum(len(m["primitives"]) for m in original.doc["meshes"]),
            "exported_primitives": sum(len(m["primitives"]) for m in grouped.doc["meshes"])}
