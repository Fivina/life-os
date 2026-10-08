"""450 km horizon study with regional satellite lights and finer spherical boundaries."""
import bpy
import json
import math
from mathutils import Vector

OUT = 'E:/LifeOS-Art/phengos'
EARTH_KM = 6371.0084
RADIUS = 480.0
ALTITUDE_KM = 450.0
source = bpy.context.scene
assert source.name == 'Phengos_Scale_Study_v9'
assert len(source.collection.objects) == len(source.objects)
assert 'Phengos_Natural_Horizon_v10' not in bpy.data.scenes
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Natural_Horizon_v10'
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
receiver_copies = {}
for original in source.objects:
    receivers = original.light_linking.receiver_collection
    if receivers:
        if receivers.name not in receiver_copies:
            collection = bpy.data.collections.new(receivers.name + '_v10')
            for receiver in receivers.objects:
                assert receiver.name in copies
                collection.objects.link(copies[receiver.name])
            receiver_copies[receivers.name] = collection
        copies[original.name].light_linking.receiver_collection = receiver_copies[receivers.name]
scene.camera = copies[source.camera.name]
scene.world = source.world.copy()
scene.compositing_node_group = source.compositing_node_group.copy()
for node in scene.compositing_node_group.nodes:
    if node.type == 'R_LAYERS':
        node.scene = scene
if bpy.context.window:
    bpy.context.window.scene = scene

def enum_value(owner, key, value):
    valid = [i.identifier for i in owner.bl_rna.properties[key].enum_items]
    assert value in valid
    return value

def new_node(tree, kind, label):
    node = tree.nodes.new(kind)
    node.label = label
    return node

earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
old_center = earth.location.copy()
factor = RADIUS / earth['scene_radius']
camera_horizon = Vector((0, 0, 20))
distance = RADIUS * (1 + ALTITUDE_KM / EARTH_KM)
center_angle = math.radians(-5) - math.asin(RADIUS / distance)
center = camera_horizon + Vector((0, distance * math.sin(center_angle),
                                 -distance * math.cos(center_angle)))

# Smooth geometric boundaries prevent large sphere facets from shaping the limb.
for obj, radius, segments, rings in ((earth, RADIUS, 512, 256),
                                    (atmosphere, RADIUS * (1 + 80 / EARTH_KM), 256, 256)):
    materials = list(obj.data.materials)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius)
    temporary = bpy.context.object
    obj.data = temporary.data
    bpy.data.objects.remove(temporary, do_unlink=True)
    for material in materials:
        obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.location = center
earth['scene_radius'] = RADIUS

origin = scene.camera.location.copy()
records = json.loads(source['scale_record'])
for record in records:
    planet = copies[record['object']]
    old_location = planet.location.copy()
    planet.location = origin + (old_location - origin) * factor
    planet.scale *= factor
    planet['scene_radius'] *= factor
    for light in scene.objects:
        if light.type != 'LIGHT' or 'planet_depth_base_energy' not in light:
            continue
        receivers = light.light_linking.receiver_collection
        if receivers and planet.name in receivers.objects:
            light.location = planet.location + (light.location - old_location) * factor
            light.data.size *= factor
            light['planet_depth_base_energy'] *= factor * factor
            light.data.energy = light['planet_depth_base_energy'] * scene['planet_depth_strength']
    record['object'] = planet.name
    record['radius'] *= factor
    record['opening_camera_distance'] *= factor
    record['position'] = list(planet.location)
scene['scale_record'] = json.dumps(records)

emitter = next(o for o in scene.objects if o.get('emitter_role') == 'continuous_curved_horizon')
emitter.location = center + (emitter.location - old_center) * factor
for vertex in emitter.data.vertices:
    vertex.co *= factor
