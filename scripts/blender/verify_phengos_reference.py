"""Verify saved staging continuity and isolation of near/far lighting."""
import bpy
import json
import math
from array import array
from bpy_extras.object_utils import world_to_camera_view

scene = bpy.data.scenes['Phengos_Reference_v16']
source = bpy.data.scenes['Phengos_Cinematic_Hierarchy_v15']
bpy.context.window.scene = scene
mapping = json.loads(scene['object_copy_map'])
earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
planets = [o for o in scene.objects if o.name.startswith(('Distant_Banded_Planet', 'Distant_Cobalt_Planet'))]
letters = [o for o in scene.objects if o.type == 'FONT']
sky = next(o for o in scene.objects if o.get('art_role') == 'surrounding sky')
light = next(o for o in scene.objects if o.get('art_role') == 'Phengos cinematic distant-planet point light')
assert light.parent == circle
assert not circle.visible_shadow, 'Character shell must not block its internal source'
assert set(light.light_linking.receiver_collection.objects) == set(planets)
assert set(circle.light_linking.receiver_collection.objects) == set(planets)
assert all(not getattr(sky, p) for p in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_shadow'))
assert not sky.data.materials[0].node_tree.animation_data
for obj in scene.objects:
    if obj.get('art_role') in ('restricted atmospheric reflection', 'Phengos moving point light'):
        assert obj.hide_render
        if obj.type == 'LIGHT':
            assert obj.data.energy == 0
    if obj.get('optical_role') == 'earth_limb':
        spark = next((n for n in obj.data.materials[0].node_tree.nodes if n.label == 'Art-directed Phengos atmospheric spark'), None)
        if spark:
            assert spark.inputs[1].default_value == 0

for old_name, name in mapping.items():
    obj = scene.objects[name]
    if obj not in [earth]+planets:
        continue
    old = source.objects[old_name]
    expected = array('f', [0])*len(old.data.vertices)*3
    actual = array('f', [0])*len(obj.data.vertices)*3
    old.data.vertices.foreach_get('co', expected)
    obj.data.vertices.foreach_get('co', actual)
    assert actual == expected, obj.name
    assert (obj.location-old.location).length < 0.00001
    assert (obj.scale-old.scale).length < 0.00001

initial_positions = {o.name:o.location.copy() for o in [earth]+planets}
previous_opacity = 1
previous_radius = 0
previous_circle = None
records = []
for frame in range(1, 512):
    scene.frame_set(frame)
    for obj in [earth]+planets:
        assert (obj.location-initial_positions[obj.name]).length < 0.00001
    values = [next(n for n in o.data.materials[0].node_tree.nodes if n.type == 'MIX_SHADER').inputs[0].default_value for o in letters]
    assert max(values)-min(values) < 0.000001
    assert 0 <= values[0] <= 1
    assert values[0] <= previous_opacity+0.000001
    previous_opacity = values[0]
    if frame == 1:
        assert values[0] == 1
    if frame >= 289:
        assert values[0] < 0.000001
    projected = world_to_camera_view(scene, scene.camera, circle.location)
    assert 0 < projected.x < 1 and 0 < projected.y < 1 and projected.z > 0
    if frame <= 301:
        radius = circle.scale.x/projected.z
        assert radius >= previous_radius-0.000001
        previous_radius = radius
    if previous_circle is not None:
        assert (circle.location-previous_circle).length < 10, ('Character discontinuity', frame)
    previous_circle = circle.location.copy()
    assert math.isfinite(light.data.energy) and 0 < light.data.energy <= 14000001
    # Camera corner rays must stay on the textured dome, including the upward view.
    for corner in scene.camera.data.view_frame(scene=scene):
        ray = scene.camera.matrix_world.to_quaternion() @ corner.normalized()
        longitude = math.degrees(math.atan2(ray.x, -ray.z))
        latitude = math.degrees(math.asin(ray.y))
        assert -55 < longitude < 55 and -38 < latitude < 90, (frame, longitude, latitude)
    if frame in (1, 157, 217, 289, 301, 361, 421, 511):
        records.append({'frame':frame, 'circle_xy':[projected.x, projected.y],
                        'opacity':values[0], 'planet_light':light.data.energy})
end = world_to_camera_view(scene, scene.camera, circle.location)
assert abs(end.x-.5) < .002 and abs(end.y-.5) < .002
assert records[5]['circle_xy'][1] > .55, 'Character must lead the upward camera move'
print('PHENGOS_REFERENCE_VERIFY_PASS', json.dumps({'frames':511,
      'body_geometry_and_positions_preserved':True, 'earth_reflection_removed':True,
      'far_background_independent':True, 'fade_and_projection':records}))
