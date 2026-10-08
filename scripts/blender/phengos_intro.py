"""Author the Phengos opening in a separate Blender scene; never clear user scenes.

Run in Blender or with: blender --background --python scripts/blender/phengos_intro.py
Output/cache lives on E:. Interactive UI stays in React, not baked into a video.
"""
import bpy
import json
import math
import random
from mathutils import Quaternion, Vector

OUT = "E:/LifeOS-Art/phengos"
FPS = 60
END = 511
scene = bpy.data.scenes.new("Phengos_Intro_v3")
if bpy.context.window:
    bpy.context.window.scene = scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, END
scene.eevee.taa_render_samples = 64
scene.render.image_settings.file_format = "PNG"
scene["contract"] = "5s approach then 3.5s rise; planets leave by camera movement, never opacity"
scene["palette"] = "near-black ink navy, restrained cobalt, icy atmospheric rim, clean white Phengos"

def enum_value(owner, key, value):
    values = [item.identifier for item in owner.bl_rna.properties[key].enum_items]
    if value not in values:
        raise ValueError(f"Unsupported {key}: {value}; valid: {values}")
    return value

def node_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes.clear()
    return material, material.node_tree

def emission(name, color, strength):
    material, tree = node_material(name)
    source = tree.nodes.new("ShaderNodeEmission")
    source.inputs["Color"].default_value = (*color, 1)
    source.inputs["Strength"].default_value = strength
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(source.outputs[0], output.inputs["Surface"])
    return material

def sphere(name, radius, position, material, segments=96):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=48, radius=radius, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj

world = bpy.data.worlds.new("Phengos_Quiet_Void")
world.use_nodes = True
background = next(node for node in world.node_tree.nodes if node.type == "BACKGROUND")
background.inputs["Color"].default_value = (0.0005, 0.0012, 0.0035, 1)
background.inputs["Strength"].default_value = 0.3
scene.world = world

# Broad low-frequency haze: no photo plane, granular nebula or noisy star wallpaper.
haze, tree = node_material("Phengos_Smooth_Cobalt_Depth")
noise = tree.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 1.6
noise.inputs["Detail"].default_value = 0
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.3
ramp.color_ramp.elements[0].color = (0.0001, 0.0003, 0.0012, 1)
ramp.color_ramp.elements[1].position = 0.85
ramp.color_ramp.elements[1].color = (0.0012, 0.0045, 0.016, 1)
source = tree.nodes.new("ShaderNodeEmission")
output = tree.nodes.new("ShaderNodeOutputMaterial")
tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], source.inputs["Color"])
tree.links.new(source.outputs[0], output.inputs["Surface"])
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 20, -95))
bpy.context.object.name = "Smooth_Infinite_Space"
bpy.context.object.data.materials.append(haze)

stars = emission("Phengos_Sparse_Stars", (0.22, 0.38, 0.65), 0.7)
rng = random.Random(1901)
vertices, faces = [], []
for index in range(650):
    x, y, z = rng.uniform(-75, 75), rng.uniform(-45, 90), rng.uniform(-80, -30)
    radius = rng.uniform(0.008, 0.025)
    start = len(vertices)
    vertices.extend([(x-radius, y-radius, z), (x+radius, y-radius, z), (x+radius, y+radius, z), (x-radius, y+radius, z)])
    faces.append((start, start+1, start+2, start+3))
mesh = bpy.data.meshes.new("Sparse_Star_Depths")
mesh.from_pydata(vertices, [], faces)
obj = bpy.data.objects.new("Sparse_Stars", mesh)
scene.collection.objects.link(obj)
obj.data.materials.append(stars)

