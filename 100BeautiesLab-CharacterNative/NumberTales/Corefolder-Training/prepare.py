"""6体のVRMを、画像条件付き3D追加訓練用の点群・GLBへ変換する。
Blenderの別プロセスで実行。元VRM・blendは保存しない。
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
IDS = (4, 16, 20, 22, 25, 93)


def read_vrm(path):
    data = path.read_bytes()
    magic, version, total, length, kind = struct.unpack_from("<5I", data)
    if (magic, version, total, kind) != (0x46546C67, 2, len(data), 0x4E4F534A):
        raise ValueError(f"Invalid GLB: {path}")
    return json.loads(data[20:20 + length]), hashlib.sha256(data).hexdigest()


def prepare(number, out):
    source, = (ROOT / f"Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{number}").glob("*.vrm")
    gltf, sha = read_vrm(source)
    dest = out / f"Corefolder-{number}"
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / "provenance.json").exists():
        raise FileExistsError(f"Completed dataset exists: {dest}")
    # 空の別プロセスのシーンだけを初期化する。
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # 原作者による6体の追加訓練依頼（2026-09-09）に基づく読み込み承認。
    # 元ファイルのMetaは書き換えずprovenanceへ保存する。
    bpy.ops.wm.vrm_license_warning(filepath=str(source), import_anyway=True,
                             extract_textures_into_folder=False, enable_mtoon_outline_preview=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise ValueError("VRM contains no mesh")
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    tris, uvtris, matids, materials = [], [], [], []
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            offset = len(materials)
            materials.extend(list(mesh.materials))
            for tri in mesh.loop_triangles:
                tris.append([list(obj.matrix_world @ mesh.vertices[i].co) for i in tri.vertices])
                uvtris.append([list(mesh.uv_layers.active.data[i].uv) for i in tri.loops])
                matids.append(offset + tri.material_index)
        finally:
            evaluated.to_mesh_clear()
    tris, uvtris, matids = np.array(tris), np.array(uvtris), np.array(matids)
    lo, hi = tris.min(axis=(0, 1)), tris.max(axis=(0, 1))
    center, scale = (lo + hi) / 2, float(max(hi - lo))
    if scale <= 0:
        raise ValueError("Degenerate model")
    areas = np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    rng = np.random.default_rng(number)
    chosen = rng.choice(len(tris), size=32768, p=areas / areas.sum())
    ab = rng.random((len(chosen), 2))
    ab[ab.sum(axis=1) > 1] = 1 - ab[ab.sum(axis=1) > 1]
    weights = np.column_stack((1 - ab.sum(axis=1), ab))
    coords = (np.einsum("ni,nij->nj", weights, tris[chosen]) - center) / scale
    uvs = np.einsum("ni,nij->nj", weights, uvtris[chosen])
    colors = np.empty((len(coords), 3), dtype=np.float32)
    for i, mat in enumerate(materials):
        mask = matids[chosen] == i
        if not mask.any():
            continue
        pbr = mat.vrm_addon_extension.mtoon1.pbr_metallic_roughness
        image = pbr.base_color_texture.index.source
        factor = np.array(pbr.base_color_factor[:3])
        if image is None:
            linear = np.broadcast_to(factor, (int(mask.sum()), 3))
        else:
            pixels = np.array(image.pixels[:], dtype=np.float32).reshape(image.size[1], image.size[0], 4)
            transform = pbr.base_color_texture.extensions.khr_texture_transform
            uv = (uvs[mask] * np.array(transform.scale) + np.array(transform.offset)) % 1
            x = (uv[:, 0] * image.size[0]).astype(int)
            y = (uv[:, 1] * image.size[1]).astype(int)
            sampled = pixels[y, x, :3]
            if image.colorspace_settings.name == "sRGB" and not image.is_float:
                sampled = np.where(sampled <= .04045, sampled / 12.92,
                                   ((sampled + .055) / 1.055) ** 2.4)
            linear = sampled * factor
        # 非float sRGB画像のpixelsは符号化済み。係数は線形色で適用しsRGBへ戻す。
        colors[mask] = np.clip(np.where(linear <= .0031308, linear * 12.92,
                                      1.055 * np.maximum(linear, 0) ** (1 / 2.4) - .055), 0, 1)
    np.savez_compressed(dest / "surface.npz", coords=coords.astype(np.float32), rgb=colors)
    # 学習素材用GLB。骨格・表情の正典はsource VRMに残す。
    bpy.ops.export_scene.gltf(filepath=str(dest / "source.glb"), export_format="GLB",
                              export_animations=False, export_lights=False, export_cameras=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = False
    scene.render.film_transparent = False
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (1, 1, 1)
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    camdata = bpy.data.cameras.new("TrainingCamera")
    camera = bpy.data.objects.new("TrainingCamera", camdata)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camdata.type, camdata.ortho_scale = "ORTHO", scale * 1.22
    views = []
    for i in range(8):
        azimuth = 2 * math.pi * i / 8
        direction = Vector((math.sin(azimuth), -math.cos(azimuth), .12))
        camera.location = Vector(center) + direction * scale * 3
        camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        scene.render.filepath = str(dest / f"view-{i:02}.png")
        bpy.ops.render.render(write_still=True)
        views.append({"file": f"view-{i:02}.png", "azimuth_rad": azimuth,
                      "camera_to_world": [list(row) for row in camera.matrix_world]})
    vrm = gltf["extensions"]["VRM"]
    record = {"id": number, "source": source.relative_to(ROOT).as_posix(), "sha256": sha,
              "vrm_meta": vrm.get("meta"), "humanoid_bones": len(vrm["humanoid"]["humanBones"]),
              "coordinate_system": "Blender Z-up; XYZ normalized to [-0.5,0.5]; RGB sRGB [0,1]",
              "center_m": center.tolist(), "scale_m": scale, "triangles": len(tris),
              "surface_points": len(coords), "views": views}
    (dest / "provenance.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    assert np.isfinite(coords).all() and np.isfinite(colors).all()
    assert np.abs(coords).max() <= .50001 and colors.min() >= 0 and colors.max() <= 1
    assert read_vrm(source)[1] == sha, "Source changed during preparation"
    print("PREPARED", number, len(tris), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "dataset-v1")
    parser.add_argument("--id", type=int, choices=IDS, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if not bpy.app.background:
        raise RuntimeError("Run in a separate background Blender process")
    prepare(args.id, args.out.resolve())

