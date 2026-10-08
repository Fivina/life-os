"""Shared physical radius ratios, cinematic distances and a broader Earth horizon."""
import bpy
import json
import math
from mathutils import Vector

OUT = 'E:/LifeOS-Art/phengos'
EARTH_KM = 6371.0084
EARTH_RADIUS = 240.0
RATIOS = {'Earth': 1.0, 'Mars': 3389.50 / EARTH_KM,
          'Mercury': 2439.4 / EARTH_KM}
source = bpy.context.scene
assert source.name == 'Phengos_Planet_Depth_v8'
assert len(source.collection.objects) == len(source.objects)
assert 'Phengos_Scale_Study_v9' not in bpy.data.scenes
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Scale_Study_v9'
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
            collection = bpy.data.collections.new(receivers.name + '_v9')
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

earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
old_earth_center = earth.location.copy()
earth_factor = EARTH_RADIUS / max(v.co.length for v in earth.data.vertices)
new_earth_center = Vector((0, -EARTH_RADIUS - 2.4, -40))
for obj in (earth, atmosphere):
    for vertex in obj.data.vertices:
        vertex.co *= earth_factor
    obj.data.update()
    obj.location = new_earth_center
earth['reference_radius_km'] = EARTH_KM
earth['scene_radius'] = EARTH_RADIUS
earth['normalized_radius'] = 10.0
for node in atmosphere.data.materials[0].node_tree.nodes:
    if node.type == 'MATH':
        if node.label == 'Altitude above Earth':
            node.inputs[1].default_value = EARTH_RADIUS
        elif node.label in ('Negative inverse scale height', 'Rayleigh density'):
            node.inputs[1].default_value /= earth_factor
emitter = next(o for o in scene.objects if o.get('emitter_role') == 'continuous_curved_horizon')
emitter.location = new_earth_center + (emitter.location - old_earth_center) * earth_factor
for vertex in emitter.data.vertices:
    vertex.co *= earth_factor
emitter.data.update()
emitter['source_radius'] *= earth_factor

origin = scene.camera.location.copy()
records = []
for prefix, reference, angle, sightline in (
    ('Distant_Banded_Planet', 'Mars', 8.0, (0.48, 0.16, -1)),
    ('Distant_Cobalt_Planet', 'Mercury', 3.5, (-0.50, 0.20, -1)),
):
    planet = next(o for o in scene.objects if o.name.startswith(prefix))
    old_location = planet.location.copy()
    old_radius = max(planet.dimensions) / 2
    radius = EARTH_RADIUS * RATIOS[reference]
    mesh_radius = max(v.co.length for v in planet.data.vertices)
    planet.scale = (radius / mesh_radius,) * 3
    distance = radius / math.sin(math.radians(angle) / 2)
    planet.location = origin + Vector(sightline).normalized() * distance
    size_factor = radius / old_radius
    for lamp in scene.objects:
        if lamp.type != 'LIGHT' or 'planet_depth_base_energy' not in lamp:
            continue
        receivers = lamp.light_linking.receiver_collection
        if receivers and planet.name in receivers.objects:
            lamp.location = planet.location + (lamp.location - old_location) * size_factor
            lamp.rotation_euler = (planet.location - lamp.location).to_track_quat('-Z', 'Y').to_euler()
            lamp.data.size *= size_factor
            lamp['planet_depth_base_energy'] *= size_factor * size_factor
            lamp.data.energy = lamp['planet_depth_base_energy'] * 1.3
    planet['scale_reference'] = reference
    planet['normalized_radius'] = RATIOS[reference] * 10
    planet['scene_radius'] = radius
    planet['distance_is_cinematic_not_orbital'] = True
    records.append({'object': planet.name, 'reference': reference,
                    'radius_ratio': RATIOS[reference], 'radius': radius,
                    'opening_camera_distance': distance,
                    'earth_radius_distance': distance / EARTH_RADIUS,
                    'opening_angular_diameter_degrees': angle,
                    'position': list(planet.location)})

# Put every star and the smooth sky behind the newly distant worlds.
stars = next(o for o in scene.objects if o.name.startswith('Sparse_Stars'))
stars.scale *= 4
stars.location.z -= 2250
sky = next(o for o in scene.objects if o.name.startswith('Smooth_Infinite_Space'))
sky.location.z = -5500
sky.scale = (40, 40, 40)
scene.camera.data.clip_end = 7000

# Reuse the authored easing curve, changing only the shared vertical travel.
circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
for obj in (scene.camera, circle):
    action = obj.animation_data.action
    slot = obj.animation_data.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot)
            if not bag:
                continue
            for curve in bag.fcurves:
                if curve.data_path == 'location' and curve.array_index == 1:
                    for point in curve.keyframe_points:
                        point.co.y *= 1850 / 350
                        point.handle_left.y *= 1850 / 350
                        point.handle_right.y *= 1850 / 350
                    curve.update()

scene['planet_depth_strength'] = 1.3
scene['shared_scale_km_per_unit'] = EARTH_KM / EARTH_RADIUS
scene['radius_ratio_source'] = 'https://ssd.jpl.nasa.gov/planets/phys_par.html'
scene['scale_record'] = json.dumps(records)
scene['user_setup_source'] = source.name
scene['publication_status'] = 'Shared-scale still study; not installed in browser'
scene['distance_policy'] = 'Real size ratios; deliberately compressed cinematic distances'
checks = []
for frame in (1, 91, 301, 361, 421, 511):
    scene.frame_set(frame)
    relative = scene.camera.matrix_world.inverted() @ circle.matrix_world.translation
    checks.append({'frame': frame, 'camera_local_circle': list(relative)})
    assert abs(relative.y) < 0.0001, 'Circle must rise with the camera'
scene.frame_set(301)
bpy.context.view_layer.update()
for item in records:
    obj = scene.objects[item['object']]
    assert max(obj.dimensions) - min(obj.dimensions) < 0.001, 'No stretched worlds'
scene['track_verification'] = json.dumps(checks)
altitude = (scene.camera.location - earth.location).length - EARTH_RADIUS
scene['horizon_camera_altitude_km'] = altitude * EARTH_KM / EARTH_RADIUS
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v9-shared-scale.blend')
print(json.dumps({'scene': scene.name, 'scale': records, 'earth_radius': EARTH_RADIUS,
                  'horizon_camera_altitude_km': scene['horizon_camera_altitude_km'],
                  'track_checks': checks}))