earth_material = bpy.data.materials.new("Phengos_Earth_Night_Matte")
earth_material.use_nodes = True
tree = earth_material.node_tree
shader = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
shader.inputs["Roughness"].default_value = 0.95
shader.inputs["Specular IOR Level"].default_value = 0.12
texture = tree.nodes.new("ShaderNodeTexImage")
texture.image = bpy.data.images.load("E:/LifeOS-Art/textures/nasa-blue-marble-july.jpg", check_existing=True)
clouds = tree.nodes.new("ShaderNodeTexImage")
clouds.image = bpy.data.images.load("E:/LifeOS-Art/textures/sss-earth-clouds-8k.jpg", check_existing=True)
cloud_mix = tree.nodes.new("ShaderNodeMixRGB")
cloud_mix.blend_type = enum_value(cloud_mix, "blend_type", "SCREEN")
cloud_mix.inputs[0].default_value = 0.35
tree.links.new(texture.outputs["Color"], cloud_mix.inputs[1])
tree.links.new(clouds.outputs["Color"], cloud_mix.inputs[2])
tree.links.new(cloud_mix.outputs[0], shader.inputs["Base Color"])
surface_edge = tree.nodes.new("ShaderNodeFresnel")
surface_edge.inputs["IOR"].default_value = 1.025
edge_power = tree.nodes.new("ShaderNodeMath")
edge_power.operation = enum_value(edge_power, "operation", "POWER")
edge_power.inputs[1].default_value = 2.3
tree.links.new(surface_edge.outputs[0], edge_power.inputs[0])
surface_strength = tree.nodes.new("ShaderNodeMath")
surface_strength.operation = enum_value(surface_strength, "operation", "MULTIPLY")
surface_strength.inputs[1].default_value = 8
tree.links.new(edge_power.outputs[0], surface_strength.inputs[0])
night = tree.nodes.new("ShaderNodeTexImage")
night.image = bpy.data.images.load("E:/LifeOS-Art/textures/sss-earth-night-8k.jpg", check_existing=True)
# Clouds attenuate city emission rather than glowing like daylight on the night side.
cloud_shadow = tree.nodes.new("ShaderNodeInvert")
cloud_shadow.inputs["Fac"].default_value = 0.75
tree.links.new(clouds.outputs["Color"], cloud_shadow.inputs["Color"])
night_visible = tree.nodes.new("ShaderNodeMixRGB")
night_visible.blend_type = enum_value(night_visible, "blend_type", "MULTIPLY")
night_visible.inputs[0].default_value = 1
tree.links.new(night.outputs["Color"], night_visible.inputs[1])
tree.links.new(cloud_shadow.outputs["Color"], night_visible.inputs[2])
rim_color = tree.nodes.new("ShaderNodeMixRGB")
rim_color.blend_type = enum_value(rim_color, "blend_type", "MULTIPLY")
rim_color.inputs[0].default_value = 1
rim_color.inputs[2].default_value = (0.045, 0.28, 0.85, 1)
tree.links.new(surface_strength.outputs[0], rim_color.inputs[1])
emission_sum = tree.nodes.new("ShaderNodeMixRGB")
emission_sum.blend_type = enum_value(emission_sum, "blend_type", "ADD")
emission_sum.inputs[0].default_value = 0.55
tree.links.new(rim_color.outputs[0], emission_sum.inputs[1])
tree.links.new(night_visible.outputs[0], emission_sum.inputs[2])
tree.links.new(emission_sum.outputs[0], shader.inputs["Emission Color"])
shader.inputs["Emission Strength"].default_value = 1
earth = sphere("Earth_Horizon", 120, (0, -122.4, -40), earth_material, 256)
# Orient a real UV location (10E, 50N) into the visible European foreground.
uv = earth.data.uv_layers.active.data
def europe_uv_distance(index):
    return (uv[index].uv.x - 190/360)**2 + (uv[index].uv.y - 140/180)**2

closest_loop = min(range(len(uv)), key=europe_uv_distance)
local_direction = earth.data.vertices[earth.data.loops[closest_loop].vertex_index].co.normalized()
earth.rotation_mode = enum_value(earth, "rotation_mode", "QUATERNION")
earth_orientation = local_direction.rotation_difference(Vector((0, 0.98, 0.20)).normalized())
earth.rotation_quaternion = earth_orientation

