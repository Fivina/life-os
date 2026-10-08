"""Refine the live user's composition, preserving its opening camera and silhouettes.

Run through Blender MCP in the user-arranged scene. Original objects/materials and
animation actions stay intact; this creates a separate warm-lighting revision.
"""
import bpy
import json
import math

OUT = "E:/LifeOS-Art/phengos"
source = bpy.context.scene
assert source.camera, "The user's scene needs an active camera"
assert len(source.collection.objects) == len(source.objects), "Inspect nested collections before copying"
source.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/phengos-user-setup-before-warm.blend", copy=True)

scene = source.copy()
scene.name = "Phengos_User_Warm_v4"
scene.use_fake_user = True
copies = {}
for original in list(scene.objects):
    obj = original.copy()
    if original.data:
        obj.data = original.data.copy()
        for slot in obj.material_slots:
            if slot.material:
                slot.material = slot.material.copy()
    if obj.animation_data and obj.animation_data.action:
        obj.animation_data.action = obj.animation_data.action.copy()
    scene.collection.objects.link(obj)
    scene.collection.objects.unlink(original)
    copies[original.name] = obj
scene.camera = copies[source.camera.name]
scene.world = source.world.copy()
if source.compositing_node_group:
    scene.compositing_node_group = source.compositing_node_group.copy()
    for node in scene.compositing_node_group.nodes:
        if node.type == 'R_LAYERS':
            node.scene = scene
if bpy.context.window:
    bpy.context.window.scene = scene

def enum_value(owner, key, value):
    values = [item.identifier for item in owner.bl_rna.properties[key].enum_items]
    if value not in values:
        raise ValueError(f"Unsupported {key}: {value}; valid: {values}")
    return value

