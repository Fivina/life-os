"""First editable art study. Run through Blender MCP, not system Python."""

import bpy
import math
from mathutils import Vector

scene = bpy.data.scenes.new("LifeOS_Fitness_ArtStudy")
bpy.context.window.scene = scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1440
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = "E:/LifeOS-Art/fitness/fitness-art-study.png"
scene.view_settings.view_transform = "AgX"

world = bpy.data.worlds.new("LifeOS_Void")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.001, 0.003, 0.008, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.12

art = bpy.data.collections.new("Fitness_Asset")
scene.collection.children.link(art)
stage = bpy.data.collections.new("Preview_Stage_Not_For_Export")
scene.collection.children.link(stage)


def place(obj, name, collection=art):
    obj.name = name
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


def metal(name, color, roughness=0.28, metallic=0.8, glow=0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    shader = material.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Emission Color"].default_value = (*color, 1)
    shader.inputs["Emission Strength"].default_value = glow
    return material


def planet_material(name, low, high):
    material = metal(name, low, 0.7, 0.14)
    tree = material.node_tree
    shader = tree.nodes["Principled BSDF"]
    texture = tree.nodes.new("ShaderNodeTexNoise")
    texture.inputs["Scale"].default_value = 4.8
    texture.inputs["Detail"].default_value = 5.0
    texture.inputs["Roughness"].default_value = 0.73
    texture.inputs["Distortion"].default_value = 0.65
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[0].color = (*low, 1)
    ramp.color_ramp.elements[1].position = 0.67
    ramp.color_ramp.elements[1].color = (*high, 1)
    mid = ramp.color_ramp.elements.new(0.53)
    mid.color = (*(channel * 0.38 for channel in high), 1)
    tree.links.new(texture.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    detail = tree.nodes.new("ShaderNodeTexNoise")
    detail.inputs["Scale"].default_value = 125
    detail.inputs["Detail"].default_value = 3
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.025
    tree.links.new(detail.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    fresnel = tree.nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.15
    edge = tree.nodes.new("ShaderNodeMath")
    edge.operation = "POWER"
    edge.inputs[1].default_value = 2
    strength = tree.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = 3
    tree.links.new(fresnel.outputs["Fac"], edge.inputs[0])
    tree.links.new(edge.outputs[0], strength.inputs[0])
    tree.links.new(strength.outputs[0], shader.inputs["Emission Strength"])
    shader.inputs["Emission Color"].default_value = (*high, 1)
    return material


steel = metal("Titanium_Graphite", (0.026, 0.058, 0.083))
bevel_metal = metal("Machined_Ice_Edge", (0.24, 0.42, 0.5), 0.2, 0.92)
light = metal("Fitness_Cyan_Light", (0.035, 0.62, 0.95), 0.24, 0.4, 3)
orbit_light = metal("Orbit_Quiet_Cyan", (0.035, 0.28, 0.44), 0.35, 0.1, 0.8)
surface = planet_material("Planet_Ice_Continents", (0.001, 0.004, 0.009), (0.045, 0.13, 0.23))


def sphere(name, center, radius, material, segments=64, rings=40):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=center)
    obj = place(bpy.context.object, name)
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def cylinder(name, center, radius, length, material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius, depth=length,
                                       location=center, rotation=(0, math.pi / 2, 0))
    obj = place(bpy.context.object, name)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new("Machined_Bevel", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 3
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.modifiers.new("Weighted_Normals", "WEIGHTED_NORMAL")
    return obj


def circle(name, center, radius, material, tube=0.008):
    bpy.ops.mesh.primitive_torus_add(major_segments=96, minor_segments=8,
                                    major_radius=radius, minor_radius=tube,
                                    location=center, rotation=(0, math.pi / 2, 0))
    obj = place(bpy.context.object, name)
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def orbit(name, radius, flatten, tilt, material, width=0.005):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = width
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(191)
    for index, point in enumerate(spline.points):
        angle = index * 2 * math.pi / 192
        point.co = (radius * math.cos(angle), radius * flatten * math.sin(angle),
                    math.sin(angle) * tilt, 1)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, curve)
    art.objects.link(obj)
    curve.materials.append(material)
    return obj


planet = sphere("PlanetCore", (0, 0, 0), 1.3, surface, 96, 64)
cylinder("CentralAxis", (0, -1.46, 0), 0.052, 5.1, bevel_metal)
cylinder("AxisLightTrace", (0, -1.507, 0.014), 0.009, 4.95, light)
for sign, side in [(-1, "Left"), (1, "Right")]:
    for index, radius in enumerate([0.78, 0.69, 0.58]):
        x = sign * (1.83 + index * 0.17)
        cylinder(side + "Plate" + str(index), (x, -1.46, 0), radius, 0.14, steel)
        circle(side + "PlateRim" + str(index), (x + sign * 0.072, -1.46, 0), radius - 0.024,
               bevel_metal, 0.012)
        if index != 1:
            circle(side + "PlateLight" + str(index), (x + sign * 0.074, -1.46, 0),
                   radius - 0.053, light, 0.009)
    cylinder(side + "Collar", (sign * 2.38, -1.46, 0), 0.105, 0.17, bevel_metal)

orbit("PrimaryOrbit", 2.65, 0.78, 0.32, light, 0.008)
orbit("SecondaryOrbit", 3.4, 0.76, -0.46, orbit_light, 0.003)
orbit("SatelliteOrbit", 4.15, 0.77, 0.65, orbit_light, 0.003)

for name, center, radius, color in [
    ("Training", (-2.8, 0.7, 0.72), 0.32, (0.09, 0.35, 0.55)),
    ("Nutrition", (2.7, 1.5, 0.75), 0.36, (0.16, 0.46, 0.32)),
    ("Recovery", (-2.5, -2.0, -0.55), 0.38, (0.28, 0.18, 0.46)),
    ("Body", (3.1, -0.8, -0.5), 0.35, (0.48, 0.32, 0.14)),
]:
    material = planet_material(name + "_Surface", (0.005, 0.009, 0.018), color)
    sphere(name + "_Moon", center, radius, material, 48, 32)


def aim(obj, target=(0, 0, 0)):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


for name, center, power, size, color in [
    ("Key_Softbox", (-3, -4, 5), 350, 4, (0.65, 0.83, 1)),
    ("Cyan_Rim", (2, 3, 2), 1900, 3, (0.18, 0.63, 1)),
    ("Lower_Fill", (1, -4, -2), 180, 3, (0.2, 0.55, 0.9)),
]:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    stage.objects.link(obj)
    obj.location = center
    aim(obj)

camera_data = bpy.data.cameras.new("Fitness_Preview_Camera")
camera = bpy.data.objects.new("Fitness_Preview_Camera", camera_data)
stage.objects.link(camera)
camera.location = (3.0, -11.8, 3.7)
camera_data.lens = 47
aim(camera)
scene.camera = camera

# Blender 5 uses compositor node groups rather than the legacy scene.node_tree.
compositor = bpy.data.node_groups.new("Fitness_Subtle_Bloom", "CompositorNodeTree")
scene.compositing_node_group = compositor
compositor.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
layers = compositor.nodes.new("CompositorNodeRLayers")
layers.scene = scene
glare = compositor.nodes.new("CompositorNodeGlare")
glare.inputs["Type"].default_value = "Fog Glow"
glare.inputs["Threshold"].default_value = 2.0
glare.inputs["Strength"].default_value = 0.3
output = compositor.nodes.new("NodeGroupOutput")
compositor.links.new(layers.outputs["Image"], glare.inputs["Image"])
compositor.links.new(glare.outputs["Image"], output.inputs["Image"])

for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.region_3d.view_perspective = "CAMERA"
        area.spaces.active.shading.type = "MATERIAL"
        area.spaces.active.shading.use_scene_world = True
        area.spaces.active.shading.use_scene_lights = True
        area.spaces.active.overlay.show_overlays = False

bpy.ops.wm.save_as_mainfile(filepath="E:/LifeOS-Art/fitness/fitness-art-study.blend")
print("Life OS Fitness study saved. Separate scene, independent material groups, no application changes.")