emitter.data.update()
emitter['source_radius'] *= factor
emission = next(n for n in emitter.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
emission.inputs['Strength'].default_value = 500
scene['curved_source_strength'] = 500

for node in atmosphere.data.materials[0].node_tree.nodes:
    if node.type == 'MATH':
        if node.label == 'Altitude above Earth':
            node.inputs[1].default_value = RADIUS
        elif node.label == 'Negative inverse scale height':
            node.inputs[1].default_value = -1 / (RADIUS * 8 / EARTH_KM)
        elif node.label == 'Rayleigh density':
            node.inputs[1].default_value = 0.006
    elif node.type == 'VOLUME_SCATTER' and node.label == 'Blue-white molecular scattering':
        node.inputs['Color'].default_value = (0.22, 0.43, 0.95, 1)

# Fine city radiance from a regional tile, with the existing global map outside it.
tree = earth.data.materials[0].node_tree
shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
night = next(n for n in tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'night' in n.image.filepath)
clouds = next(n for n in tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'clouds' in n.image.filepath)
for image_node in (night, clouds):
    image_node.interpolation = enum_value(image_node, 'interpolation', 'Cubic')
uv = new_node(tree, 'ShaderNodeTexCoord', 'Spherical geographic UV')
mapping = new_node(tree, 'ShaderNodeVectorMath', 'Regional lon/lat bounds 2..40E 35..62N')
mapping.operation = enum_value(mapping, 'operation', 'MULTIPLY_ADD')
mapping.inputs[1].default_value = (360 / 38, 180 / 27, 1)
mapping.inputs[2].default_value = (-182 / 38, -125 / 27, 0)
tree.links.new(uv.outputs['UV'], mapping.inputs[0])
regional = new_node(tree, 'ShaderNodeTexImage', 'NASA VIIRS night lights, bounded regional 8K')
regional.image = bpy.data.images.load(OUT + '/textures/nasa-black-marble-regional-8k.png', check_existing=True)
regional.interpolation = enum_value(regional, 'interpolation', 'Cubic')
regional.extension = enum_value(regional, 'extension', 'CLIP')
tree.links.new(mapping.outputs['Vector'], regional.inputs['Vector'])
global_gray = new_node(tree, 'ShaderNodeRGBToBW', 'Fallback global city radiance')
tree.links.new(night.outputs['Color'], global_gray.inputs['Color'])
detail = new_node(tree, 'ShaderNodeMixRGB', 'Regional satellite detail with global fallback')
detail.blend_type = enum_value(detail, 'blend_type', 'MIX')
tree.links.new(regional.outputs['Alpha'], detail.inputs[0])
tree.links.new(global_gray.outputs[0], detail.inputs[1])
tree.links.new(regional.outputs['Color'], detail.inputs[2])
city_tint = new_node(tree, 'ShaderNodeMixRGB', 'Restrained warm settlement light')
city_tint.blend_type = enum_value(city_tint, 'blend_type', 'MULTIPLY')
city_tint.inputs[0].default_value = 1
city_tint.inputs[2].default_value = (1, 0.63, 0.32, 1)
tree.links.new(detail.outputs[0], city_tint.inputs[1])
cloud_shadow = new_node(tree, 'ShaderNodeInvert', 'Clouds attenuate city radiance')
cloud_shadow.inputs[0].default_value = 0.6
tree.links.new(clouds.outputs['Color'], cloud_shadow.inputs['Color'])
city_visible = new_node(tree, 'ShaderNodeMixRGB', 'Cities underneath cloud cover')
city_visible.blend_type = enum_value(city_visible, 'blend_type', 'MULTIPLY')
city_visible.inputs[0].default_value = 1
tree.links.new(city_tint.outputs[0], city_visible.inputs[1])
tree.links.new(cloud_shadow.outputs[0], city_visible.inputs[2])
tree.links.new(city_visible.outputs[0], shader.inputs['Emission Color'])
shader.inputs['Emission Strength'].default_value = 1.1
for link in list(shader.inputs['Normal'].links):
    tree.links.remove(link)
shader.inputs['Roughness'].default_value = 0.82

# Dim cool fill reveals clouds/land without turning the dark face into daylight.
reference = next(o for o in scene.objects if o.type == 'LIGHT')
data = bpy.data.lights.new('Phengos_Night_Cloud_Fill_v10', enum_value(reference.data, 'type', 'AREA'))
data.shape = enum_value(data, 'shape', 'DISK')
data.size = RADIUS * 2
data.normalize = True
data.color = (0.22, 0.38, 0.65)
data.energy = 4 * math.pi * (RADIUS * 3) ** 2 * 0.02
fill = bpy.data.objects.new('Phengos_Night_Cloud_Fill_v10', data)
scene.collection.objects.link(fill)
fill.location = center + (camera_horizon - center).normalized() * RADIUS * 3
fill.rotation_euler = (center - fill.location).to_track_quat('-Z', 'Y').to_euler()
receivers = bpy.data.collections.new('Phengos_v10_Earth_Cloud_Fill_Receivers')
receivers.objects.link(earth)
fill.light_linking.receiver_collection = receivers
fill['rig_role'] = 'restrained_night_surface_fill'

for prefix in ('Sparse_Stars', 'Smooth_Infinite_Space'):
    obj = next(o for o in scene.objects if o.name.startswith(prefix))
    obj.location = origin + (obj.location - origin) * factor
    obj.scale *= factor
scene.camera.data.clip_end *= factor
circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
for obj in (scene.camera, circle):
    action = obj.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(obj.animation_data.action_slot)
            if bag:
                for curve in bag.fcurves:
                    if curve.data_path == 'location' and curve.array_index == 1:
                        for point in curve.keyframe_points:
                            point.co.y *= factor
                            point.handle_left.y *= factor
                            point.handle_right.y *= factor
                        curve.update()

glare = next(n for n in scene.compositing_node_group.nodes if n.type == 'GLARE')
glare.inputs['Strength'].default_value = 0.18
glare.inputs['Highlights Threshold'].default_value = 1.0
scene.cycles.volume_biased = False
scene.cycles.adaptive_threshold = 0.008
scene.cycles.samples = 192
scene.cycles.use_denoising = True
scene['shared_scale_km_per_unit'] = EARTH_KM / RADIUS
scene['horizon_camera_altitude_km'] = ALTITUDE_KM
scene['atmospheric_scale_height_km'] = 8.0
scene['surface_detail_source'] = 'NASA Black Marble C1 500m regional crop; old global fallback'
scene['user_setup_source'] = source.name
scene['publication_status'] = 'Natural horizon still study; not installed in browser'
scene.frame_set(301)
actual_altitude = ((scene.camera.location - earth.location).length - RADIUS) * EARTH_KM / RADIUS
assert abs(actual_altitude - ALTITUDE_KM) < 0.01
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v10-natural-horizon.blend')
print(json.dumps({'scene':scene.name,'radius':RADIUS,'center':list(center),
                  'altitude_km':actual_altitude,'city_texture_size':list(regional.image.size),
                  'atmosphere_vertices':len(atmosphere.data.vertices),
                  'earth_vertices':len(earth.data.vertices),'objects':len(scene.objects)}))
