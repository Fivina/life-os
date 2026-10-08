"""Repeatable system/portrait/clay proof without saving over the authored source."""
import argparse
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from art_composition import apply_portrait_composition
from art_primitives import art_material

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--composition", choices=("system", "portrait"), default="system")
parser.add_argument("--look", choices=("authored", "clay", "untextured"), default="authored")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--samples", type=int, default=32)
parser.add_argument("--width", type=int, help="Optional 160..1600 px evidence render; preserves composition aspect")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
if not 1 <= args.samples <= 256:
    raise ValueError("Samples must be between 1 and 256")
if args.width is not None and not 160 <= args.width <= 1600:
    raise ValueError("Evidence width must be between 160 and 1600 pixels")
scene = bpy.data.scenes["LifeOS_System_Composition_V2"]
bpy.context.window.scene = scene
scene.cycles.samples = args.samples
if args.composition == "portrait":
    scene.render.resolution_x, scene.render.resolution_y = 780, 1688
    apply_portrait_composition(scene)
if args.width is not None:
    aspect = scene.render.resolution_y / scene.render.resolution_x
    scene.render.resolution_x, scene.render.resolution_y = args.width, round(args.width * aspect)
if args.look == "clay":
    scene.camera.data.dof.use_dof = False
    clay = art_material("Proof_Neutral_Clay", (0.18, 0.18, 0.18), roughness=0.65, metallic=0)
    for obj in scene.objects:
        if obj.name.startswith("NonExport_") or obj.get("art_bounds_exclude"):
            obj.hide_render = True
        elif obj.type in ("MESH", "CURVE"):
            for index in range(len(obj.data.materials)):
                obj.data.materials[index] = clay
    scene.render.use_compositing = False
elif args.look == "untextured":
    scene.camera.data.dof.use_dof = False
    # Preserve real material identity/emission and lighting. Neutral clay is a
    # separate silhouette diagnostic, not proof of the authored focal hierarchy.
    seen = set()
    for obj in scene.objects:
        if obj.name.startswith("NonExport_"):
            obj.hide_render = True
        if obj.type not in ("MESH", "CURVE"):
            continue
        for mat in obj.data.materials:
            # Bounds exclusion controls fitting, not diagnostic visibility.
            if mat.get("art_role") in ("stylized_clouds", "stellar_scattering"):
                obj.hide_render = True
            if mat in seen or not mat.use_nodes:
                continue
            seen.add(mat)
            shader = mat.node_tree.nodes.get("Principled BSDF")
            if shader:
                for channel in ("Base Color", "Roughness", "Normal", "Emission Color"):
                    for link in list(shader.inputs[channel].links):
                        mat.node_tree.links.remove(link)
    scene.render.use_compositing = False
args.output.parent.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(args.output)
bpy.context.view_layer.update()
bpy.ops.render.render(write_still=True)
print("Composition proof:", args.composition, args.look, scene.render.filepath, flush=True)
