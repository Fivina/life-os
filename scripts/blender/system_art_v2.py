"""Authored cinematic scene, separate from the live application and original study."""
import bpy
import math
import random
import sys
from pathlib import Path
from mathutils import Vector, noise

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art_primitives as primitives
from art_primitives import art_aim, art_light, art_material, art_orbit, art_path, art_root, art_sphere
from home_art_geometry import build_home_art
from neural_art_geometry import build_neural_branches
from fitness_art_details import finish_fitness_faces
from fitness_art_surface import build_fitness_surface
from stellar_art_geometry import build_stellar_envelope
from scenery_art_geometry import build_scenery_depth
from art_composition import store_portrait_contract

random.seed(721)
scene = bpy.data.scenes.new("LifeOS_System_Composition_V2")
bpy.context.window.scene = scene
assets = bpy.data.collections.new("Art_V2_Assets")
scene.collection.children.link(assets)
staging = bpy.data.collections.new("Art_V2_Stage")
scene.collection.children.link(staging)
primitives.assets, primitives.staging = assets, staging
scene.render.engine = "CYCLES"
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.filepath = "E:/LifeOS-Art/system/system-art-v2"
scene.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("Art_V2_Void")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.001, 0.002, 0.004, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.02
scene.world = world


def atmospheric_edge(mat, color, strength=3, direction=None, floor=0.08):
    mat["art_rim_color"] = list(color)
    mat["art_rim_strength"] = strength
    tree = mat.node_tree
    shader = tree.nodes["Principled BSDF"]
    fresnel = tree.nodes.new("ShaderNodeFresnel")
    fresnel.name = "Art_Atmosphere_Fresnel"
    fresnel.inputs["IOR"].default_value = 1.15
    falloff = tree.nodes.new("ShaderNodeMath")
    falloff.operation = "POWER"
    falloff.inputs[1].default_value = 1.8
    multiply = tree.nodes.new("ShaderNodeMath")
    multiply.operation = "MULTIPLY"
    multiply.inputs[1].default_value = strength
    tree.links.new(fresnel.outputs[0], falloff.inputs[0])
    tree.links.new(falloff.outputs[0], multiply.inputs[0])
    emission_strength = multiply.outputs[0]
    if direction is not None:
        direction = Vector(direction).normalized()
        # Store the same world-space direction in portable glTF Y-up coordinates.
        mat["art_rim_direction"] = [direction.x, direction.z, -direction.y]
        mat["art_rim_floor"] = floor
        geometry = tree.nodes.new("ShaderNodeNewGeometry")
        dot = tree.nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        dot.inputs[1].default_value = direction
        tree.links.new(geometry.outputs["Normal"], dot.inputs[0])
        positive = tree.nodes.new("ShaderNodeMath")
        positive.operation = "MAXIMUM"
        positive.inputs[1].default_value = 0
        tree.links.new(dot.outputs["Value"], positive.inputs[0])
        taper = tree.nodes.new("ShaderNodeMath")
        taper.operation = "POWER"
        taper.inputs[1].default_value = 0.75
        tree.links.new(positive.outputs[0], taper.inputs[0])
        mask = tree.nodes.new("ShaderNodeMath")
        mask.operation = "MULTIPLY_ADD"
        mask.inputs[1].default_value = 1 - floor
        mask.inputs[2].default_value = floor
        tree.links.new(taper.outputs[0], mask.inputs[0])
        selective = tree.nodes.new("ShaderNodeMath")
        selective.operation = "MULTIPLY"
        tree.links.new(emission_strength, selective.inputs[0])
        tree.links.new(mask.outputs[0], selective.inputs[1])
        emission_strength = selective.outputs[0]
    tree.links.new(emission_strength, shader.inputs["Emission Strength"])
    shader.inputs["Emission Color"].default_value = (*color, 1)


