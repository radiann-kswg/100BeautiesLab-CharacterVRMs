"""Pack the individual model's color maps into the reference two-page RGBA layout."""
from collections import defaultdict

import bpy
import numpy as np


def repeat_sample(image, u, v):
    """Bilinear sampling with the source VRM's repeat addressing, including UV seams."""
    width, height = image.size
    pixels = np.empty(width * height * 4, np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)
    x, y = u * width - .5, v * height - .5
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - ix)[None, :, None], (y - iy)[:, None, None]
    left, right = ix % width, (ix + 1) % width
    bottom, top = (iy % height)[:, None], ((iy + 1) % height)[:, None]
    return ((1 - fy) * ((1 - fx) * pixels[bottom, left] + fx * pixels[bottom, right])
            + fy * ((1 - fx) * pixels[top, left] + fx * pixels[top, right]))


def pack_character_atlas(number, meshes, face):
    size, pad = 1024, 4
    main = face.data.materials[0].vrm_addon_extension.mtoon1.pbr_metallic_roughness.base_color_texture.index.source
    groups = defaultdict(list)
    materials = defaultdict(set)
    for obj in meshes:
        mesh = obj.data
        layer = next((layer for layer in mesh.uv_layers if layer.active_render), None)
        for poly in mesh.polygons:
            mat = mesh.materials[poly.material_index]
            image = mat.vrm_addon_extension.mtoon1.pbr_metallic_roughness.base_color_texture.index.source
            if image and image != main:
                if layer is None:
                    raise ValueError(f"Missing texture coordinates on {obj.name}")
                groups[image].extend(layer.data[i] for i in poly.loop_indices)
                materials[image].add(mat)
    if not 1 <= len(groups) <= 6 or tuple(main.size) != (size, size):
        raise ValueError(f"Unexpected texture layout on Corefolder-{number}")

    # Keep the reference face's UVs, expression islands and alpha at native resolution.
    main.name = f"CoreFolder-{number}.png"
    page = bpy.data.images.new(f"CoreFolder-{number}-2.png", size, size, alpha=True)
    page.colorspace_settings.name = main.colorspace_settings.name
    canvas = np.zeros((size, size, 4), np.float32)
    rows = (len(groups) + 1) // 2
    for index, image in enumerate(sorted(groups, key=lambda im: im.name)):
        loops = groups[image]
        uv = np.array([loop.uv[:] for loop in loops])
        low, high = uv.min(axis=0), uv.max(axis=0)
        if np.any(high <= low):
            raise ValueError(f"Empty UV extent for {image.name}")
        col, row = index % 2, index // 2
        start = np.array([col * (size // 2), row * size // rows])
        end = np.array([(col + 1) * (size // 2), (row + 1) * size // rows])
        span = end - start - 2 * pad
        # Bake the used UV range, including repeats. Extend it through the cell
        # margin so a bilinear lookup on its boundary sees the original neighbor.
        u, v = [low[k] + (np.arange(end[k] - start[k]) - pad + .5)
                * (high[k] - low[k]) / span[k] for k in (0, 1)]
        canvas[start[1]:end[1], start[0]:end[0]] = repeat_sample(image, u, v)
        adjusted = (start + pad + (uv - low) / (high - low) * span) / size
        for loop, coord in zip(loops, adjusted):
            loop.uv = coord
        for mat in materials[image]:
            ext = mat.vrm_addon_extension.mtoon1
            shade = ext.extensions.vrmc_materials_mtoon.shade_multiply_texture.index
            if shade.source and shade.source != image:
                raise ValueError(f"Independent shade map on {mat.name} requires its own UV layout")
            if shade.source:
                shade.source = page
            ext.pbr_metallic_roughness.base_color_texture.index.source = page
    page.pixels.foreach_set(canvas.ravel())
    page.update()
    page.pack()
    return main, page
