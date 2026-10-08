"""Isolated editable Settings artwork; never loads or exports the system scene.

Run the E: source copy with Blender --background --threads 4 --python ...
The saved artwork is a concept, not runtime parity or an approved art gate.
"""
import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import bpy

# Reuse existing curve primitives without writing shared-module bytecode.
sys.dont_write_bytecode = True
sys.path.insert(0, "D:/Life OS/scripts/blender")
import art_primitives as primitives
from art_primitives import art_aim, art_path, art_root


def emission(name, color, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    shader = tree.nodes.new("ShaderNodeEmission")
    shader.inputs["Color"].default_value = (*color, 1)
    shader.inputs["Strength"].default_value = strength
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(shader.outputs[0], output.inputs[0])
    return mat


def delta(angle, center):
    return math.atan2(math.sin(angle - center), math.cos(angle - center))


def point(radius, angle, z=0):
    # Authored elliptical silhouette, with shallow sculptural depth behind it.
    x, y = radius * math.cos(angle), radius * math.sin(angle) * 0.89
    turn = 0.12
    return (x * math.cos(turn) - y * math.sin(turn),
            x * math.sin(turn) + y * math.cos(turn), z)


def band(name, inner, outer, rings, parent, shade, depth=-0.015):
    steps = 768
    vertices, colors, faces = [], [], []
    for row in range(rings + 1):
        radius = inner + (outer - inner) * row / rings
        for spoke in range(steps):
            angle = math.tau * spoke / steps
            vertices.append(point(radius, angle, depth))
            colors.append((*shade(radius, angle), 1))
    for row in range(rings):
        for spoke in range(steps):
            a = row * steps + spoke
            b = row * steps + (spoke + 1) % steps
            faces.append((a, b, b + steps, a + steps))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    attr = mesh.color_attributes.new(name="AuthoredRadiance", type="FLOAT_COLOR", domain="POINT")
    for item, color in zip(attr.data, colors):
        item.color = color
    obj = bpy.data.objects.new(name, mesh)
    primitives.assets.objects.link(obj)
    obj.parent = parent
    mat = emission(name + "_VertexEmission", (1, 1, 1))
    shader = mat.node_tree.nodes.get("Emission")
    attribute = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    attribute.layer_name = attr.name
    mat.node_tree.links.new(attribute.outputs["Color"], shader.inputs["Color"])
    mesh.materials.append(mat)
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("E:/LifeOS-Art/gravity-well-study"))
    parser.add_argument("--revision", choices=("01", "02"), default="01")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--filament-gain", type=float, default=0.45)
    parser.add_argument("--bloom-strength", type=float, default=0.14)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    allowed = Path("E:/LifeOS-Art/gravity-well-study").resolve()
    if args.output_dir.resolve() != allowed:
        raise ValueError("Study outputs must stay in E:/LifeOS-Art/gravity-well-study")
    if not 1 <= args.samples <= 32:
        raise ValueError("This study is limited to 1..32 samples")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Settings_Gravity_Well_Art_Study"
    assets = bpy.data.collections.new("GravityWell_Editable_Artwork")
    staging = bpy.data.collections.new("Study_Camera_Only")
    scene.collection.children.link(assets)
    scene.collection.children.link(staging)
    primitives.assets, primitives.staging = assets, staging
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 2
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x, scene.render.resolution_y = 1200, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Absolute_Black_Stage")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0
    scene.world = world
    scene["art_gate"] = "UNAPPROVED - isolated concept; primary owns integration"
    scene["reference"] = "settings_gravity_well_catalog.png + depth_0_reference.png, viewed before authoring"
    root = art_root("GravityWellRoot", (0, 0, 0))
    root["void_radius"] = 1.195
    root["lensing_radius"] = 1.208
    root["flow_density"] = 156
    root["filament_gain"] = args.filament_gain
    root["halo_intensity"] = 0.10
    root["concept_only"] = True
    root["edit_notes"] = "Curves: spline radii control taper. Rim/halo: editable radiance vertex colors. No texture or tunnel in void."
    lens = art_root("LensingRing", (0, 0, 0))
    field = art_root("OuterDistortionField", (0, 0, 0))
    flow = art_root("FlowParticles", (0, 0, 0))
    stars = art_root("WarpedStarField", (0, 0, 0))
    for group in (lens, field, flow, stars):
        group.parent = root
    field["concept_note"] = "Authored bent curves, not physical background lensing"

    # A filled zero-emission silhouette absorbs everything behind it.
    mesh = bpy.data.meshes.new("VoidCore_Silhouette")
    mesh.from_pydata([point(1.195, math.tau * i / 768, 0.09) for i in range(768)], [], [tuple(range(768))])
    mesh.update()
    void = bpy.data.objects.new("VoidCore", mesh)
    assets.objects.link(void)
    void.parent = root
    mesh.materials.append(emission("Void_Zero_Radiance", (0, 0, 0), 0))
    void.pass_index = 1
    void["featureless"] = True

    def rim_shade(radius, angle):
        hot = math.exp(-(delta(angle, 2.40) / 0.27) ** 2)
        minor = math.exp(-(delta(angle, 5.28) / 0.20) ** 2)
        intensity = (0.70 + 5.2 * hot + 2.1 * minor) * math.exp(-((radius - 1.208) / 0.0075) ** 2)
        ice = 0.75 * hot + 0.35 * minor
        return tuple(intensity * channel for channel in (0.32 + ice * 0.45, 0.69 + ice * 0.22, 1.0))

    band("Continuous_Narrow_Photon_Rim", 1.1955, 1.233, 16, lens, rim_shade)
    band("Cool_Weak_Halo", 1.215, 1.70, 24, field,
         lambda r, a: tuple(c * 0.10 * math.exp(-((r - 1.24) / 0.13) ** 2)
                            * (0.42 + 0.58 * math.exp(-(delta(a, 2.4) / 0.65) ** 2))
                            for c in (0.09, 0.29, 0.49)), depth=-0.22)
    for label, center, span, width, strength in (
            ("Primary", 2.40, 0.36, 0.005, 5.2),
            ("Secondary", 5.28, 0.24, 0.0035, 2.2)):
        crescent = art_path(label + "_Localized_Hot_Crescent",
                            [point(1.213, center - span + 2 * span * j / 96, 0.015)
                             for j in range(97)], width,
                            emission(label + "_Ice_Radiance", (0.70, 0.91, 1.0), strength), lens)
        for j, p in enumerate(crescent.data.splines[0].points):
            p.radius = 0.015 + math.sin(math.pi * j / 96) ** 1.8

    rng = random.Random(721034)
    mats = [emission("Cool_Filament_%02d" % i, (0.11 + i * 0.025, 0.31 + i * 0.05, 0.48 + i * 0.065),
                     args.filament_gain * (0.28 + i * 0.12)) for i in range(7)]
    particle_mat = emission("Flow_Silver_Blue", (0.48, 0.76, 0.96), 1.3)
    paths = []
    for index in range(156):
        family = index % 2
        lane = (index // 2) / 77
        end = (2.40 if family == 0 else 5.28) + (lane - 0.5) * (1.05 if family == 0 else 0.90)
        outer = rng.uniform(2.6, 4.8)
        twist = 1.8 + lane * 0.7 + rng.uniform(-0.12, 0.12)
        points = []
        for j in range(112):
            t = j / 111
            radial = 1.245 + (outer - 1.245) * (1 - t) ** 1.55
            angle = end - twist * (1 - t) ** 0.84
            points.append(point(radial, angle, -0.065 + 0.035 * math.sin(t * math.pi + lane * 3)))
        paths.append(points)
        material_index = rng.randrange(7)
        curve = art_path("Infall_Fan_%s_%03d" % ("A" if family == 0 else "B", index),
                         points, rng.uniform(0.0015, 0.0033), mats[material_index], field)
        for j, p in enumerate(curve.data.splines[0].points):
            t = j / 111
            p.radius = (0.04 + math.sin(math.pi * t) ** 0.75 + 0.35 * t ** 5) * (0.35 + 0.65 * t)
        curve["flow_direction"] = "Spline start -> end: inward"

    # Small elongated beads follow the tangent; no isolated dots inside the void.
    for index in range(135):
        points = paths[rng.randrange(len(paths))]
        j = rng.randrange(16, 99)
        bead = art_path("Infall_Bead_%03d" % index, points[j:j + 2],
                        rng.uniform(0.0022, 0.0048), particle_mat, flow)
        bead.data.splines[0].points[0].radius = 0.15

    quiet = emission("Warped_Starlight_Quiet", (0.12, 0.25, 0.35), 0.36)
    for index in range(22):
        angle = rng.uniform(0, math.tau)
        radius = rng.uniform(1.85, 3.85)
        span = rng.uniform(0.025, 0.08)
        points = [point(radius + span * (1 - j / 10), angle + span * j / 10, -0.15)
                  for j in range(11)]
        art_path("Bent_Starlight_%02d" % index, points, 0.002, quiet, stars)

    data = bpy.data.cameras.new("Fixed_1200x900_Closeup")
    camera = bpy.data.objects.new(data.name, data)
    staging.objects.link(camera)
    camera.location = (0, 0, 12)
    art_aim(camera, (0, 0, 0))
    data.type = "ORTHO"
    data.ortho_scale = 6.5
    scene.camera = camera
    scene["fixed_camera"] = "Orthographic 6.5, location 0/0/12, aim 0/0/0; identical across revisions"

    # Re-mask the absorbing silhouette after optical scatter, keeping its interior empty.
    bpy.context.view_layer.use_pass_object_index = True
    bpy.context.view_layer.update_render_passes()
    tree = bpy.data.node_groups.new("Quiet_Lensing_Scatter_With_Absorbing_Void", "CompositorNodeTree")
    scene.compositing_node_group = tree
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = tree.nodes.new("CompositorNodeRLayers")
    layers.scene = scene
    glow = tree.nodes.new("CompositorNodeGlare")
    glow.inputs["Type"].default_value = "Fog Glow"
    glow.inputs["Threshold"].default_value = 1.0
    glow.inputs["Strength"].default_value = args.bloom_strength
    glow.inputs["Size"].default_value = 0.20
    mask = tree.nodes.new("CompositorNodeIDMask")
    mask.inputs["Index"].default_value = 1
    mask.inputs["Anti-Alias"].default_value = True
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (0, 0, 0, 1)
    output = tree.nodes.new("NodeGroupOutput")
    tree.links.new(layers.outputs["Image"], glow.inputs["Image"])
    tree.links.new(layers.outputs["Object Index"], mask.inputs[0])
    tree.links.new(mask.outputs[0], mix.inputs[0])
    tree.links.new(glow.outputs["Image"], mix.inputs[6])
    tree.links.new(mix.outputs[2], output.inputs["Image"])
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    bpy.context.view_layer.objects.active = root
    root.select_set(True)
    stem = "gravity-well-study-r" + args.revision
    blend_path = args.output_dir / (stem + ".blend")
    png_path = args.output_dir / (stem + "-closeup.png")
    scene.render.filepath = str(png_path)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)
    report = {
        "blender": bpy.app.version_string,
        "blend": str(blend_path), "png": str(png_path),
        "resolution": [1200, 900], "engine": scene.render.engine,
        "samples": scene.cycles.samples, "threads": scene.render.threads,
        "objects": len(scene.objects), "curves": sum(o.type == "CURVE" for o in scene.objects),
        "duration_seconds": round(time.monotonic() - started, 2),
        "filament_gain": args.filament_gain, "bloom_strength": args.bloom_strength,
        "art_gate": scene["art_gate"],
        "limitations": ["Authored bent starlight, no physical background refraction",
                        "Static artwork, no state animation or production export",
                        "Relative Core brightness not verified in a shared composition"]
    }
    (args.output_dir / (stem + "-result.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("GRAVITY_WELL_STUDY_RESULT " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
