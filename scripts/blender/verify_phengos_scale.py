"""Validate persisted common-scale geometry, linked lights and camera continuity."""
import bpy
import json
import math
import sys
from mathutils import Vector

natural = '--natural' in sys.argv
silver = '--silver' in sys.argv
luminous = '--luminous' in sys.argv
scene = bpy.data.scenes['Phengos_Luminous_Horizon_v12' if luminous else 'Phengos_Silver_Horizon_v11' if silver else
                        'Phengos_Natural_Horizon_v10' if natural else 'Phengos_Scale_Study_v9']
source = bpy.data.scenes['Phengos_Silver_Horizon_v11' if luminous else 'Phengos_Natural_Horizon_v10' if silver else
                         'Phengos_Scale_Study_v9' if natural else 'Phengos_Planet_Depth_v8']
radius_reference = 480 if natural or silver or luminous else 240
assert len(source.objects) == (37 if luminous else 33 if silver else 32)
assert len(scene.objects) == (37 if silver or luminous else 33 if natural else 32)
if bpy.context.window:
    bpy.context.window.scene = scene
assert scene.use_fake_user
assert scene.camera.data is not source.camera.data
for node in scene.compositing_node_group.nodes:
    if node.type == 'R_LAYERS':
        assert node.scene == scene
records = json.loads(scene['scale_record'])
earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
old_earth = next(o for o in source.objects if o.name.startswith('Earth_Horizon'))
assert earth.data is not old_earth.data
assert math.isclose(max(v.co.length for v in old_earth.data.vertices),
                    radius_reference if silver or luminous else radius_reference / 2,
                    rel_tol=0.00002, abs_tol=0.001)
# Dense UV primitives accumulate small float error while generating longitude rings.
assert math.isclose(max(v.co.length for v in earth.data.vertices), radius_reference,
                    rel_tol=0.00002, abs_tol=0.001)
if natural:
    assert len(earth.data.vertices) > len(old_earth.data.vertices)
else:
    assert len(earth.data.vertices) == len(old_earth.data.vertices)