atmosphere, tree = node_material("Phengos_Icy_Rim")
fresnel = tree.nodes.new("ShaderNodeFresnel")
fresnel.inputs["IOR"].default_value = 1.08
edge = tree.nodes.new("ShaderNodeMath")
edge.operation = enum_value(edge, "operation", "MULTIPLY")
edge.inputs[1].default_value = 0.8
tree.links.new(fresnel.outputs[0], edge.inputs[0])
light = tree.nodes.new("ShaderNodeEmission")
light.inputs["Color"].default_value = (0.025, 0.20, 0.6, 1)
light.inputs["Strength"].default_value = 2
transparent = tree.nodes.new("ShaderNodeBsdfTransparent")
mix = tree.nodes.new("ShaderNodeMixShader")
output = tree.nodes.new("ShaderNodeOutputMaterial")
tree.links.new(edge.outputs[0], mix.inputs[0])
tree.links.new(transparent.outputs[0], mix.inputs[1])
tree.links.new(light.outputs[0], mix.inputs[2])
tree.links.new(mix.outputs[0], output.inputs["Surface"])
rim = sphere("Earth_Thin_Atmosphere", 120.04, earth.location, atmosphere, 160)
rim.hide_render = True

for name, radius, position, path, color in [
    ("Distant_Cobalt_Planet", 2.6, (-17.82201767, -0.0265938, -15), "sss-neptune.jpg", (0.025, 0.12, 0.4, 1)),
    ("Distant_Banded_Planet", 4.1, (18.10551071, 5.93720388, -15), "sss-jupiter.jpg", (0.03, 0.09, 0.25, 1)),
]:
    material = bpy.data.materials.new(name + "_Surface")
    material.use_nodes = True
    tree = material.node_tree
    planet_shader = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    planet_shader.inputs["Roughness"].default_value = 0.9
    planet_shader.inputs["Specular IOR Level"].default_value = 0.15
    planet_tex = tree.nodes.new("ShaderNodeTexImage")
    planet_tex.image = bpy.data.images.load("E:/LifeOS-Art/textures/" + path, check_existing=True)
    tree.links.new(planet_tex.outputs["Color"], planet_shader.inputs["Base Color"])
    edge = tree.nodes.new("ShaderNodeFresnel")
    edge.inputs["IOR"].default_value = 1.1
    planet_shader.inputs["Emission Color"].default_value = color
    planet_rim = tree.nodes.new("ShaderNodeMixRGB")
    planet_rim.blend_type = enum_value(planet_rim, "blend_type", "MULTIPLY")
    planet_rim.inputs[0].default_value = 1
    planet_rim.inputs[2].default_value = color
    tree.links.new(edge.outputs[0], planet_rim.inputs[1])
    planet_detail = tree.nodes.new("ShaderNodeMixRGB")
    planet_detail.blend_type = enum_value(planet_detail, "blend_type", "MULTIPLY")
    planet_detail.inputs[0].default_value = 1
    planet_detail.inputs[2].default_value = (0.055, 0.055, 0.055, 1)
    tree.links.new(planet_tex.outputs["Color"], planet_detail.inputs[1])
    planet_sum = tree.nodes.new("ShaderNodeMixRGB")
    planet_sum.blend_type = enum_value(planet_sum, "blend_type", "ADD")
    planet_sum.inputs[0].default_value = 1
    tree.links.new(planet_rim.outputs[0], planet_sum.inputs[1])
    tree.links.new(planet_detail.outputs[0], planet_sum.inputs[2])
    tree.links.new(planet_sum.outputs[0], planet_shader.inputs["Emission Color"])
    planet_shader.inputs["Emission Strength"].default_value = 1
    planet = sphere(name, radius, position, material, 128)
    planet.rotation_euler = (math.radians(70), math.radians(20), 0)

light_data = bpy.data.lights.new("Hidden_Distant_Sun", "SUN")
light_data.energy = 2.5
light_data.color = (0.75, 0.86, 1)
light_data.angle = math.radians(0.53)
key = bpy.data.objects.new("Horizon_Key", light_data)
scene.collection.objects.link(key)
key.location = (0, -2000, -1800)
key.rotation_euler = (earth.location - key.location).to_track_quat('-Z', 'Y').to_euler()

