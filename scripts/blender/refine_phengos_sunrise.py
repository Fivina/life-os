"""Create an isolated sunrise study from the live, user-arranged warm revision.

Run through Blender MCP. No source scene, object, material or action is overwritten.
Photographed CC0 height/roughness enrich fictional geology, not planet identity.
"""
import bpy
import math
import json
from mathutils import Vector

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.context.scene
assert source.name == 'Phengos_User_Warm_v4', 'Inspect the current setup before refining'
assert len(source.collection.objects) == len(source.objects), 'Nested collection copy needs inspection'
assert 'Phengos_Sunrise_v5' not in bpy.data.scenes, 'Do not overwrite an existing study'
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Sunrise_v5'
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
scene.compositing_node_group = source.compositing_node_group.copy()
for node in scene.compositing_node_group.nodes:
    if node.type == 'R_LAYERS':
        node.scene = scene
if bpy.context.window:
    bpy.context.window.scene = scene

def enum_value(owner, key, value):
    valid = [item.identifier for item in owner.bl_rna.properties[key].enum_items]
    assert value in valid, f'{key}: {value} not in {valid}'
    return value

def node(tree, kind, label):
    result = tree.nodes.new(kind)
    result.label = label
    return result

def math_node(tree, operation, label, second=0):
    result = node(tree, 'ShaderNodeMath', label)
    result.operation = enum_value(result, 'operation', operation)
    result.inputs[1].default_value = second
    return result

try:
    scene.render.engine = 'CYCLES'
except TypeError as error:
    raise RuntimeError('This scattering study requires the installed Cycles renderer') from error
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.cycles.adaptive_threshold = 0.025
scene.cycles.volume_bounces = 2
scene.cycles.max_bounces = 6
scene.cycles.volume_step_rate = 0.5
scene.render.resolution_percentage = 100

earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
tree = earth.data.materials[0].node_tree
shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
old_sum = shader.inputs['Emission Color'].links[0].from_node
city_source = old_sum.inputs[2].links[0].from_socket
# Only city lights emit. No Fresnel/emission substitute for the atmosphere.
tree.links.new(city_source, shader.inputs['Emission Color'])
shader.inputs['Emission Strength'].default_value = 0.45
shader.inputs['Roughness'].default_value = 0.9
cloud_image = next(n for n in tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'clouds' in n.image.filepath)
cloud_bump = node(tree, 'ShaderNodeBump', 'Subtle cloud relief')
cloud_bump.inputs['Strength'].default_value = 0.16
cloud_bump.inputs['Distance'].default_value = 0.018
tree.links.new(cloud_image.outputs['Color'], cloud_bump.inputs['Height'])
tree.links.new(cloud_bump.outputs['Normal'], shader.inputs['Normal'])

atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
for vertex in atmosphere.data.vertices:
    vertex.co = vertex.co.normalized() * 121.5
