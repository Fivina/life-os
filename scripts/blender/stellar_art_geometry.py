"""Surface-rooted magnetic streamers and a portable, source-bound corona."""
import math
import random

import bpy
from mathutils import Vector

from art_primitives import art_material, art_path, art_place


def build_stellar_envelope(root):
    rng = random.Random(813)
    hot = art_material("V8_Plasma_Hot", (0.16, 0.67, 1.0), 6.5, metallic=0)
    warm = art_material("V8_Plasma_Field", (0.025, 0.32, 0.72), 2.8, metallic=0)
    faint = art_material("V8_Plasma_Fine", (0.009, 0.09, 0.25), 0.9, metallic=0)
    for bundle in range(24):
        z = 1 - 2 * (bundle + 0.5) / 24
        azimuth = bundle * 2.39996323
        normal = Vector((math.sqrt(1 - z * z) * math.cos(azimuth),
                         math.sqrt(1 - z * z) * math.sin(azimuth), z))
        tangent = normal.cross(Vector((0, 0, 1))).normalized()
        binormal = normal.cross(tangent).normalized()
        reach = rng.uniform(0.22, 0.5) if bundle % 4 else rng.uniform(0.7, 1.2)
        sweep = rng.uniform(0.25, 0.75)
        for strand in range(3):
            offset = (strand - 1) * 0.012
            points = []
            for sample in range(65):
                t = sample / 64
                arch = math.sin(math.pi * t)
                angle = sweep * t ** 1.3
                radius = 0.435 + reach * t ** 0.8 * (1 + offset * 4)
                direction = normal * math.cos(angle) + tangent * math.sin(angle)
                p = direction * radius
                p += binormal * (offset + (strand - 1) * 0.12 * t ** 1.5 + 0.06 * arch * math.sin(t * 11 + bundle))
                p += tangent * (0.035 * arch * math.sin(t * 15 + strand * 0.6))
                points.append(tuple(p))
            brightest = strand == 1 and bundle % 5 == 0
            material = hot if brightest else warm if strand == 1 else faint
            width = 0.0045 if brightest else 0.0024 if material == warm else 0.0011
            curve = art_path("Self_Magnetic_Bundle_{}_{}".format(bundle, strand),
                             points, width, material, root)
            for sample, point in enumerate(curve.data.splines[0].points):
                t = sample / 64
                point.radius = (1 - t) ** 0.8 * (0.5 + 0.8 * math.sin(math.pi * t))

    # Keep the source's long, optical filaments out of body/label fitting bounds.
    outer_material = art_material("V31_Rooted_Coronal_Field", (0.018, 0.3, 0.65), 1.5, metallic=0)
    field = None
    for ray in range(8):
        angle = ray * math.tau / 8 + rng.uniform(-0.32, 0.32)
        reach = rng.uniform(1.3, 2.4)
        sweep = rng.choice((-1, 1)) * rng.uniform(0.12, 0.38)
        lift = rng.uniform(-1.2, 1.2)
        shoulder = rng.uniform(0.28, 0.5)
        for strand in range(2):
            points = []
            strand_reach = reach * (1 if strand == 0 else rng.uniform(0.65, 0.9))
            divergence = rng.uniform(-0.14, 0.14) if strand else 0
            for sample in range(97):
                t = sample / 96
                phase = angle + sweep * t ** 1.4 + divergence * t ** 1.5
                phase += 0.10 * math.sin(t * 13 + ray) * math.sin(math.pi * t)
                radius = 0.435 + strand_reach * t ** 0.85
                height = 0.06 + lift * t + (0.13 + strand * 0.08) * math.sin(math.pi * t)
                height += 0.035 * math.sin(t * 9 + ray) * math.sin(math.pi * t)
                points.append((radius * math.cos(phase), radius * math.sin(phase), height))
            if field is None:
                field = art_path("Self_Extended_Coronal_Field", points, 0.0020, outer_material, root)
                field["art_bounds_exclude"] = True
                spline = field.data.splines[0]
            else:
                spline = field.data.splines.new("POLY")
                spline.points.add(len(points) - 1)
            # A continuous, source-rooted envelope fades without detached caps.
            for sample, (point, position) in enumerate(zip(spline.points, points)):
                t = sample / 96
                activity = 0.45 + 0.65 * math.exp(-((t - shoulder) / 0.2) ** 2)
                point.co = (*position, 1)
                point.radius = (1 - t) ** 2.1 * activity * (1 if strand == 0 else 0.65)

    # A static optical-depth sheet follows the authored camera direction. It is
    # a stellar scattering layer, not a background decoration or baked lighting.
    mat = art_material("V8_Stellar_Corona", (0, 0, 0), 3.2, 1, 0)
    mat["art_role"] = "stellar_scattering"
    mat.surface_render_method = "DITHERED"
    mat.use_backface_culling = True
    tree = mat.node_tree
    shader = tree.nodes["Principled BSDF"]
    shader.inputs["Specular IOR Level"].default_value = 0
    shader.inputs["Emission Color"].default_value = (0.014, 0.31, 0.8, 1)
    uv = tree.nodes.new("ShaderNodeTexCoord")
    distance = tree.nodes.new("ShaderNodeVectorMath")
    distance.operation = "DISTANCE"
    distance.inputs[1].default_value = (0.5, 0.5, 0)
    tree.links.new(uv.outputs["UV"], distance.inputs[0])
    radial = tree.nodes.new("ShaderNodeValToRGB")
    radial.color_ramp.interpolation = "EASE"
    radial.color_ramp.elements.remove(radial.color_ramp.elements[1])
    for index, (position, opacity) in enumerate([(0, 0.25), (0.12, 0.21),
                                               (0.22, 0.045), (0.37, 0.005), (0.5, 0)]):
        element = radial.color_ramp.elements[0] if index == 0 else radial.color_ramp.elements.new(position)
        element.position = position
        element.color = (opacity, opacity, opacity, 1)
    tree.links.new(distance.outputs["Value"], radial.inputs["Fac"])
    density = tree.nodes.new("ShaderNodeTexNoise")
    density.inputs["Scale"].default_value = 8
    density.inputs["Detail"].default_value = 4
    density.inputs["Distortion"].default_value = 1.4
    tree.links.new(uv.outputs["UV"], density.inputs["Vector"])
    modulation = tree.nodes.new("ShaderNodeValToRGB")
    modulation.color_ramp.elements[0].position = 0.36
    modulation.color_ramp.elements[0].color = (0.18, 0.18, 0.18, 1)
    modulation.color_ramp.elements[1].position = 0.7
    modulation.color_ramp.elements[1].color = (0.72, 0.72, 0.72, 1)
    tree.links.new(density.outputs["Fac"], modulation.inputs["Fac"])
    alpha = tree.nodes.new("ShaderNodeMath")
    alpha.operation = "MULTIPLY"
    tree.links.new(radial.outputs["Color"], alpha.inputs[0])
    tree.links.new(modulation.outputs["Color"], alpha.inputs[1])
    tree.links.new(alpha.outputs[0], shader.inputs["Alpha"])
    facing = Vector((0, -19.5, 12.15)).normalized()
    bpy.ops.mesh.primitive_plane_add(size=4.5)
    envelope = art_place(bpy.context.object, "Self_Source_Bound_Corona", root)
    envelope.location = -facing * 0.29
    envelope.rotation_euler = facing.to_track_quat("Z", "Y").to_euler()
    envelope.data.materials.append(mat)
    envelope.visible_shadow = False
    envelope["art_bounds_exclude"] = True