camera_data = bpy.data.cameras.new("Phengos_Cinematic_Camera")
camera_data.lens = 30
camera_data.clip_end = 500
camera = bpy.data.objects.new("Phengos_Cinematic_Camera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera.rotation_euler = (0, 0, 0)

circle_material = emission("Phengos_Pure_White", (0.96, 0.985, 1), 8)
circle = sphere("Phengos", 0.43, (1.2, 0, 2), circle_material)

title_material, tree = node_material("Life_OS_Title_Fade")
source = tree.nodes.new("ShaderNodeEmission")
source.inputs["Color"].default_value = (0.8, 0.9, 1, 1)
source.inputs["Strength"].default_value = 1.3
transparent = tree.nodes.new("ShaderNodeBsdfTransparent")
mix = tree.nodes.new("ShaderNodeMixShader")
output = tree.nodes.new("ShaderNodeOutputMaterial")
tree.links.new(transparent.outputs[0], mix.inputs[1])
tree.links.new(source.outputs[0], mix.inputs[2])
tree.links.new(mix.outputs[0], output.inputs["Surface"])
font = bpy.data.fonts.load("C:/Windows/Fonts/segoeuil.ttf")
title = []
for letter, x in [("L", -3.6), ("I", -2.4), ("F", -1.2), ("E", 0), ("S", 2.4)]:
    data = bpy.data.curves.new("Life_OS_" + letter, "FONT")
    data.body, data.size, data.font = letter, 1.1, font
    data.align_x = enum_value(data, "align_x", "CENTER")
    obj = bpy.data.objects.new("Life_OS_" + letter, data)
    scene.collection.objects.link(obj)
    obj.location = (x, -0.4, 2)
    obj.data.materials.append(title_material)
    title.append(obj)

def smooth(value):
    t = min(1, max(0, value))
    return t*t*t*(t*(6*t-15)+10)

# Bake deterministic camera/object tracks; camera rises in world space, not a fade.
for frame in range(1, END+1):
    seconds = (frame-1)/FPS
    approach = smooth(seconds/5)
    center = smooth((seconds-3.8)/1.2)
    rise = smooth((seconds-5)/3.5)
    camera.location = (0, 22*rise, 25-5*approach)
    camera.keyframe_insert("location", frame=frame)
    circle.location = (1.2*(1-center), 22*rise, 2)
    circle.keyframe_insert("location", frame=frame)
    earth.rotation_quaternion = Quaternion((0, 1, 0), math.radians(seconds*0.15)) @ earth_orientation
    earth.keyframe_insert("rotation_quaternion", frame=frame)
    mix.inputs[0].default_value = smooth(seconds/1.2)*(1-center)
    mix.inputs[0].keyframe_insert("default_value", frame=frame)

# Blender 5 compositor node group: keep restrained glow only on highlights.
group = bpy.data.node_groups.new("Phengos_Cinematic_Finish", "CompositorNodeTree")
scene.compositing_node_group = group
group.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
layers = group.nodes.new("CompositorNodeRLayers")
glare = group.nodes.new("CompositorNodeGlare")
# Blender's dynamic Menu socket omits its enum items from RNA; verified in 5.2.2.
glare.inputs["Type"].default_value = "Fog Glow"
glare.inputs["Highlights Threshold"].default_value = 0.8
glare.inputs["Strength"].default_value = 0.8
glare.inputs["Size"].default_value = 0.55
glare.inputs["Tint"].default_value = (0.45, 0.7, 1, 1)
final = group.nodes.new("NodeGroupOutput")
group.links.new(layers.outputs["Image"], glare.inputs["Image"])
group.links.new(glare.outputs["Image"], final.inputs["Image"])

for frame, label in [(1, "Title approach"), (229, "Letters dissolve / circle centers"), (301, "Rise begins"), (END, "Only Phengos in deep space")]:
    scene.timeline_markers.new(label, frame=frame)
scene.frame_set(1)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/phengos-intro-v3.blend")
print(json.dumps({"saved": OUT + "/phengos-intro-v3.blend", "scene": scene.name, "frames": END, "fps": FPS, "view": scene.view_settings.view_transform, "objects": len(scene.objects)}))
