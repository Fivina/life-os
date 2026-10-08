"""Independent reflected-light studies; preserve the approved horizon and camera."""
import bpy
import json
import math
from mathutils import Vector

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.context.scene
assert source.name == 'Phengos_Curved_Source_v7', 'Inspect the live source before editing'
assert len(source.collection.objects) == len(source.objects), 'Inspect nested collections first'
assert 'Phengos_Planet_Depth_v8' not in bpy.data.scenes, 'Do not overwrite an existing study'
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Planet_Depth_v8'
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
            collection = bpy.data.collections.new(receivers.name + '_v8')
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
for obj in scene.objects:
    if obj.type == 'LIGHT' and obj.get('rig_role') == 'planet_detail':
        obj.data.energy = 0

def enum_value(owner, key, value):
    valid = [item.identifier for item in owner.bl_rna.properties[key].enum_items]
    assert value in valid, f'{key}: {value} not in {valid}'
    return value

reference = next(o for o in scene.objects if o.type == 'LIGHT')
records = []
for prefix, side, key_angle, elevation, irradiance, key_color, fill_irradiance in (
    ('Distant_Banded_Planet', -1, 88, 0.22, 2.5, (0.88, 0.94, 1), 0.12),
    ('Distant_Cobalt_Planet', 1, 118, -0.18, 1.8, (1, 0.95, 0.88), 0.07),
):
    planet = next(o for o in scene.objects if o.name.startswith(prefix))
    radius = max(planet.dimensions) / 2
    view = (scene.camera.location - planet.location).normalized()
    camera_up = scene.camera.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    right = camera_up.cross(view).normalized()
    up = view.cross(right).normalized()
    receivers = bpy.data.collections.new('Phengos_v8_' + prefix + '_Receivers')
    receivers.objects.link(planet)
    material = planet.data.materials[0]
    shader = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Emission Strength'].default_value = 0
    for role, angle, height, flux, color, size in (
        ('key', key_angle, elevation, irradiance, key_color, radius * 0.65),
        ('fill', 38, -elevation, fill_irradiance, (0.6, 0.72, 0.9), radius * 2.8),
    ):
        radians = math.radians(angle)
        lateral = (right * side + up * height).normalized()
        direction = view * math.cos(radians) + lateral * math.sin(radians)
        distance = radius * 6
        energy = 4 * math.pi * distance * distance * flux
        name = 'Planet_Depth_v8_' + prefix + '_' + role
        data = bpy.data.lights.new(name, enum_value(reference.data, 'type', 'AREA'))
        data.shape = enum_value(data, 'shape', 'DISK')
        data.size = size
        data.normalize = True
        data.energy = energy
        data.color = color
        lamp = bpy.data.objects.new(name, data)
        scene.collection.objects.link(lamp)
        lamp.location = planet.location + direction * distance
        lamp.rotation_euler = (planet.location - lamp.location).to_track_quat('-Z', 'Y').to_euler()
        lamp.light_linking.receiver_collection = receivers
        lamp['rig_role'] = 'independent_planet_' + role
        lamp['planet_depth_base_energy'] = energy
        lamp['nominal_phase_angle'] = angle
        lamp['camera_side'] = 'left' if side < 0 else 'right'
        records.append({'name':name, 'role':role, 'side':lamp['camera_side'],
                        'phase_angle':angle, 'energy':energy, 'receiver':planet.name,
                        'color':list(color), 'elevation':height})

scene['planet_depth_strength'] = 1.0
scene['planet_depth_rig_record'] = json.dumps(records)
scene['lighting_experiment'] = 'Independent asymmetric planet reflection rigs; unchanged curved horizon'
scene['user_setup_source'] = source.name
scene['publication_status'] = 'Planet depth still study; no movie/browser replacement'
scene.frame_set(301)
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v8-planet-depth.blend')
print(json.dumps({'scene':scene.name, 'rig':records, 'geometry_and_camera_unchanged':True}))
