"""Select actual VRM triangles for clothing-off and underlying head-and-torso inspections."""
import numpy as np

GROUPS = ("undressed", "bare-torso", "cranial-base")


def island_faces(mesh, points):
    """Weld split normal/UV vertices for membership only. Return original polygon indices."""
    _, weld = np.unique(np.round(points, 5), axis=0, return_inverse=True)
    parent = list(range(len(set(weld))))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for edge in mesh.edges:
        a, b = weld[list(edge.vertices)]
        parent[root(a)] = root(b)
    groups = {}
    for poly in mesh.polygons:
        groups.setdefault(root(weld[poly.vertices[0]]), []).append(poly.index)
    return groups.values()


def uv_patches(mesh, faces, points):
    """Identify the cap sewn into #16's hair at coincident geometric boundaries."""
    uv = mesh.uv_layers.active.data
    neighbors = {}
    for f in faces:
        for loop in f.loop_indices:
            key = (*np.round(points[mesh.loops[loop].vertex_index],5), *np.round(uv[loop].uv,5))
            neighbors.setdefault(key, []).append(f.index)
    linked = {f.index:set() for f in faces}
    for shared in neighbors.values():
        for index in shared:
            linked[index].update(shared)
    while linked:
        start = next(iter(linked))
        stack, found = [start], set()
        while stack:
            index = stack.pop()
            if index not in found:
                found.add(index)
                stack.extend(linked.pop(index))
        yield sorted(found)


def classify(label, node, tris, materials, width, depth, floor, height):
    base = label == "Base"
    node = node.split(".")[0].lower()
    cranial = any(m.startswith("Corefolder Cranial Base") for m in materials)
    if cranial or (base and node == "head"):
        return (GROUPS[0], GROUPS[2]), "cranial skin"
    if node == "body":
        if floor < .06 and .52 < height < .84 and min(width, depth) > .55:
            return GROUPS, "torso skin"
        return (), "attached accessory outside the actual torso island"
    if node in ("outfit", "tail"):
        return (), node
    if node == "face":
        # The canonical assets use one atlas for skin, hair and clothing. These
        # island counts pertain only to SHA-verified originals in the manifest.
        if label == "93" and tris in (186, 216):
            return (), "detached headband and ties"
        if label == "22" and tris == 116:
            return (), "small spherical ear decoration"
        if (label == "20" and tris == 568) or (label == "25" and tris == 330):
            return (GROUPS[0],), "separable lock"
        return (GROUPS[0], GROUPS[2]), "face or integrated cranium/ear"
    if node == "hair":
        if label == "16" and tris == 90:
            return (), "detachable blue cap ear"
        if label == "4" and tris == 912:
            return (GROUPS[0], GROUPS[2]), "the canonical rear skull is continuous with this head covering"
        return (GROUPS[0],), "hair, ears or cheek fur"
    return (), "unclassified"


def select(label, obj, mesh, points):
    subsets = {group: [] for group in GROUPS}
    notes, torso_bounds = [], None
    for polygons in island_faces(mesh, points):
        faces = [mesh.polygons[i] for i in polygons]
        verts = np.unique([i for face in faces for i in face.vertices])
        p = points[verts]
        lo, hi = p.min(0), p.max(0)
        mats = {m.name for i in {f.material_index for f in faces}
                if i < len(mesh.materials) and (m := mesh.materials[i]) is not None}
        tris = sum(len(f.vertices) - 2 for f in faces)
        width, depth, height = hi-lo
        if label == "16" and obj.name.startswith("Hair") and tris == 1210:
            # These islands sample the blue cap, grey underside and printed
            # badge in #16's original atlas. Retain even the short rear ponytail.
            removed = []
            for patch in uv_patches(mesh, faces, points):
                cap = len(patch) in (12, 50, 498)
                if cap:
                    removed.extend(patch)
                for name in (() if cap else (GROUPS[0], GROUPS[2])):
                    subsets[name].extend(patch)
                notes.append({"triangles":len(patch), "materials":sorted(mats),
                    "include":() if cap else (GROUPS[0],GROUPS[2]),
                    "part":"cap surface" if cap else "hair of the canonical head"})
            if len(removed) != 560:
                raise ValueError(f"Unexpected cap topology in #16: {len(removed)}")
            continue
        group_names, reason = classify(label, obj.name, tris, mats, width, depth, lo[2], height)
        if reason == "unclassified":
            raise ValueError(f"Inspect unexpected renderer {obj.name} in {label}")
        if reason == "torso skin":
            if torso_bounds is not None:
                raise ValueError(f"Ambiguous torso skin in {label}/{obj.name}")
            torso_bounds = (lo, hi)
        for group in group_names:
            subsets[group].extend(polygons)
        notes.append({"triangles":tris, "materials":sorted(mats), "include":group_names, "part":reason})
    return subsets, notes, torso_bounds


def extract(mesh, indices):
    """Copy evaluated positions and original per-corner normals without altering shared source data."""
    import bpy
    faces = [mesh.polygons[i] for i in indices]
    vertices = sorted({j for f in faces for j in f.vertices})
    remap = {j: k for k, j in enumerate(vertices)}
    subset = bpy.data.meshes.new("Clay part")
    subset.from_pydata([mesh.vertices[i].co for i in vertices], [],
                       [[remap[j] for j in f.vertices] for f in faces])
    for original, copy in zip(faces, subset.polygons):
        copy.use_smooth = original.use_smooth
    normals = [mesh.corner_normals[i].vector for f in faces for i in f.loop_indices]
    subset.normals_split_custom_set(normals)
    return subset
