"""Portable geodesic ceramic/metal shell for the authored system scene."""
import bpy
import math
import random
from mathutils import Vector


def build_home_art(collection, location=(5.25, 1.85, 0.4)):
    rng = random.Random(427)
    relief_rng = random.Random(1427)
    root = bpy.data.objects.new("Home", None)
    collection.objects.link(root)
    root.location = location

    def material(name, color, metal, rough, emission=0):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        p = mat.node_tree.nodes["Principled BSDF"]
        p.inputs["Base Color"].default_value = (*color, 1)
        p.inputs["Metallic"].default_value = metal
        p.inputs["Roughness"].default_value = rough
        p.inputs["Emission Color"].default_value = (*color, 1)
        p.inputs["Emission Strength"].default_value = emission
        if not emission:
            finish = mat.node_tree.nodes.new("ShaderNodeTexNoise")
            finish.inputs["Scale"].default_value = 12
            finish.inputs["Detail"].default_value = 2
            roughness = mat.node_tree.nodes.new("ShaderNodeMapRange")
            roughness.inputs["To Min"].default_value = max(0, rough - 0.055)
            roughness.inputs["To Max"].default_value = min(1, rough + 0.09)
            mat.node_tree.links.new(finish.outputs["Fac"], roughness.inputs["Value"])
            mat.node_tree.links.new(roughness.outputs["Result"], p.inputs["Roughness"])
            grain = mat.node_tree.nodes.new("ShaderNodeTexNoise")
            grain.inputs["Scale"].default_value = 180
            grain.inputs["Detail"].default_value = 2
            bump = mat.node_tree.nodes.new("ShaderNodeBump")
            bump.inputs["Distance"].default_value = 0.0015
            bump.inputs["Strength"].default_value = 0.22
            mat.node_tree.links.new(grain.outputs["Fac"], bump.inputs["Height"])
            mat.node_tree.links.new(bump.outputs["Normal"], p.inputs["Normal"])
        return mat

    mats = [material("Home_Burnished_Bronze", (0.29, 0.13, 0.035), 0.88, 0.48),
            material("Home_Ceramic_Graphite", (0.065, 0.045, 0.026), 0.18, 0.73),
            material("Home_Pale_Alloy", (0.23, 0.155, 0.07), 0.78, 0.59),
            material("Home_Recessed_Graphite", (0.016, 0.011, 0.008), 0.22, 0.76),
            material("Home_Satin_Bronze", (0.19, 0.084, 0.024), 0.76, 0.67)]
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1)
    seed = bpy.context.object
    for vertex in seed.data.vertices:
        normal = vertex.co.normalized()
        perturbation = Vector((rng.uniform(-0.035, 0.035), rng.uniform(-0.035, 0.035), rng.uniform(-0.035, 0.035)))
        perturbation -= normal * perturbation.dot(normal)
        vertex.co = (normal + perturbation).normalized()
    seed.data.update()
    vertices = [v.co.copy() for v in seed.data.vertices]
    centers = [p.center.copy().normalized() for p in seed.data.polygons]
    adjacent = [[] for _ in vertices]
    for polygon in seed.data.polygons:
        for index in polygon.vertices:
            adjacent[index].append(centers[polygon.index])
    bpy.data.objects.remove(seed, do_unlink=True)
    verts, faces, slots = [], [], []
    # Mix whole geodesic cells with paired modules; retain a fitted shared shell.
    cells = []
    for index, normal in enumerate(vertices):
        normal.normalize()
        tangent = normal.cross(Vector((0, 0, 1)))
        if tangent.length < 0.01:
            tangent = normal.cross(Vector((0, 1, 0)))
        tangent.normalize()
        bitangent = normal.cross(tangent).normalized()
        corners = sorted(adjacent[index], key=lambda p: math.atan2(p.dot(bitangent), p.dot(tangent)))
        if len(corners) == 6 and index % 4 == 0:
            for part in [corners[:4], [corners[3], corners[4], corners[5], corners[0]]]:
                cells.append((sum(part, Vector()).normalized(), part))
        else:
            cells.append((normal.copy(), corners))
    # Local recessed pockets leave most of the fitted shell and silhouette intact.
    pockets = [(Vector(direction).normalized(), width) for direction, width in [
        ((-0.42, -0.85, 0.25), 0.34),
        ((0.68, -0.56, -0.30), 0.28),
        ((-0.35, 0.40, 0.85), 0.30),
    ]]
    for index, (normal, corners) in enumerate(cells):
        count = len(corners)
        start = len(verts)
        utility = index % 17 == 0
        offset = rng.uniform(-0.026, 0.036) - (0.028 if utility else 0)
        seam = rng.uniform(0.87, 0.95)
        slot = 1 if utility else rng.choices([0, 1, 2], [7, 3, 1])[0]
        pocket = max(max(0, 1 - (normal - direction).length / width) for direction, width in pockets)
        recessed = pocket > 0.18
        depth = 0.035 + 0.055 * pocket if recessed else 0
        offset -= depth
        if recessed:
            offset = max(offset, -0.075)
            seam -= relief_rng.uniform(0.07, 0.14)
            slot = 1 if pocket > 0.55 else 4
        elif slot == 0 and relief_rng.random() < 0.3:
            slot = 4
        bevel_width = relief_rng.uniform(0.019, 0.050)
        bevel_height = relief_rng.uniform(0.009, 0.022)
        tilt = Vector((relief_rng.uniform(-1, 1), relief_rng.uniform(-1, 1), relief_rng.uniform(-1, 1)))
        tilt -= normal * tilt.dot(normal)
        tilt *= 0.09
        # Pull back one local corner instead of opening every joint uniformly.
        chip = relief_rng.randrange(count) if recessed else -1
        fitted = [normal.lerp(corner, seam - (0.13 if edge == chip else 0)).normalized()
                  for edge, corner in enumerate(corners)]
        crown = [normal.lerp(corner, seam - bevel_width - (0.13 if edge == chip else 0)).normalized()
                 for edge, corner in enumerate(corners)]
        lowest_shoulder = min(1.001 + offset + max(-0.012, min(0.012, tilt.dot(direction - normal)))
                              for direction in fitted)
        base_radius = 0.889 if recessed else min(0.958, lowest_shoulder - 0.018)
        for ring_index, (ring, radius) in enumerate([(fitted, base_radius), (fitted, 1.001 + offset),
                                                    (crown, 1.001 + bevel_height + offset)]):
            verts.extend(tuple(direction * (radius + (max(-0.012, min(0.012, tilt.dot(direction - normal)))
                                                     if ring_index else 0)))
                         for direction in ring)
        center = len(verts)
        verts.append(tuple(normal * (1.001 + bevel_height + offset + relief_rng.uniform(0.004, 0.015))))
        for edge in range(count):
            nxt = (edge + 1) % count
            faces.append((start + edge, start + nxt, start + count + nxt, start + count + edge))
            slots.append(3 if recessed else 1)
            faces.append((start + count + edge, start + count + nxt, start + 2 * count + nxt, start + 2 * count + edge))
            slots.append(0 if slot == 0 else slot)
            faces.append((start + 2 * count + edge, start + 2 * count + nxt, center))
            slots.append(slot)
    mesh = bpy.data.meshes.new("Home_Geodesic_Panel_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        # Radial walls pass through the origin; their winding comes from corner order.
        if polygon.index % 3 != 0 and polygon.normal.dot(polygon.center) < 0:
            polygon.flip()
        polygon.material_index = slots[polygon.index]
        polygon.use_smooth = polygon.index % 3 == 2
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        coordinates = []
        for loop in polygon.loop_indices:
            p = mesh.vertices[mesh.loops[loop].vertex_index].co.normalized()
            coordinates.append(((math.atan2(p.y, p.x) + math.pi) / math.tau,
                                math.acos(max(-1, min(1, p.z))) / math.pi))
        wraps = max(u for u, _ in coordinates) - min(u for u, _ in coordinates) > 0.5
        for loop, (u, v) in zip(polygon.loop_indices, coordinates):
            uv.data[loop].uv = (u + (1 if wraps and u < 0.5 else 0), v)
    obj = bpy.data.objects.new("Home_Modular_Panels", mesh)
    collection.objects.link(obj)
    obj.parent = root
    for mat in mats:
        mesh.materials.append(mat)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.881)
    core = bpy.context.object
    for owner in list(core.users_collection):
        owner.objects.unlink(core)
    collection.objects.link(core)
    core.name = "Home_Recessed_Seam_Core"
    core.parent = root
    core.data.materials.append(mats[3])
    for polygon in core.data.polygons:
        polygon.use_smooth = True
    return root
