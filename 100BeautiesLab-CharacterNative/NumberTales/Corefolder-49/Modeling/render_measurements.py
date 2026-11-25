"""Orthographic VRM angle sweep for the #49 artwork comparison (Blender background)."""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'Corefolder-Training'))
from render_corefolder_comparison import load_model


def render(model, output, angles):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene=bpy.context.scene
    collection,center,dimensions,_=load_model(model.resolve(),model.stem,accept_candidate_license=True)
    cell=max(1.47,dimensions.z*720/610*1.07)
    for i,angle in enumerate(angles):
        obj=bpy.data.objects.new('yaw '+str(angle),None)
        scene.collection.objects.link(obj)
        obj.instance_type='COLLECTION'
        obj.instance_collection=collection
        obj.rotation_euler.z=math.radians(angle)
        obj.location=Vector(((i-(len(angles)-1)/2)*cell,0,0))-obj.rotation_euler.to_matrix()@center
    camera=bpy.data.objects.new('measure',bpy.data.cameras.new('measure'))
    scene.collection.objects.link(camera)
    scene.camera=camera
    camera.data.type='ORTHO'
    camera.data.sensor_fit='HORIZONTAL'
    camera.data.ortho_scale=cell*len(angles)
    camera.location=(0,-15,0)
    camera.rotation_euler.x=math.pi/2
    sun=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN'))
    scene.collection.objects.link(sun)
    sun.rotation_euler=Vector((.35,1,-.6)).to_track_quat('-Z','Y').to_euler()
    sun.data.energy=2
    scene.world=bpy.data.worlds.new('gray')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.14,.14,.14,1)
    scene.render.film_transparent=True
    scene.render.engine='BLENDER_EEVEE'
    scene.eevee.taa_render_samples=8
    scene.eevee.use_shadows=False
    scene.view_settings.view_transform='Standard'
    scene.render.resolution_x=720*len(angles)
    scene.render.resolution_y=610
    scene.render.resolution_percentage=100
    scene.render.image_settings.color_mode='RGBA'
    output.parent.mkdir(parents=True,exist_ok=True)
    scene.render.filepath=str(output.resolve())
    bpy.ops.render.render(write_still=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--angles',nargs='+',type=float,default=[-18,-24,-30,-36])
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    render(args.model,args.output,args.angles)