scene.frame_set(1)
bpy.context.view_layer.update()
for record in records:
    planet = scene.objects[record['object']]
    assert max(planet.dimensions) - min(planet.dimensions) < 0.001
    radius = max(planet.dimensions) / 2
    assert abs(radius / radius_reference - record['radius_ratio']) < 0.00001
    distance = (scene.camera.matrix_world.translation - planet.matrix_world.translation).length
    angle = math.degrees(2 * math.asin(radius / distance))
    assert abs(angle - record['opening_angular_diameter_degrees']) < 0.0001
    shader = next(n for n in planet.data.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    assert shader.inputs['Emission Strength'].default_value == 0
lights = [o for o in scene.objects if o.type == 'LIGHT' and 'planet_depth_base_energy' in o]
assert len(lights) == 4
for light in lights:
    receivers = light.light_linking.receiver_collection
    assert receivers and len(receivers.objects) == 1
    assert all(o.name in scene.objects for o in receivers.objects)
    assert all(o.name not in source.objects for o in receivers.objects)
    assert light.data.energy > 0
emitter = next(o for o in scene.objects if o.get('emitter_role') == 'continuous_curved_horizon')
assert not emitter.visible_camera
assert len(emitter.light_linking.receiver_collection.objects) == 1
assert all(o.name.startswith('Earth_Thin_Atmosphere')
           for o in emitter.light_linking.receiver_collection.objects)
for frame in (1, 91, 301, 361, 421, 511):
    scene.frame_set(frame)
    circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
    relative = scene.camera.matrix_world.inverted() @ circle.matrix_world.translation
    assert abs(relative.y) < 0.0001
    if frame >= 301:
        assert abs(relative.x) < 0.0001 and abs(relative.z + 18) < 0.0001
scene.frame_set(511)
corners = scene.camera.data.view_frame(scene=scene)
half_vertical = max(abs(v.y / v.z) for v in corners)
for record in records:
    planet = scene.objects[record['object']]
    relative = scene.camera.matrix_world.inverted() @ planet.matrix_world.translation
    assert relative.y + record['radius'] < -(-relative.z + record['radius']) * half_vertical
stars = next(o for o in scene.objects if o.name.startswith('Sparse_Stars'))
nearest_star = max((stars.matrix_world @ v.co).z for v in stars.data.vertices)
for record in records:
    assert nearest_star < record['position'][2] - record['radius']
assert scene.camera.data.clip_end > (11000 if natural or silver or luminous else 5500)
if natural or silver or luminous:
    scene.frame_set(301)
    altitude = ((scene.camera.location - earth.location).length - radius_reference) * scene['shared_scale_km_per_unit']
    assert abs(altitude - (900 if luminous else 600 if silver else 450)) < 0.01
    tree = earth.data.materials[0].node_tree
    tile = next(n for n in tree.nodes if n.type == 'TEX_IMAGE' and n.label.startswith('NASA VIIRS'))
    assert list(tile.image.size) == [8192, 5821]
    assert tile.image.packed_file
    shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    assert not shader.inputs['Normal'].is_linked
    fill = next(o for o in scene.objects if o.get('rig_role') == 'restrained_night_surface_fill')
    assert list(fill.light_linking.receiver_collection.objects) == [earth]
    assert scene.cycles.volume_biased is False
    assert scene['atmospheric_scale_height_km'] == 8
    if natural:
        assert abs(old_earth.location.y + 242.4) < 0.001
if silver or luminous:
    # Evaluate the archived scene's own animation graph, not the active scene's graph.
    if bpy.context.window:
        bpy.context.window.scene = source
    source.frame_set(301)
    source.view_layers[0].update()
    old_altitude = ((source.camera.location - old_earth.location).length - 480) * source['shared_scale_km_per_unit']
    assert abs(old_altitude - (600 if luminous else 450)) < 0.01
    if bpy.context.window:
        bpy.context.window.scene = scene
    assert scene['horizon_mode'] == 'SILVER_OPTICS'
    atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
    assert atmosphere.hide_render
    optics = [o for o in scene.objects if o.get('camera_only_art_direction')]
    assert len(optics) == 4
    assert sum(o.get('optical_role') == 'earth_limb' for o in optics) == 2
    assert sum(o.get('optical_role') == 'planet_dawn_limb' for o in optics) == 2
    for shell in optics:
        assert shell['optical_body'] in scene.objects
        nodes = shell.data.materials[0].node_tree.nodes
        assert any(n.type == 'LIGHT_PATH' for n in nodes)
        assert not any(n.type in ('TEX_NOISE', 'VOLUME_SCATTER') for n in nodes)
        gate = next(n for n in nodes if n.label == 'No diffuse, reflection or shadow contribution')
        assert gate.inputs[1].links[0].from_socket.identifier == 'Is Camera Ray'
        if shell.get('optical_role') == 'planet_dawn_limb':
            assert any(n.label == 'No full glowing planet ring' for n in nodes)
    dawn = json.loads(scene['dawn_rig_record'])
    assert [r['key_phase_degrees'] for r in dawn] == [124, 132]
    assert all(0.1 < r['illuminated_fraction'] < 0.25 for r in dawn)
    for record in records:
        planet = scene.objects[record['object']]
        assert len(planet.data.vertices) == 32514
        nodes = planet.data.materials[0].node_tree.nodes
        height = next(n for n in nodes if n.label == 'NASA SVS LOLA elevation, bounded bump only')
        albedo = next(n for n in nodes if n.label == 'NASA SVS LROC terrain texture, recolored')
        assert height.image.packed_file and albedo.image.packed_file
        assert list(height.image.size) == [5760, 2880]
        assert list(albedo.image.size) == [4096, 2048]
        assert height.image.colorspace_settings.name == 'Non-Color'
if luminous:
    scene.frame_set(1)
    first_earth = earth.rotation_quaternion.copy()
    circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
    def smooth(t):
        t = min(1, max(0, t))
        return t*t*t*(t*(6*t-15)+10)
    for frame in (1, 91, 181, 229, 271, 301):
        scene.frame_set(frame)
        progress = smooth((frame - 1) / scene.render.fps / 5)
        assert abs(scene.camera.location.z - (20 + 40 * progress)) < 0.0001
        rotation = first_earth.rotation_difference(earth.rotation_quaternion)
        assert abs(math.degrees(rotation.angle) - 0.75 * progress) < 0.03
        letters = [o for o in scene.objects if o.type == 'FONT']
        for letter in letters:
            assert abs(letter.location.z - (2 + 32 * progress)) < 0.0001
            assert abs((scene.camera.location.z - letter.location.z) - (18 + 8 * progress)) < 0.0001
        if frame <= 229:
            assert abs(max(circle.dimensions) - circle['wordmark_o_height']) < 0.0001
            for letter in letters:
                points = [letter.matrix_world @ Vector(p) for p in letter.bound_box]
                center_y = (min(p.y for p in points) + max(p.y for p in points)) / 2
                assert abs(center_y - circle.location.y) < 0.001
    scene.frame_set(1)
    for light in lights:
        if light.get('rig_role') == 'independent_planet_key':
            planet = next(iter(light.light_linking.receiver_collection.objects))
            view = (scene.camera.location - planet.location).normalized()
            right = Vector((0, 1, 0)).cross(view).normalized()
            up = view.cross(right).normalized()
            assert abs((light.location - planet.location).normalized().dot(up)) < 0.00001
    for shell in optics:
        if shell.get('optical_role') == 'earth_limb':
            emission = next(n for n in shell.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
            assert min(emission.inputs['Color'].default_value[:3]) >= 0.7
    city_tree = earth.data.materials[0].node_tree
    tint = next(n for n in city_tree.nodes if n.label == 'Restrained warm settlement light')
    assert tint.inputs[2].is_linked
    noise = next(n for n in city_tree.nodes if n.label == 'Stable settlement warmth variation; no temporal flicker')
    assert not noise.inputs['Scale'].is_linked
    assert noise.noise_dimensions == '3D'
    old_circle = next(o for o in source.objects if o.name.startswith('Phengos.'))
    assert list(old_circle.scale) == [1, 1, 1]
    assert all(abs(o.location.y + 0.4) < 0.0001 for o in source.objects if o.type == 'FONT')
    print('PHENGOS_LUMINOUS_VERIFICATION_PASS: 900 km, silver palette, O-size/baseline, '
          'lateral keys, shared Earth/camera clock, 5:1 wordmark relative motion, source preservation')
print('PHENGOS_SCALE_VERIFICATION_PASS: geometry, ratios, angles, source preservation, '
      'four linked lights, hidden horizon source, six track samples, idle clearance, star depth')
