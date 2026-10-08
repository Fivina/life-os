"""Shared primitives for authored Life OS scene studies (Blender MCP safe mode)."""
import bpy
import math
import random
from mathutils import Vector


def art_material(name, color, emission=0, roughness=0.45, metallic=0.1):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Emission Color"].default_value = (*color, 1)
    shader.inputs["Emission Strength"].default_value = emission
    return mat


def art_place(obj, name, root=None, collection=None):
    obj.name = name
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    (collection or assets).objects.link(obj)
    obj.parent = root
    return obj


def art_root(name, location):
    obj = bpy.data.objects.new(name, None)
    assets.objects.link(obj)
    obj.location = location
    return obj


def art_sphere(name, radius, mat, root=None, location=(0, 0, 0), detail=48):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=detail, ring_count=detail // 2,
                                       radius=radius, location=location)
    obj = art_place(bpy.context.object, name, root)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def art_path(name, points, width, mat, root=None, cyclic=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = width
    data.bevel_resolution = 1
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, position in zip(spline.points, points):
        point.co = (*position, 1)
    spline.use_cyclic_u = cyclic
    data.materials.append(mat)
    obj = bpy.data.objects.new(name, data)
    assets.objects.link(obj)
    obj.parent = root
    return obj


def art_orbit(name, radius, color, root=None, flatten=0.75, tilt=0.2, width=0.008):
    return art_path(name, [(radius * math.cos(t), radius * flatten * math.sin(t), tilt * math.sin(t))
                          for t in [i * math.tau / 192 for i in range(192)]], width, color, root, True)


def art_surface(name, low, high, mid=None):
    mat = art_material(name, low, roughness=0.72)
    tree = mat.node_tree
    shader = tree.nodes["Principled BSDF"]
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 5.5
    noise.inputs["Detail"].default_value = 5
    noise.inputs["Roughness"].default_value = 0.72
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.40
    ramp.color_ramp.elements[0].color = (*low, 1)
    ramp.color_ramp.elements[1].position = 0.62
    ramp.color_ramp.elements[1].color = (*high, 1)
    if mid:
        middle = ramp.color_ramp.elements.new(0.52)
        middle.color = (*mid, 1)
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    texture = tree.nodes.new("ShaderNodeTexNoise")
    texture.inputs["Scale"].default_value = 85
    texture.inputs["Detail"].default_value = 3
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.018
    bump.inputs["Strength"].default_value = 0.3
    tree.links.new(texture.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


def art_aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def art_light(name, position, energy, color, size=3):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    staging.objects.link(obj)
    obj.location = position
    art_aim(obj, (0, 0, 0))
    return obj
