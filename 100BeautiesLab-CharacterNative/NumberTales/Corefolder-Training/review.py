"""保存済み試験点群をBlenderで比較する。既存モデルの上書きはしない。"""
import argparse
from pathlib import Path
import sys
import bpy
import numpy as np

def point_object(path, name):
    data = np.load(path)
    xyz = data["coords"]
    rgb = np.stack([data[c] for c in "RGB"], axis=1)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(xyz.tolist(), [], [])
    attr = mesh.color_attributes.new(name="point_color", type="FLOAT_COLOR", domain="POINT")
    for value, color in zip(attr.data, rgb):
        value.color_srgb = (*np.clip(color, 0, 1), 1)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new(name + "_colors")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    attribute = mat.node_tree.nodes.new("ShaderNodeAttribute")
    attribute.attribute_name = "point_color"
    shader = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    mat.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    mat.node_tree.links.new(attribute.outputs["Color"], shader.inputs["Base Color"])
    modifier = obj.modifiers.new("Point display", "NODES")
    group = bpy.data.node_groups.new(name + "_display", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    modifier.node_group = group
    nodes, links = group.nodes, group.links
    inp, out = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    sphere = nodes.new("GeometryNodeMeshIcoSphere")
    sphere.inputs["Radius"].default_value = .007
    sphere.inputs["Subdivisions"].default_value = 1
    instance, realize = nodes.new("GeometryNodeInstanceOnPoints"), nodes.new("GeometryNodeRealizeInstances")
    material = nodes.new("GeometryNodeSetMaterial")
    material.inputs["Material"].default_value = mat
    links.new(inp.outputs["Geometry"], instance.inputs["Points"])
    links.new(sphere.outputs["Mesh"], instance.inputs["Instance"])
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
    links.new(realize.outputs["Geometry"], material.inputs["Geometry"])
    links.new(material.outputs["Geometry"], out.inputs["Geometry"])
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if not bpy.app.background:
        raise RuntimeError("Use a separate Blender process")
    run = args.run.resolve()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for i, name in enumerate(("before", "after")):
        obj = point_object(run / (name + ".npz"), name)
        obj.location.x = (i - .5) * 1.3
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.shading.type = "MATERIAL"
            area.spaces.active.region_3d.view_distance = 3.5
    bpy.ops.wm.save_as_mainfile(filepath=str(run / "comparison.blend"))



if __name__ == "__main__":
    main()