def terrain(name, low, middle, high, scale=4, rim=(0.1, 0.35, 0.65),
            roughness_range=(0.28, 0.65), specular=0.5):
    mat = art_material(name, low, roughness=0.65, metallic=0.12)
    mat["art_role"] = "terrain"
    tree = mat.node_tree
    p = tree.nodes["Principled BSDF"]
    p.inputs["Specular IOR Level"].default_value = specular
    tex = tree.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 6
    tex.inputs["Roughness"].default_value = 0.8
    tex.inputs["Distortion"].default_value = 0.8
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    for element, pos, color in zip(ramp.color_ramp.elements, [0.30, 0.72], [low, high]):
        element.position, element.color = pos, (*color, 1)
    ramp.color_ramp.elements.new(0.52).color = (*middle, 1)
    tree.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    rough = tree.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = roughness_range[0]
    rough.inputs["To Max"].default_value = roughness_range[1]
    tree.links.new(tex.outputs["Fac"], rough.inputs["Value"])
    tree.links.new(rough.outputs["Result"], p.inputs["Roughness"])
    previous = None
    for size, distance, strength in [(25, 0.018, 0.38), (190, 0.003, 0.28)]:
        detail = tree.nodes.new("ShaderNodeTexNoise")
        detail.inputs["Scale"].default_value = size
        detail.inputs["Detail"].default_value = 3
        bump = tree.nodes.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value = distance
        bump.inputs["Strength"].default_value = strength
        tree.links.new(detail.outputs["Fac"], bump.inputs["Height"])
        if previous:
            tree.links.new(previous.outputs["Normal"], bump.inputs["Normal"])
        previous = bump
    tree.links.new(previous.outputs["Normal"], p.inputs["Normal"])
    if rim:
        atmospheric_edge(mat, rim)
    return mat


def rocky_sphere(name, radius, mat, root, center=(0, 0, 0), relief=0.013):
    obj = art_sphere(name, radius, mat, root, center, 80)
    for vertex in obj.data.vertices:
        direction = vertex.co.normalized()
        height = noise.noise(direction * 5.3) + 0.35 * noise.noise(direction * 21)
        vertex.co = direction * radius * (1 + relief * height)
    obj.data.update()
    return obj


cyan = art_material("V2_Cyan_Emitter", (0.04, 0.55, 0.92), 2.5)
violet = art_material("V2_Violet_Emitter", (0.29, 0.13, 0.65), 2.4)
amber = art_material("V2_Amber_Emitter", (0.57, 0.28, 0.068), 1.8)
green = art_material("V2_Living_Emitter", (0.08, 0.32, 0.26), 1.5)
quiet = art_material("V2_Quiet_System_Tracks", (0.018, 0.046, 0.077), 0.6)

