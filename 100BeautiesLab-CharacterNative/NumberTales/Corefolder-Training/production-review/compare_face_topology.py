"""Project editable face meshes and highlight the vertices moved by two actual shape keys.

Run with Python, NumPy and Pillow: python compare_face_topology.py --blender <executable>.
The extractor runs inside Blender. No input .blend is saved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import numpy as np

HERE = Path(__file__).resolve().parent
NUMBERS = (4, 16, 20, 22, 25, 93, 6, 49, 57, 85)
UPPER_LIP = {4: 370, 16: 173, 20: 179, 22: 495, 25: 158, 93: 325}


def measurements(face, xyz, edges, lip):
    armature = face.find_armature()
    slots = {b.bone: b.node.bone_name for b in armature.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    eye_centers = []
    for slot in ("leftEye", "rightEye"):
        index = face.vertex_groups[slots[slot]].index
        ids = [v.index for v in face.data.vertices if any(g.group == index and g.weight > .45 for g in v.groups)]
        if not ids:
            raise ValueError(f"Missing weighted eye in {slot}")
        # Midpoint of the actual skinned eye's horizontal extent.
        eye_centers.append((xyz[ids, 0].min() + xyz[ids, 0].max()) / 2)
    # Weld coincident seams for finding the continuous front cheek sheet.
    _, merged = np.unique(np.round(xyz, 5), axis=0, return_inverse=True)
    graph = [set() for _ in range(merged.max()+1)]
    for a, b in merged[edges]:
        graph[a].add(b)
        graph[b].add(a)
    # The forward-most vertex in the narrow nose band sits on the outer face.
    band = np.flatnonzero((abs(xyz[:, 0]-lip[0]) < .035) & (abs(xyz[:, 2]-lip[2]-.045) < .027))
    # Some references have a separate nose mark in front of the skin.
    examined = set()
    for vertex in band[np.argsort(xyz[band, 1])]:
        seed = merged[vertex]
        if seed in examined:
            continue
        visited, queue = {seed}, [seed]
        while queue:
            new = graph[queue.pop()] - visited
            visited.update(new)
            queue.extend(new)
        examined.update(visited)
        patch = xyz[np.isin(merged, list(visited))]
        if np.ptp(patch[:, 0]) > .25 and np.ptp(patch[:, 2]) > .1:
            break
    else:
        raise ValueError("Missing continuous cheek surface")
    chosen = edges[np.isin(merged[edges[:, 0]], list(visited))]
    a, b = xyz[chosen[:, 0]], xyz[chosen[:, 1]]
    level = lip[2]+.018
    hit = ((a[:, 2] > level) != (b[:, 2] > level))
    a, b = a[hit], b[hit]
    section = a + (b-a)*((level-a[:, 2])/(b[:, 2]-a[:, 2]))[:, None]
    section = section[section[:, 1] < lip[1]+.175]
    width = float(np.ptp(section[:, 0]))
    if width < .25:
        raise ValueError(f"Cheek section is incomplete: {width}")
    spacing = float(abs(eye_centers[1]-eye_centers[0]))
    return dict(cheekWidthMM=width*1000, eyeSpacingMM=spacing*1000, eyeSpacingOverCheekWidth=spacing/width)


def extract(directory):
    import bpy

    for number in NUMBERS:
        model = HERE.parent.parent / f"Corefolder-{number}"
        if number in UPPER_LIP:
            source, = model.glob("VRCModel*.blend")
        else:
            source = model / "Modeling" / f"Corefolder-{number}.blend"
        bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
        face, = [o for o in bpy.context.scene.objects if o.type == "MESH" and
                 o.name.lower().startswith("face") and o.data.shape_keys]
        keys = face.data.shape_keys.key_blocks

        def position(name):
            return np.array([face.matrix_world @ v.co for v in keys[name].data])

        basis = position("Basis")
        edges = np.array([edge.vertices[:] for edge in face.data.edges])
        lip = basis[UPPER_LIP.get(number, 370)]
        report = measurements(face, basis, edges, lip)
        report["nativeSHA256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        (directory/f"{number}.json").write_text(json.dumps(report), encoding="utf8")
        np.savez(directory / f"{number}.npz", basis=basis, center=lip,
                 blink=np.linalg.norm(position("EyeClose") - basis, axis=1),
                 vowel=np.linalg.norm(position("a") - basis, axis=1),
                 edges=edges)


def draw(directory, output):
    from PIL import Image, ImageDraw, ImageFont

    tile, height, factor = 244, 223, 2
    board = Image.new("RGB", (6 * tile, 2 * height + 63), "#f4f5f5")
    label = ImageFont.truetype("segoeui.ttf", 18)
    caption = ImageFont.truetype("segoeui.ttf", 15)
    ink = ["#bfc6ca", "#13758a", "#b24f23"]
    for index, number in enumerate(NUMBERS):
        with np.load(directory / f"{number}.npz") as raw:
            xyz, center, edges = raw["basis"], raw["center"], raw["edges"]
            blink, vowel = raw["blink"], raw["vowel"]
        # Use one common scale. Anchor at the upper lip so faces can be compared
        # across different rigs and world origins; retain original mesh edges.
        scale = tile / .54
        points = np.column_stack((tile / 2 + (xyz[:, 0]-center[0]) * scale,
                                  145 - (xyz[:, 2]-center[2]) * scale)) * factor
        visible = (xyz[edges, 1] < center[1]+.22).all(axis=1)
        edges = edges[visible]
        groups = np.zeros(len(edges), dtype=int)
        groups[blink[edges].min(axis=1) > .002] = 1
        groups[vowel[edges].min(axis=1) > .002] = 2
        panel = Image.new("RGB", (tile*factor, (height-27)*factor), "white")
        pen = ImageDraw.Draw(panel)
        for group, color in enumerate(ink):
            for a, b in edges[groups == group]:
                pen.line((tuple(points[a]), tuple(points[b])), fill=color, width=1 if group==0 else 2)
        x, y = (index % 6)*tile, (index // 6)*height
        board.paste(panel.resize((tile-2, height-27), Image.Resampling.LANCZOS), (x, y+27))
        ImageDraw.Draw(board).text((x+8, y+3), f"#{number}", fill="#283138", font=label)
    pen = ImageDraw.Draw(board)
    for j, text in enumerate(("Rest edges", "Blink", "Aa (lips and interior)")):
        x = 20 + j * 245
        pen.line((x, 2*height+19, x+35, 2*height+19), fill=ink[j], width=3)
        pen.text((x+44, 2*height+7), text, fill="#283138", font=label)
    pen.text((20, 2*height+36), "Front projection at one world scale. Color requires both endpoints to move over 2 mm. Inner surfaces are visible.",
             fill="#384a54", font=caption)
    board.save(output)
    metrics = {n: json.loads((directory/f"{n}.json").read_text()) for n in NUMBERS}
    output.with_suffix(".json").write_text(json.dumps({
        "method": "Frontal world-space section of the continuous outer cheek, 18 mm above the neutral upper lip. "
                  "Weld coincident seams and omit surface behind 175 mm depth relative to the lip. "
                  "Eye spacing uses horizontal extent midpoints of each eye skin (bone influence > 0.45).",
        "models": metrics}, indent=2)+"\n", encoding="utf8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender")
    parser.add_argument("--extract", type=Path)
    parser.add_argument("--out", type=Path, default=HERE/"face-topology.png")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else None)
    if args.extract:
        extract(args.extract)
        return
    if not args.blender:
        parser.error("--blender is required")
    with TemporaryDirectory() as folder:
        subprocess.run([args.blender, "-b", "--offline-mode", "--disable-autoexec", "--python-exit-code", "1",
                        "-P", str(Path(__file__).resolve()), "--", "--extract", folder], check=True)
        draw(Path(folder), args.out)


if __name__ == "__main__":
    main()
