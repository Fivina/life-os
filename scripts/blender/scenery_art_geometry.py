"""Perspective-staged foreground, receding debris and sparse source-lit dust."""
import math
import random

import bpy
from mathutils import Vector, noise

from art_primitives import art_material, art_path, art_place, art_root


def build_scenery_depth(root, basalt, belt_basalt, track_material):
    def layer(name):
        group = art_root(name, (0, 0, 0))
        group.parent = root
        group["art_scenery_layer"] = True
        return group

    near_root = layer("Scenery_Near_Frame")
    belt_root = layer("Scenery_Receding_Belt")
    tracks_root = layer("Scenery_Orbit_Tracks")
    camera = Vector((0, -19.5, 12.5))
    forward = (Vector((0, 0.1, 0)) - camera).normalized()
    right = forward.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(forward).normalized()
    tan_x = 18 / 43
    tan_y = tan_x * 9 / 16

    def stage(position):
        x, y, depth = position
        return camera + forward * depth + right * (x * depth * tan_x) + up * (y * depth * tan_y)

    def bezier(points, t):
        return ((1 - t) ** 3 * points[0] + 3 * (1 - t) ** 2 * t * points[1]
                + 3 * (1 - t) * t ** 2 * points[2] + t ** 3 * points[3])

    # Screen-space control points author real perspective positions, not a flat backdrop.
    near = [stage(p) for p in [(-1.12, -0.98, 11.5), (-0.78, -0.60, 13.2),
                               (-0.56, -1.03, 15.5), (0.22, -1.12, 18.0)]]
    receding = [stage(p) for p in [(-1.02, -0.65, 16.5), (-1.04, 0.19, 23.5),
                                  (-0.12, 0.62, 31), (0.98, 0.32, 34.5)]]

    def belt_position(t, generator, width_scale=1):
        center = bezier(receding, t)
        tangent = (bezier(receding, min(1, t + 0.01))
                   - bezier(receding, max(0, t - 0.01))).normalized()
        transverse = (right * tangent.dot(up) - up * tangent.dot(right)).normalized()
        width = (0.24 + 0.68 * math.sin(math.pi * t)) * width_scale
        width *= 0.8 + 0.2 * math.sin(t * 27 + 0.6)
        offset = max(-width, min(width, generator.gauss(0, width * 0.55)))
        center += transverse * (offset + 0.12 * math.sin(t * 23))
        center += forward * generator.uniform(-0.45, 0.45) * (1 + 0.8 * math.sin(math.pi * t))
        return center

    root["art_depth_layers"] = "Near frame 11.5-18; receding belt 16.5-34.5; distant bitmap is non-geometry"
    rng = random.Random(916)
    meshes = {}

    def rock(name, center, radius, detail, shape, parent, material):
        key = (detail, shape, material.as_pointer())
        if key not in meshes:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=detail, radius=1)
            obj = art_place(bpy.context.object, name, parent)
            offset = Vector((shape * 0.73, shape * 0.21, 0))
            for vertex in obj.data.vertices:
                direction = vertex.co.normalized()
                relief = noise.noise(direction * 2.9 + offset) * 0.25
                relief += noise.noise(direction * 13.5 + offset) * 0.055
                relief += noise.noise(direction * 37 + offset) * 0.016
                vertex.co *= 1 + relief
            obj.data.materials.append(material)
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
            meshes[key] = obj.data
        else:
            obj = bpy.data.objects.new(name, meshes[key])
            root.users_collection[0].objects.link(obj)
            obj.parent = parent
        obj.location = center
        obj.scale = (radius * rng.uniform(1.05, 1.8), radius * rng.uniform(0.65, 1.1),
                     radius * rng.uniform(0.8, 1.3))
        obj.rotation_euler = tuple(rng.uniform(-math.pi, math.pi) for _ in range(3))

    for index in range(18):
        t = index / 17
        center = bezier(near, t)
        center += right * rng.uniform(-0.16, 0.16) + up * rng.uniform(-0.10, 0.10)
        radius = (0.50 * (1 - t) ** 1.6 + 0.09) * rng.uniform(0.65, 1.2)
        rock("Near_Frame_Debris_%02d" % index, center, radius,
             4 if index < 7 else 3, index % 5, near_root, basalt)

    # Unequal clumps and dark gaps avoid the uniformly spaced bead-chain reading.
    times = []
    for cluster, (count, center, spread) in enumerate(((12, 0.07, 0.05), (10, 0.23, 0.06),
                                                      (16, 0.42, 0.07), (12, 0.65, 0.09),
                                                      (8, 0.87, 0.10))):
        if cluster == 0:
            times.extend(0.02 + 0.19 * (index + rng.uniform(0.1, 0.9)) / count
                         for index in range(count))
        else:
            times.extend(max(0, min(1, rng.gauss(center, spread * 0.5))) for _ in range(count))
    for index, t in enumerate(sorted(times)):
        center = belt_position(t, rng, 0.9)
        radius = (0.25 * (1 - t) ** 1.8 + 0.028) * rng.uniform(0.38, 1.25)
        if t < 0.38:
            radius *= 0.78 if index % 5 == 0 else 0.3
            center += forward * (index % 3 - 1) * 0.6
        rock("Receding_Belt_Debris_%02d" % index, center, radius,
             3 if index < 18 else 2, index % 5, belt_root, belt_basalt)

    dust = art_material("V26_Source_Lit_Dust", (0.16, 0.22, 0.27), 0, 0.85, 0)
    dust.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.08
    dust_mesh = None
    for index in range(90):
        t = rng.uniform(0.1, 0.97)
        center = belt_position(t, rng, 1.3)
        if dust_mesh is None:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1)
            fleck = art_place(bpy.context.object, "Source_Lit_Dust_%02d" % index, belt_root)
            fleck.data.materials.append(dust)
            dust_mesh = fleck.data
        else:
            fleck = bpy.data.objects.new("Source_Lit_Dust_%02d" % index, dust_mesh)
            root.users_collection[0].objects.link(fleck)
            fleck.parent = belt_root
        fleck.location = center
        radius = rng.uniform(0.008, 0.024) * (1.2 - t * 0.4)
        fleck.scale = (radius * 1.8, radius * 0.6, radius)
        fleck.rotation_euler = tuple(rng.uniform(-2, 2) for _ in range(3))

    # Smaller shared-material chips bridge clumps without filling their dark gaps.
    fragments = random.Random(1916)
    fragment_times = [fragments.uniform(0.03, 0.98) for _ in range(48)]
    for center, spread in ((0.07, 0.05), (0.23, 0.06), (0.42, 0.07),
                           (0.65, 0.09), (0.87, 0.10)):
        fragment_times.extend(max(0, min(1, fragments.gauss(center, spread)))
                              for _ in range(24))
    for index, t in enumerate(sorted(fragment_times)):
        center = belt_position(t, fragments, 1.05)
        radius = (0.075 * (1 - t) ** 1.3 + 0.012) * fragments.uniform(0.45, 1.1)
        rock("Receding_Belt_Chip_%03d" % index, center, radius,
             1, index % 5, belt_root, belt_basalt)

    # Interrupted noncoplanar paths remain subordinate to the physical belt.
    for index, radius in enumerate((5.2, 7.25)):
        for arc, (start, end) in enumerate(((0.18, 1.3), (1.45, 2.7), (3.05, 4.25), (4.65, 5.85))):
            angles = [start + (end - start) * i / 63 for i in range(64)]
            path = art_path("System_Depth_Track_%s_%s" % (index, arc),
                            [(radius * math.cos(t), radius * 0.73 * math.sin(t),
                              0.5 * math.sin(t) + (index * 2 - 1) * 0.35 * math.cos(t * 2)) for t in angles],
                            0.0018, track_material, tracks_root)
            for sample, point in enumerate(path.data.splines[0].points):
                point.radius = 0.1 + 0.9 * math.sin(math.pi * sample / 63) ** 0.7
    return near_root