# Granulation, a source-bound limb and surface-anchored plasma streamers.
core = art_root("SelfCore", (0, 0, 0.35))
star = art_material("V2_Stellar_Photosphere", (0.025, 0.25, 0.55), 7.5, 0.45, 0)
star["art_role"] = "photosphere"
tree = star.node_tree
tex = tree.nodes.new("ShaderNodeTexNoise")
tex.inputs["Scale"].default_value = 48
tex.inputs["Detail"].default_value = 3
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.36
ramp.color_ramp.elements[0].color = (0.002, 0.035, 0.1, 1)
ramp.color_ramp.elements[1].position = 0.64
ramp.color_ramp.elements[1].color = (0.28, 0.68, 1.0, 1)
tree.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
regions = tree.nodes.new("ShaderNodeTexNoise")
regions.inputs["Scale"].default_value = 4.2
regions.inputs["Detail"].default_value = 3
regions.inputs["Distortion"].default_value = 1.3
activity = tree.nodes.new("ShaderNodeValToRGB")
activity.color_ramp.elements[0].position = 0.36
activity.color_ramp.elements[0].color = (0.12, 0.12, 0.12, 1)
activity.color_ramp.elements[1].position = 0.61
activity.color_ramp.elements[1].color = (1, 1, 1, 1)
tree.links.new(regions.outputs["Fac"], activity.inputs["Fac"])
modulated = tree.nodes.new("ShaderNodeMixRGB")
modulated.blend_type = "MULTIPLY"
modulated.inputs[0].default_value = 1
tree.links.new(ramp.outputs["Color"], modulated.inputs[1])
tree.links.new(activity.outputs["Color"], modulated.inputs[2])
tree.links.new(modulated.outputs[0], tree.nodes["Principled BSDF"].inputs["Emission Color"])
star["art_rim_color"] = [0.025, 0.38, 1.0]
star["art_rim_strength"] = 8.0
fresnel = tree.nodes.new("ShaderNodeFresnel")
fresnel.inputs["IOR"].default_value = 1.15
falloff = tree.nodes.new("ShaderNodeMath")
falloff.operation = "POWER"
falloff.inputs[1].default_value = 1.8
strength = tree.nodes.new("ShaderNodeMath")
strength.operation = "MULTIPLY"
strength.inputs[1].default_value = 8
corona = tree.nodes.new("ShaderNodeEmission")
corona.inputs["Color"].default_value = (0.025, 0.38, 1, 1)
tree.links.new(fresnel.outputs[0], falloff.inputs[0])
tree.links.new(falloff.outputs[0], strength.inputs[0])
tree.links.new(strength.outputs[0], corona.inputs["Strength"])
add = tree.nodes.new("ShaderNodeAddShader")
tree.links.new(tree.nodes["Principled BSDF"].outputs[0], add.inputs[0])
tree.links.new(corona.outputs[0], add.inputs[1])
tree.links.new(add.outputs[0], tree.nodes["Material Output"].inputs["Surface"])
photosphere = art_sphere("Self_Granular_Star", 0.45, star, core, detail=64)
# The visual source surrounds its analytic light; it must not occlude that light.
photosphere.visible_shadow = False
photosphere["art_light_source"] = True
build_stellar_envelope(core)

calendar = art_root("Calendar", (-5.1, 0.8, 0.35))
mineral = terrain("V2_Chrono_Obsidian", (0.003, 0.003, 0.012), (0.026, 0.016, 0.065), (0.14, 0.095, 0.23),
                  5.2, (0.22, 0.12, 0.8), roughness_range=(0.58, 0.88), specular=0.12)
rocky_sphere("Chrono_Mineral_Body", 0.91, mineral, calendar, relief=0.018)
art_orbit("Chrono_Precision_Ring", 1.31, violet, calendar, 1, 0.06, 0.008)
clock_major = art_material("V21_Chrono_Major_Ticks", (0.35, 0.2, 0.72), 2.0)
clock_minor = art_material("V21_Chrono_Minor_Ticks", (0.13, 0.075, 0.28), 0.65)
for tick in range(96):
    angle = tick / 96 * math.tau
    major = tick % 8 == 0
    inner = 1.31 - (0.065 if major else 0.026)
    art_path("Chrono_Clock_Tick_" + str(tick),
             [(r * math.cos(angle), r * math.sin(angle), 0.06 * math.sin(angle)) for r in [inner, 1.31]],
             0.0045 if major else 0.0022, clock_major if major else clock_minor, calendar)
art_sphere("Chrono_Now", 0.078, cyan, calendar, (0.62, -1.17, -0.052), 20)
art_sphere("Chrono_Moon", 0.12, mineral, calendar, (-1.22, -0.99, 0.1), 24)

learning = art_root("Learning", (-0.2, 4.7, 1.0))
neural_surface = terrain("V2_Neural_Crystalline", (0.003, 0.001, 0.008), (0.014, 0.004, 0.03), (0.045, 0.012, 0.075), 7, None)
# Source-facing limb; terrain's other channels keep their existing bake contract.
atmospheric_edge(neural_surface, (0.32, 0.13, 0.8), 2.5, (0.08, -0.55, -0.84), floor=0.025)
neural_shader = neural_surface.node_tree.nodes["Principled BSDF"]
for channel in ("Roughness", "Normal"):
    for link in list(neural_shader.inputs[channel].links):
        neural_surface.node_tree.links.remove(link)
