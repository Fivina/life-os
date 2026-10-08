"""Render repeatable close-ups without modifying the saved authored scene."""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOTS = ("SelfCore", "Calendar", "Learning", "Home", "Life", "Fitness", "Scenery")
parser = argparse.ArgumentParser()
parser.add_argument("--target", choices=(*ROOTS[:-1], "all"), default="Fitness")
parser.add_argument("--output-dir", type=Path, default=Path("E:/LifeOS-Art/system"))
parser.add_argument("--samples", type=int, default=32)
parser.add_argument("--hide-light-sources", choices=("none", "transmission", "all"), default="none",
                    help="Diagnostic only: hide light geometry from transmission or all specular rays")
parser.add_argument("--learning-material-probe", action="store_true",
                    help="Diagnostic only: test a softly refractive crystal shell")
parser.add_argument("--life-longitude-offset", type=float, default=0,
                    help="Diagnostic only: rotate Earth's geography/clouds by -180..180 degrees")
parser.add_argument("--front-key-probe", action="store_true",
                    help="Diagnostic only: move the existing key forward without increasing power")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
if not 1 <= args.samples <= 256:
    raise ValueError("Samples must be between 1 and 256")
if not math.isfinite(args.life_longitude_offset) or not -180 <= args.life_longitude_offset <= 180:
    raise ValueError("Life longitude offset must be finite and between -180 and 180 degrees")
scene = bpy.data.scenes["LifeOS_System_Composition_V2"]
bpy.context.window.scene = scene
camera = scene.camera
# Material detail views must not inherit the full scene's shallow foreground focus.
camera.data.dof.use_dof = False
scene.render.resolution_x, scene.render.resolution_y = 1200, 900
scene.cycles.samples = args.samples
if args.front_key_probe:
    key = scene.objects["Art_Key"]
    key.location = (-6, -4, 5.5)
    key.rotation_euler = (-key.location).to_track_quat("-Z", "Y").to_euler()
if args.life_longitude_offset:
    for name in ("Life_Geographic_Globe", "Life_Cloud_Shell"):
        scene.objects[name].rotation_euler.z += math.radians(args.life_longitude_offset)
if args.learning_material_probe:
    shader = bpy.data.materials["V2_Neural_Crystalline"].node_tree.nodes["Principled BSDF"]
    shader.inputs["Roughness"].default_value = 0.24
    shader.inputs["IOR"].default_value = 1.04
if args.hide_light_sources != "none":
    for obj in scene.objects:
        if obj.type == "LIGHT":
            obj.visible_transmission = False
            if args.hide_light_sources == "all":
                obj.visible_glossy = False
args.output_dir.mkdir(parents=True, exist_ok=True)
targets = ROOTS[:-1] if args.target == "all" else [args.target]


def root_of(obj):
    while obj:
        if obj.name in ROOTS:
            return obj.name
        obj = obj.parent
    return None


for target in targets:
    root = scene.objects[target]
    center = root.matrix_world.translation.copy()
    for obj in scene.objects:
        owner = root_of(obj)
        if owner:
            obj.hide_render = owner != target
    distance = 8.0 if target == "Fitness" else 5.3
    if target == "SelfCore":
        distance = 8.5
    camera.location = center + Vector((distance * 0.16, -distance, distance * 0.47))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 52
    rotation = camera.rotation_euler.to_quaternion()
    backplate = scene.objects["NonExport_Backplate"]
    backplate.location = camera.location + rotation @ Vector((0, 0, -65))
    backplate.rotation_euler = camera.rotation_euler
    backplate.scale = (65 * 36 / 104, 65 * 36 / 104 * 3 / 4, 1)
    scene.render.filepath = str(args.output_dir / (target.lower() + "-closeup.png"))
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)
    print("Authored close-up:", scene.render.filepath, flush=True)