atmosphere.hide_render = False
material = bpy.data.materials.new('Phengos_Altitude_Scattering_v5')
material.use_nodes = True
atmosphere.data.materials.clear()
atmosphere.data.materials.append(material)
tree = material.node_tree
tree.nodes.clear()
coordinates = node(tree, 'ShaderNodeTexCoord', 'Local altitude, not screen-space rim')
radius = node(tree, 'ShaderNodeVectorMath', 'Radius')
radius.operation = enum_value(radius, 'operation', 'LENGTH')
tree.links.new(coordinates.outputs['Object'], radius.inputs[0])
altitude = math_node(tree, 'SUBTRACT', 'Altitude above Earth', 120)
tree.links.new(radius.outputs['Value'], altitude.inputs[0])
safe_altitude = math_node(tree, 'MAXIMUM', 'Avoid exponential overflow inside Earth', 0)
tree.links.new(altitude.outputs[0], safe_altitude.inputs[0])
falloff = math_node(tree, 'MULTIPLY', 'Negative inverse scale height', -4)
tree.links.new(safe_altitude.outputs[0], falloff.inputs[0])
exponential = math_node(tree, 'EXPONENT', 'Exponential density falloff')
tree.links.new(falloff.outputs[0], exponential.inputs[0])
above_surface = math_node(tree, 'GREATER_THAN', 'No atmosphere inside Earth', 0)
tree.links.new(altitude.outputs[0], above_surface.inputs[0])
bounded = math_node(tree, 'MULTIPLY', 'Bounded shell density')
tree.links.new(exponential.outputs[0], bounded.inputs[0])
tree.links.new(above_surface.outputs[0], bounded.inputs[1])
density = math_node(tree, 'MULTIPLY', 'Rayleigh density', 0.035)
tree.links.new(bounded.outputs[0], density.inputs[0])
rayleigh = node(tree, 'ShaderNodeVolumeScatter', 'Blue-white molecular scattering')
rayleigh.phase = enum_value(rayleigh, 'phase', 'RAYLEIGH')
rayleigh.inputs['Color'].default_value = (0.32, 0.53, 0.95, 1)
tree.links.new(density.outputs[0], rayleigh.inputs['Density'])
mie_density = math_node(tree, 'MULTIPLY', 'Weak aerosol density', 0.04)
tree.links.new(density.outputs[0], mie_density.inputs[0])
mie = node(tree, 'ShaderNodeVolumeScatter', 'Forward sunrise scatter')
mie.phase = enum_value(mie, 'phase', 'HENYEY_GREENSTEIN')
mie.inputs['Color'].default_value = (0.98, 0.95, 0.87, 1)
mie.inputs['Anisotropy'].default_value = 0.65
tree.links.new(mie_density.outputs[0], mie.inputs['Density'])
combined = node(tree, 'ShaderNodeAddShader', 'Molecules plus aerosols')
tree.links.new(rayleigh.outputs[0], combined.inputs[0])
tree.links.new(mie.outputs[0], combined.inputs[1])
output = node(tree, 'ShaderNodeOutputMaterial', 'Volume only; no luminous surface')
tree.links.new(combined.outputs[0], output.inputs['Volume'])

height_image = bpy.data.images.load(OUT + '/textures/aerial_rocks_02_disp_4k.exr', check_existing=True)
rough_image = bpy.data.images.load(OUT + '/textures/aerial_rocks_02_rough_2k.jpg', check_existing=True)
for image in (height_image, rough_image):
    image.colorspace_settings.name = enum_value(image.colorspace_settings, 'name', 'Non-Color')

camera = scene.camera
origin = camera.location.copy()
planet_records = []
for prefix in ('Distant_Cobalt_Planet', 'Distant_Banded_Planet'):
    obj = next(o for o in scene.objects if o.name.startswith(prefix))
    obj.location = origin + (obj.location - origin) * 2
    obj.scale *= 1.6
    tree = obj.data.materials[0].node_tree
    shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Emission Strength'].default_value = 0.008
    coordinates = next(n for n in tree.nodes if n.type == 'TEX_COORD')
    detail_coords = node(tree, 'ShaderNodeVectorMath', 'Photographed rock scale')
    detail_coords.operation = enum_value(detail_coords, 'operation', 'SCALE')
    detail_coords.inputs['Scale'].default_value = 2.5
    tree.links.new(coordinates.outputs['Generated'], detail_coords.inputs[0])
    maps = []
    for image in (height_image, rough_image):
        texture = node(tree, 'ShaderNodeTexImage', 'CC0 Poly Haven ' + image.name)
        texture.image = image
        texture.projection = enum_value(texture, 'projection', 'BOX')
        texture.projection_blend = 0.35
        tree.links.new(detail_coords.outputs['Vector'], texture.inputs['Vector'])
        maps.append(texture)
    old_bump = next(n for n in tree.nodes if n.type == 'BUMP')
    old_bump.inputs['Strength'].default_value = 0.08
    photographed = node(tree, 'ShaderNodeBump', 'Photographed fractured stone relief')
    photographed.inputs['Strength'].default_value = 0.26
    photographed.inputs['Distance'].default_value = 0.035
    tree.links.new(maps[0].outputs['Color'], photographed.inputs['Height'])
    tree.links.new(old_bump.outputs['Normal'], photographed.inputs['Normal'])
    tree.links.new(photographed.outputs['Normal'], shader.inputs['Normal'])
    roughness = node(tree, 'ShaderNodeValToRGB', 'Matte natural roughness')
    roughness.color_ramp.elements[0].color = (0.65, 0.65, 0.65, 1)
    roughness.color_ramp.elements[1].color = (0.98, 0.98, 0.98, 1)
    tree.links.new(maps[1].outputs['Color'], roughness.inputs['Fac'])
    tree.links.new(roughness.outputs[0], shader.inputs['Roughness'])
    obj['surface_source'] = 'Poly Haven aerial_rocks_02, Rob Tuytel, CC0; height/roughness only'
    obj['opening_angular_size_preserved'] = False
    planet_records.append({'name':obj.name, 'location':list(obj.location), 'dimensions':list(obj.dimensions), 'angular_scale_vs_v4':0.8})

