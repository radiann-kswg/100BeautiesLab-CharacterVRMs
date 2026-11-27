"""Photograph a VRM copy in the official pose-1 viewing direction for fit checks."""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"Corefolder-Training"))
from render_corefolder_comparison import load_model


def render():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vrm",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--yaw",type=float,default=6)
    parser.add_argument("--elevation",type=float,default=2.5)
    parser.add_argument("--neutral",action="store_true")
    parser.add_argument("--rear-tails",action="store_true")
    parser.add_argument("--head",action="store_true",help="Frame the face for iris and expression inspection")
    parser.add_argument("--gaze",type=float,default=0,help="Rotate both humanoid eye bones in degrees")
    p=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    bpy.ops.wm.read_homefile(use_empty=True)
    scene=bpy.context.scene
    model,_,_,_=load_model(p.vrm.resolve(),"Mui",accept_candidate_license=True)
    arm=next(o for o in model.objects if o.type=="ARMATURE")
    def rotate(name,rotations):
        bone=arm.pose.bones.get(name)
        if bone is None:return
        pivot=bone.head.copy()
        mat=Matrix.Identity(4)
        for axis,degrees in rotations:mat=mat@Matrix.Rotation(math.radians(degrees),4,axis)
        bone.matrix=Matrix.Translation(pivot)@mat@Matrix.Translation(-pivot)@bone.matrix
        bpy.context.view_layer.update()
    if not (p.neutral or p.rear_tails):
        rotate("head",[('Y',8),('Z',6)])
        for sign,side in ((1,"L"),(-1,"R")):
            rotate("MuiTailUpper"+side+"_01",[('X',-18),('Z',-sign*7)])
            rotate("MuiTailMiddle"+side+"_01",[('Z',-sign*23),('Y',-sign*5)])
            rotate("MuiTailLower"+side+"_01",[('Z',-sign*25)])
            rotate("MuiTailLower"+side+"_03",[('Y',-sign*23)])
    if p.rear_tails:
        for o in model.objects:
            if o.type=="MESH":o.hide_render="tail" not in o.name.lower()
    if p.gaze:
        slots=arm.data.vrm_addon_extension.vrm0.humanoid.human_bones
        for slot in slots:
            if slot.bone in {'leftEye','rightEye'}:
                rotate(slot.node.bone_name,[('Z',p.gaze)])
    inst=bpy.data.objects.new("Displayed character",None)
    scene.collection.objects.link(inst)
    inst.instance_type='COLLECTION'
    inst.instance_collection=model
    inst.rotation_euler.z=math.radians(180 if p.rear_tails else p.yaw)
    cam=bpy.data.objects.new("Camera",bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(cam)
    scene.camera=cam
    cam.data.type='ORTHO'
    cam.data.ortho_scale=.70 if p.head else 1.60
    target=Vector((0,-.15,.837)) if p.head else Vector((0,.030,.55))
    theta=math.radians(0 if p.rear_tails else p.elevation)
    cam.location=target+Vector((0,-15*math.cos(theta),15*math.sin(theta)))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    sun=bpy.data.objects.new("Key",bpy.data.lights.new("Key",'SUN'))
    scene.collection.objects.link(sun)
    sun.rotation_euler=Vector((.35,1,-.60)).to_track_quat('-Z','Y').to_euler()
    sun.data.energy=2
    scene.world=bpy.data.worlds.new("World")
    scene.render.engine='BLENDER_EEVEE'
    scene.eevee.taa_render_samples=6
    scene.eevee.use_shadows=False
    scene.view_settings.view_transform='Standard'
    scene.render.film_transparent=True
    scene.render.resolution_x=720
    scene.render.resolution_y=720
    scene.render.resolution_percentage=100
    scene.render.image_settings.color_mode="RGBA"
    scene.render.filepath=str(p.out.resolve())
    bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    render()