neural_shader.inputs["Roughness"].default_value = 0.24
neural_shader.inputs["Metallic"].default_value = 0
neural_shader.inputs["Transmission Weight"].default_value = 0.86
neural_shader.inputs["Specular IOR Level"].default_value = 0.035
neural_shader.inputs["IOR"].default_value = 1.04
rocky_sphere("Neural_Violet_Shell", 0.88, neural_surface, learning, relief=0.003)
build_neural_branches(learning)
art_orbit("Neural_Fine_Orbit", 1.25, violet, learning, 0.78, 0.27, 0.004)
art_sphere("Neural_Satellite", 0.09, neural_surface, learning, (-1.03, -0.68, 0.04), 24)

home = build_home_art(assets, (5.35, 2.0, 0.45))
art_orbit("Home_Resource_Ring", 1.46, amber, home, 0.82, 0.28, 0.004)
for index, angle in enumerate([0.1, 3.8]):
    art_sphere("Home_Resource_Node_" + str(index), 0.045, amber, home, (1.46 * math.cos(angle), 1.46 * 0.82 * math.sin(angle), 0.28 * math.sin(angle)), 16)

life = art_root("Life", (-2.8, -4.0, -0.25))
earth_mat = art_material("V2_Life_Blue_Marble", (0.02, 0.08, 0.08), 0, 0.68, 0.02)
earth_mat["art_role"] = "geographic"
earth_mat.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.12
earth_tex = earth_mat.node_tree.nodes.new("ShaderNodeTexImage")
earth_tex.image = bpy.data.images.load("E:/LifeOS-Art/textures/nasa-blue-marble-july.jpg", check_existing=True)
earth_mat.node_tree.links.new(earth_tex.outputs["Color"], earth_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
atmospheric_edge(earth_mat, (0.018, 0.28, 0.54), 3.5)
earth = art_sphere("Life_Geographic_Globe", 1.0, earth_mat, life, detail=80)
earth.rotation_euler = (math.radians(28), math.radians(-12), 3.0)
# Stylized cloud working layer; geography remains the NASA surface, not weather data.
cloud_mat = art_material("V6_Life_Cloud_Layer", (0.72, 0.82, 0.88), 0, 0.94, 0)
cloud_mat["art_role"] = "stylized_clouds"
cloud_mat.surface_render_method = "DITHERED"
cloud_mat.use_backface_culling = True
cloud_tree = cloud_mat.node_tree
cloud_noise = cloud_tree.nodes.new("ShaderNodeTexNoise")
cloud_noise.inputs["Scale"].default_value = 9
cloud_noise.inputs["Detail"].default_value = 6
cloud_noise.inputs["Roughness"].default_value = 0.72
cloud_noise.inputs["Distortion"].default_value = 2.2
coverage = cloud_tree.nodes.new("ShaderNodeValToRGB")
coverage.color_ramp.elements[0].position = 0.54
coverage.color_ramp.elements[0].color = (0, 0, 0, 1)
coverage.color_ramp.elements[1].position = 0.68
coverage.color_ramp.elements[1].color = (0.74, 0.74, 0.74, 1)
cloud_tree.links.new(cloud_noise.outputs["Fac"], coverage.inputs["Fac"])
cloud_tree.links.new(coverage.outputs["Color"], cloud_tree.nodes["Principled BSDF"].inputs["Alpha"])
clouds = art_sphere("Life_Cloud_Shell", 1.012, cloud_mat, life, detail=64)
clouds.rotation_euler = earth.rotation_euler
art_orbit("Life_Habitat_Track", 1.49, green, life, 0.72, 0.17, 0.004)
art_sphere("Life_Habitat_Moon", 0.115, mineral, life, (1.4, 0.37, 0.13), 24)

# Preserve pilot machining; refine its relationship with the sphere and shared view.
fitness = art_root("Fitness", (4.9, -3.55, -0.25))
fitness.scale = (0.67, 0.67, 0.67)
fitness.rotation_euler.y = -0.14
with bpy.data.libraries.load("E:/LifeOS-Art/fitness/fitness-art-study.blend", link=False) as (src, dst):
    dst.collections = ["Fitness_Asset"]
pilot = dst.collections[0]
for original in list(pilot.objects):
    if original.name.endswith("_Moon") or original.name.startswith(("SecondaryOrbit", "SatelliteOrbit")):
        continue
    obj = original.copy()
    obj.name = "Fitness_" + original.name
    assets.objects.link(obj)
    obj.parent = fitness
    if original.name.startswith(("Left", "Right", "CentralAxis", "AxisLightTrace")):
        obj.location.y = -1.16 if original.name != "AxisLightTrace" else -1.211
        obj.location.z = 0.61 if original.name != "AxisLightTrace" else 0.63
    if original.name == "PlanetCore":
        obj.data = original.data.copy()
        obj.data.materials.clear()
        surface = build_fitness_surface()
        atmospheric_edge(surface, (0.045, 0.45, 0.85))
        obj.data.materials.append(surface)
        for vertex in obj.data.vertices:
            d = vertex.co.normalized()
            vertex.co = d * 1.3 * (1 + 0.003 * noise.noise(d * 7.4) + 0.002 * noise.noise(d * 30))
    if original.name == "PrimaryOrbit":
        obj.data = original.data.copy()
        obj.data.materials.clear()
        obj.data.materials.append(art_material("V3_Fitness_Quiet_Orbit", (0.025, 0.2, 0.34), 1.0))
        obj.data.bevel_depth = 0.004

finish_fitness_faces(fitness)

scenery = art_root("Scenery", (0, 0, 0))
basalt = terrain("V2_Foreground_Basalt", (0.003, 0.0035, 0.004), (0.018, 0.019, 0.021), (0.055, 0.058, 0.063), 7, None)
basalt_shader = basalt.node_tree.nodes["Principled BSDF"]
for link in list(basalt_shader.inputs["Roughness"].links):
    basalt.node_tree.links.remove(link)
basalt_shader.inputs["Roughness"].default_value = 0.85
basalt_shader.inputs["Metallic"].default_value = 0
basalt_shader.inputs["Specular IOR Level"].default_value = 0.08
belt_basalt = terrain("V31_Receding_Mineral", (0.004, 0.008, 0.012), (0.018, 0.024, 0.033),
                      (0.07, 0.08, 0.10), 7, None, roughness_range=(0.35, 0.88), specular=0.35)
belt_basalt.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0
near_frame = build_scenery_depth(scenery, basalt, belt_basalt, quiet)
rocky_sphere("Foreground_Quiet_Crescent", 4.2, basalt, near_frame, (8.8, -8.0, -2.0), relief=0.024)

art_light("Art_Key", (-6, -4, 5.5), 400, (0.72, 0.82, 1), 4)
art_light("Art_Rim", (2, 7, 3), 400, (0.24, 0.48, 1), 3)
art_light("Art_Home_Warm_Fill", (8.5, 3.5, 3), 400, (1, 0.65, 0.33), 3)
strip = art_light("Art_Machining_Strip", (7.5, -6.5, 1.7), 100, (0.75, 0.86, 1), 1.8)
strip.data.shape = "RECTANGLE"
strip.data.size_y = 0.5
art_aim(strip, fitness.location)
lamp_data = bpy.data.lights.new("Self_Core_Light", "POINT")
lamp_data.energy, lamp_data.color, lamp_data.shadow_soft_size = 6250, (0.56, 0.76, 1), 0.55
core["art_source_power_version"] = 1
core["art_source_power_scale"] = lamp_data.energy / 2500
core["art_source_color_version"] = 1
core["art_source_color_linear"] = list(lamp_data.color)
lamp = bpy.data.objects.new("Self_Core_Light", lamp_data)
staging.objects.link(lamp)
lamp.location = (0, 0, 0.5)

camera_data = bpy.data.cameras.new("System_Composition_Camera")
camera = bpy.data.objects.new("System_Composition_Camera", camera_data)
staging.objects.link(camera)
camera.location = (0, -19.5, 12.5)
camera_data.lens = 43
art_aim(camera, (0, 0.1, 0))
camera_data.dof.use_dof = True
camera_data.dof.focus_distance = (camera.location - core.location).length
camera_data.dof.aperture_fstop = 0.32
camera["art_camera_optics_version"] = 1
camera["art_depth_focus_range"] = 10.0
camera["art_depth_bokeh_scale"] = 1.5
scene.camera = camera
rotation = camera.rotation_euler.to_quaternion()
bpy.ops.mesh.primitive_plane_add(size=2, location=camera.location + (rotation @ Vector((0, 0, -65))))
backdrop = primitives.art_place(bpy.context.object, "NonExport_Backplate", collection=staging)
backdrop["art_export"] = False
# The distant sky is composited after camera optics, like the preview's bitmap layer.
backdrop.hide_render = True
backdrop.rotation_euler = camera.rotation_euler
backdrop.scale = (65 * 36 / (2 * 43), 65 * 36 / (2 * 43) * 9 / 16, 1)
mat = bpy.data.materials.new("V2_Distant_Backplate")
mat.use_nodes = True
tree = mat.node_tree
tree.nodes.clear()
texture = tree.nodes.new("ShaderNodeTexImage")
texture.image = bpy.data.images.load("D:/Life OS/apps/web/public/art/system/deep-space-v1.png", check_existing=True)
emission = tree.nodes.new("ShaderNodeEmission")
emission.inputs["Strength"].default_value = 0.45
output = tree.nodes.new("ShaderNodeOutputMaterial")
tree.links.new(texture.outputs["Color"], emission.inputs["Color"])
tree.links.new(emission.outputs[0], output.inputs[0])
backdrop.data.materials.append(mat)

compositor = bpy.data.node_groups.new("V2_Selective_Light_Scatter", "CompositorNodeTree")
scene.compositing_node_group = compositor
compositor.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
layers = compositor.nodes.new("CompositorNodeRLayers")
layers.scene = scene
background = compositor.nodes.new("CompositorNodeImage")
background.image = texture.image
background.name = "Distant_Sky_Outside_Camera_Optics"
fit = compositor.nodes.new("CompositorNodeScale")
fit.inputs["Type"].default_value = "Render Size"
fit.inputs["Frame Type"].default_value = "Crop"
grade = compositor.nodes.new("ShaderNodeMix")
grade.data_type = "RGBA"
grade.blend_type = "MULTIPLY"
grade.inputs[0].default_value = 1
grade.inputs[7].default_value = (0.45, 0.45, 0.45, 1)
over = compositor.nodes.new("CompositorNodeAlphaOver")
compositor.links.new(background.outputs["Image"], fit.inputs["Image"])
compositor.links.new(fit.outputs["Image"], grade.inputs[6])
compositor.links.new(grade.outputs[2], over.inputs["Background"])
compositor.links.new(layers.outputs["Image"], over.inputs["Foreground"])
glow = compositor.nodes.new("CompositorNodeGlare")
glow.inputs["Type"].default_value = "Fog Glow"
glow.inputs["Threshold"].default_value = 0.6
glow.inputs["Strength"].default_value = 0.8
glow.inputs["Size"].default_value = 0.6
output = compositor.nodes.new("NodeGroupOutput")
compositor.links.new(over.outputs["Image"], glow.inputs["Image"])
compositor.links.new(glow.outputs["Image"], output.inputs["Image"])
store_portrait_contract(scene)
bpy.ops.wm.save_as_mainfile(filepath="E:/LifeOS-Art/system/system-art-v2.blend")
print("V2 authored scene saved; source procedural materials preserved for baking/export")