def fictional_surface(name, low, middle, high):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Roughness"].default_value = 0.97
    shader.inputs["Specular IOR Level"].default_value = 0.025
    shader.inputs["Metallic"].default_value = 0
    coordinates = tree.nodes.new("ShaderNodeTexCoord")
    terrain = tree.nodes.new("ShaderNodeTexNoise")
    terrain.noise_dimensions = enum_value(terrain, "noise_dimensions", "3D")
    terrain.noise_type = enum_value(terrain, "noise_type", "FBM")
    terrain.normalize = True
    terrain.inputs["Scale"].default_value = 4.5
    terrain.inputs["Detail"].default_value = 5
    terrain.inputs["Roughness"].default_value = 0.7
    terrain.inputs["Distortion"].default_value = 1.8
    tree.links.new(coordinates.outputs["Generated"], terrain.inputs["Vector"])
    palette = tree.nodes.new("ShaderNodeValToRGB")
    palette.color_ramp.elements[0].position = 0.22
    palette.color_ramp.elements[0].color = (*low, 1)
    palette.color_ramp.elements[1].position = 0.78
    palette.color_ramp.elements[1].color = (*high, 1)
    palette.color_ramp.elements.new(0.5).color = (*middle, 1)
    tree.links.new(terrain.outputs["Fac"], palette.inputs["Fac"])

    faults = tree.nodes.new("ShaderNodeTexVoronoi")
    faults.voronoi_dimensions = enum_value(faults, "voronoi_dimensions", "3D")
    faults.feature = enum_value(faults, "feature", "DISTANCE_TO_EDGE")
    faults.inputs["Scale"].default_value = 28
    tree.links.new(coordinates.outputs["Generated"], faults.inputs["Vector"])
    seams = tree.nodes.new("ShaderNodeValToRGB")
    seams.color_ramp.elements[0].position = 0.012
    seams.color_ramp.elements[0].color = (0.35, 0.35, 0.35, 1)
    seams.color_ramp.elements[1].position = 0.07
    seams.color_ramp.elements[1].color = (1, 1, 1, 1)
    tree.links.new(faults.outputs["Distance"], seams.inputs["Fac"])
    rock = tree.nodes.new("ShaderNodeMixRGB")
    rock.blend_type = enum_value(rock, "blend_type", "MULTIPLY")
    rock.inputs[0].default_value = 0.4
    tree.links.new(palette.outputs["Color"], rock.inputs[1])
    tree.links.new(seams.outputs["Color"], rock.inputs[2])
    tree.links.new(rock.outputs[0], shader.inputs["Base Color"])
    # Very low ambient readability, not a luminous outline or emissive lava.
    tree.links.new(rock.outputs[0], shader.inputs["Emission Color"])
    shader.inputs["Emission Strength"].default_value = 0.075
    detail = tree.nodes.new("ShaderNodeTexNoise")
    detail.noise_dimensions = enum_value(detail, "noise_dimensions", "3D")
    detail.noise_type = enum_value(detail, "noise_type", "FBM")
    detail.normalize = True
    detail.inputs["Scale"].default_value = 160
    detail.inputs["Detail"].default_value = 3
    tree.links.new(coordinates.outputs["Generated"], detail.inputs["Vector"])
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.04
    tree.links.new(detail.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(shader.outputs[0], output.inputs["Surface"])
    material["provenance"] = "Original procedural fictional geology; no Solar System planet photograph"
    return material

camera = scene.camera
camera_origin = camera.location.copy()
planet_records = []
for prefix, factor, name, colors in [
    ("Distant_Cobalt_Planet", 3, "Fictional_Dark_Red", ((0.006, 0.0015, 0.002), (0.10, 0.010, 0.009), (0.26, 0.035, 0.022))),
    ("Distant_Banded_Planet", 6, "Fictional_Dark_Orange", ((0.008, 0.004, 0.002), (0.13, 0.042, 0.012), (0.32, 0.105, 0.025))),
]:
    obj = next(o for o in scene.objects if o.name.startswith(prefix))
    before = {"location": list(obj.location), "scale": list(obj.scale), "dimensions": list(obj.dimensions)}
    obj.location = camera_origin + (obj.location - camera_origin) * factor
    obj.scale *= factor
    obj.data.materials.clear()
    obj.data.materials.append(fictional_surface(name, *colors))
    obj["depth_multiplier"] = factor
    obj["opening_angular_size_preserved"] = True
    planet_records.append({"object": obj.name, "original": before, "depth_multiplier": factor, "location": list(obj.location), "scale": list(obj.scale)})

earth = next(o for o in scene.objects if o.name.startswith("Earth_Horizon"))
tree = earth.data.materials[0].node_tree
shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
emission_sum = shader.inputs["Emission Color"].links[0].from_node
rim_color = emission_sum.inputs[1].links[0].from_node
rim_strength = rim_color.inputs[1].links[0].from_node
rim_color.inputs[2].default_value = (0.34, 0.42, 0.55, 1)
rim_strength.inputs[1].default_value = 5
emission_sum.inputs[0].default_value = 0.5
city_source = emission_sum.inputs[2].links[0].from_socket
warm_cities = tree.nodes.new("ShaderNodeMixRGB")
warm_cities.blend_type = enum_value(warm_cities, "blend_type", "MULTIPLY")
warm_cities.inputs[0].default_value = 1
warm_cities.inputs[2].default_value = (1, 0.72, 0.44, 1)
tree.links.new(city_source, warm_cities.inputs[1])
tree.links.new(warm_cities.outputs[0], emission_sum.inputs[2])

sun = next(o for o in scene.objects if o.type == 'LIGHT' and o.data.type == 'SUN')
sun.data.color = (1, 0.96, 0.9)
sun.data.energy = 2.0
sun.data.angle = math.radians(0.53)

# Place the sky behind the genuinely distant planets, not between them and camera.
sky = next(o for o in scene.objects if o.name.startswith("Smooth_Infinite_Space"))
sky.location = (0, 180, -900)
sky.scale *= 8
stars = next(o for o in scene.objects if o.name.startswith("Sparse_Stars"))
stars.scale *= 8
camera.data.clip_end = 2000
circle = next(o for o in scene.objects if o.name.split('.')[0] == "Phengos")

def smooth(value):
    t = min(1, max(0, value))
    return t*t*t*(t*(6*t-15)+10)

# Both share the same rise. Distant worlds have slower, physically coherent parallax.
for frame in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame)
    rise = smooth(((frame - 1) / scene.render.fps - 5) / 3.5)
    camera.location.y = camera_origin.y + 200 * rise
    camera.keyframe_insert("location", index=1, frame=frame)
    circle.location.y = camera.location.y
    circle.keyframe_insert("location", index=1, frame=frame)

glare = next(n for n in scene.compositing_node_group.nodes if n.type == 'GLARE')
glare.inputs["Tint"].default_value = (0.94, 0.96, 1, 1)
glare.inputs["Strength"].default_value = 0.6
scene["palette"] = "Warm city amber; subordinate matte red/orange worlds; whitish horizon; pure white Phengos"
scene["user_setup_source"] = source.name
scene["planet_transform_record"] = json.dumps(planet_records)
scene["rise_distance"] = 200
scene.frame_set(1)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/phengos-intro-v4-user-warm.blend")
print(json.dumps({"scene": scene.name, "saved": bpy.data.filepath, "planets": planet_records, "lens": camera.data.lens, "rise_distance": 200}))
