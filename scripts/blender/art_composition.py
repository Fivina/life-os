"""Authored portrait staging shared with the exported development preview."""
import math

import bpy
from mathutils import Vector

from art_primitives import art_aim


PORTRAIT = {
    "SelfCore": ((0, -0.05, 0.35), 0.9),
    "Learning": ((-0.3, 4.1, 1.45), 0.82),
    "Calendar": ((-1.32, 1.65, 0.65), 0.7),
    "Home": ((1.2, 2.1, 0.8), 0.7),
    "Life": ((-1.2, -2.6, -0.7), 0.78),
    "Fitness": ((1.15, -2.8, -0.85), 0.64),
    "Scenery": ((0, 0, 0), 1),
    "Scenery_Near_Frame": ((0.5, -2.0, -0.45), 0.4),
    "Scenery_Receding_Belt": ((0.7, 0.6, -1.3), 0.48),
    "Scenery_Orbit_Tracks": ((0.2, -1.7, -0.7), 0.38),
}

# The tighter authored staging places neighbors closer to the central source.
PORTRAIT_SOURCE_POWER_SCALE = 0.22


def store_portrait_contract(scene):
    scene.objects["SelfCore"]["art_portrait_source_power_scale"] = PORTRAIT_SOURCE_POWER_SCALE
    for name, (position, scale) in PORTRAIT.items():
        root = scene.objects[name]
        x, y, z = position
        # Extras contain final glTF Y-up coordinates; the exporter changes only
        # geometry/transforms, not arbitrary numeric metadata.
        root["art_portrait_position"] = [x, z, -y]
        root["art_portrait_scale"] = scale


def apply_portrait_composition(scene):
    # Replay the saved revision's contract, not today's constants, for old studies.
    for root in scene.objects:
        position = root.get("art_portrait_position")
        scale = root.get("art_portrait_scale")
        if position is None or len(position) != 3 or not isinstance(scale, (int, float)):
            continue
        if (not all(isinstance(v, (int, float)) and math.isfinite(v) and abs(v) <= 20 for v in position)
                or not math.isfinite(scale) or not 0.2 <= scale <= 1.5):
            raise ValueError("Invalid authored portrait metadata: " + root.name)
        root.location = (position[0], -position[2], position[1])
        root.scale *= scale
    power = scene.objects["SelfCore"].get("art_portrait_source_power_scale", 1)
    if not isinstance(power, (int, float)) or not math.isfinite(power) or not 0 < power <= 1:
        raise ValueError("Invalid authored portrait source power")
    scene.objects["Self_Core_Light"].data.energy *= power
    camera = scene.camera
    camera.location = (0, -13, 8.3)
    camera.data.lens = 43
    art_aim(camera, (0, 0.45, 0))
    camera.data.dof.focus_distance = (camera.location - scene.objects["SelfCore"].location).length
    camera.data.dof.aperture_fstop = 0.5
    rotation = camera.rotation_euler.to_quaternion()
    backplate = scene.objects["NonExport_Backplate"]
    backplate.location = camera.location + rotation @ Vector((0, 0, -65))
    backplate.rotation_euler = camera.rotation_euler
    width = 65 * 36 / (2 * camera.data.lens)
    # Match Blender's AUTO sensor-fit: portrait uses its vertical 36mm field.
    # Cover the portrait frame by cropping the wide bitmap, never stretching it.
    backplate.scale = (width * 16 / 9, width, 1)
    bpy.context.view_layer.update()