# A finite-distance source gives each world a different crescent angle. Keep
# the legacy directional light disabled; its location cannot change illumination.
sun = next(o for o in scene.objects if o.type == 'LIGHT' and o.data.type == 'SUN')
sun.data.energy = 0
sun.data.color = (1, 0.97, 0.92)
sun.data.angle = math.radians(0.53)
sun_point_data = bpy.data.lights.new('Phengos_Finite_Sun_Light', enum_value(sun.data, 'type', 'POINT'))
sun_point_data.energy = 80000000
sun_point_data.color = (1, 0.97, 0.92)
sun_point_data.shadow_soft_size = 3.7
sun_point = bpy.data.objects.new('Phengos_Finite_Sun_Light', sun_point_data)
scene.collection.objects.link(sun_point)
disc_mesh = bpy.data.meshes.new('Distant_Sun_Disc_Mesh')
vertices = [(0, 0, 0)]
for index in range(96):
    angle = index * 2 * math.pi / 96
    vertices.append((3.7 * math.cos(angle), 3.7 * math.sin(angle), 0))
faces = []
for index in range(96):
    faces.append((0, index + 1, (index + 1) % 96 + 1))
disc_mesh.from_pydata(vertices, [], faces)
disc = bpy.data.objects.new('Distant_White_Sun_v5', disc_mesh)
scene.collection.objects.link(disc)
sun_material = bpy.data.materials.new('Phengos_Distant_Sun_White')
sun_material.use_nodes = True
tree = sun_material.node_tree
shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
shader.inputs['Base Color'].default_value = (1, 0.97, 0.92, 1)
shader.inputs['Emission Color'].default_value = (1, 0.97, 0.92, 1)
shader.inputs['Emission Strength'].default_value = 15
disc.data.materials.append(sun_material)
circle = next(o for o in scene.objects if o.name.split('.')[0] == 'Phengos')

def smooth(value):
    t = min(1, max(0, value))
    return t*t*t*(t*(6*t-15)+10)

for frame in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame)
    seconds = (frame - 1) / scene.render.fps
    approach = smooth(seconds / 5)
    rise = smooth((seconds - 5) / 3.5)
    camera.location.y = origin.y + 350 * rise
    camera.keyframe_insert('location', index=1, frame=frame)
    circle.location.y = camera.location.y
    circle.keyframe_insert('location', index=1, frame=frame)
    disc.location = (90, -38 + 10 * approach, -860)
    disc.keyframe_insert('location', frame=frame)
    sun_point.location = disc.location
    sun_point.keyframe_insert('location', frame=frame)
    sun.location = disc.location
    direction = Vector((0, -3, -45)) - disc.location
    sun.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    sun.keyframe_insert('rotation_euler', frame=frame)

glare = next(n for n in scene.compositing_node_group.nodes if n.type == 'GLARE')
glare.inputs['Strength'].default_value = 0.35
scene['sunrise_design'] = 'Bounded exponential Rayleigh + weak forward scatter; no emissive Earth rim'
scene['user_setup_source'] = source.name
scene['rise_distance'] = 350
scene['planet_transform_record'] = json.dumps(planet_records)
scene['publication_status'] = 'Composition study only; movie/browser not yet replaced'
scene.frame_set(1)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v5-sunrise.blend')
print(json.dumps({'scene':scene.name, 'saved':bpy.data.filepath, 'planets':planet_records, 'renderer':scene.render.engine, 'samples':scene.cycles.samples}))
