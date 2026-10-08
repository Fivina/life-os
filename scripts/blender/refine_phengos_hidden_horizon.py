"""Isolate the user's hidden-source, horizon-wide cinematic lighting experiment."""
import bpy
import json
import math
from mathutils import Vector, Quaternion

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.context.scene
assert source.name == 'Phengos_Sunrise_v5', 'Inspect live composition first'
assert len(source.collection.objects) == len(source.objects), 'Nested collections need inspection'
assert 'Phengos_Hidden_Horizon_v6' not in bpy.data.scenes, 'Existing lighting study must not be overwritten'
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Hidden_Horizon_v6'
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
    assert value in valid, f'Unsupported {key}: {value}; valid {valid}'
    return value

# Lamps themselves are not visible geometry. Preserve the previous source but
# disable its illumination and hide the disc, rather than deleting either.
for obj in scene.objects:
    if obj.type == 'LIGHT':
        obj.data.energy = 0
    if obj.name.startswith('Distant_White_Sun'):
        obj.hide_render = True
        obj.hide_viewport = True

earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
earth_receivers = bpy.data.collections.new('Phengos_v6_Atmosphere_Receivers')
earth_receivers.objects.link(atmosphere)

def area_light(name, location, target, energy, size, receivers, color):
    reference = next(o for o in scene.objects if o.type == 'LIGHT')
    data = bpy.data.lights.new(name, enum_value(reference.data, 'type', 'AREA'))
    data.shape = enum_value(data, 'shape', 'RECTANGLE')
    data.size = size
    data.size_y = size * 0.35
    data.energy = energy
    data.color = color
    data.normalize = True
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    obj.light_linking.receiver_collection = receivers
    obj['rig_base_energy'] = energy
    obj['rig_role'] = 'horizon' if receivers == earth_receivers else 'planet_detail'
    return obj

records = []
for index, x in enumerate((-64, -32, 0, 32, 64)):
    target_x = x * 0.6
    location = (x, 14 - x*x / 240, -120)
    target = (target_x, -3 - target_x*target_x / 240, -33)
    energy = 140000 if index == 2 else 110000
    lamp = area_light('Horizon_Wide_v6_' + str(index), location, target, energy, 34,
                      earth_receivers, (0.95, 0.97, 1))
    records.append({'name':lamp.name, 'role':'horizon', 'energy':energy, 'location':list(lamp.location)})

# Side/back sources use camera-relative phase angles, not arbitrary Euler
# angles. Link each to its world only, retaining Earth's unlit night side.
for prefix in ('Distant_Cobalt_Planet', 'Distant_Banded_Planet'):
    planet = next(o for o in scene.objects if o.name.startswith(prefix))
    receivers = bpy.data.collections.new('Phengos_v6_' + prefix + '_Receivers')
    receivers.objects.link(planet)
    radius = max(planet.dimensions) / 2
    to_camera = (scene.camera.location - planet.location).normalized()
    for index, angle in enumerate((100, 120, 130)):
        side = 1 if prefix == 'Distant_Cobalt_Planet' else -1
        direction = Quaternion(Vector((0, 1, 0)), math.radians(angle * side)) @ to_camera
        direction.y -= 0.15
        direction.normalize()
        distance = radius * 5
        energy = 4 * math.pi * distance*distance * (1.4 if index else 2.4)
        location = planet.location + direction * distance
        lamp = area_light('Planet_Graze_v6_' + prefix + '_' + str(angle), location,
                          planet.location, energy, radius * 1.3, receivers, (1, 0.94, 0.85))
        lamp['phase_angle_degrees'] = angle
        records.append({'name':lamp.name, 'role':'planet_detail', 'energy':energy, 'phase_angle':angle})

scene['lighting_experiment'] = 'Hidden horizon-wide sources; linked 100/120/130-degree planetary grazing lights'
scene['rig_strength'] = 1.6
for obj in scene.objects:
    if obj.type == 'LIGHT' and 'rig_base_energy' in obj:
        obj.data.energy = obj['rig_base_energy'] * scene['rig_strength']
scene['lighting_rig_record'] = json.dumps(records)
scene['user_setup_source'] = source.name
scene['publication_status'] = 'Lighting comparison stills only; not shipped movie'
scene.frame_set(301)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v6-hidden-horizon.blend')
print(json.dumps({'scene':scene.name, 'objects':len(scene.objects), 'rig':records, 'sun_disc_hidden':True}))
