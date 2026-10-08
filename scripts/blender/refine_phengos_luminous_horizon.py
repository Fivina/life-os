"""900 km silver-limb study with lateral dawn keys and measured wordmark geometry."""
import bpy
import json
import math
from mathutils import Quaternion, Vector

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.data.scenes['Phengos_Silver_Horizon_v11']
assert 'Phengos_Luminous_Horizon_v12' not in bpy.data.scenes
assert len(source.collection.objects) == len(source.objects) == 37
bpy.context.window.scene = source
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Luminous_Horizon_v12'
scene.use_fake_user = True
copies = {}
for original in list(scene.objects):
    obj = original.copy()
    if original.data:
        obj.data = original.data.copy()
        for slot in obj.material_slots:
            if slot.material:
                slot.material = slot.material.copy()
                tree = slot.material.node_tree
                if tree and tree.animation_data and tree.animation_data.action:
                    tree.animation_data.action = tree.animation_data.action.copy()
    if obj.animation_data and obj.animation_data.action:
        obj.animation_data.action = obj.animation_data.action.copy()
    scene.collection.objects.link(obj)
    scene.collection.objects.unlink(original)
    copies[original.name] = obj
receivers = {}
for original in source.objects:
    collection = original.light_linking.receiver_collection
    if collection:
        if collection.name not in receivers:
            replacement = bpy.data.collections.new(collection.name + '_v12')
            for receiver in collection.objects:
                replacement.objects.link(copies[receiver.name])
            receivers[collection.name] = replacement
        copies[original.name].light_linking.receiver_collection = receivers[collection.name]
    if original.get('optical_body'):
        copies[original.name]['optical_body'] = copies[original['optical_body']].name
scene.camera = copies[source.camera.name]
scene.world = source.world.copy()
scene.compositing_node_group = source.compositing_node_group.copy()
for n in scene.compositing_node_group.nodes:
    if n.type == 'R_LAYERS':
        n.scene = scene
    elif n.type == 'GLARE':
        n.inputs['Strength'].default_value = 0.3
bpy.context.window.scene = scene

def enum_value(owner, key, value):
    assert value in [i.identifier for i in owner.bl_rna.properties[key].enum_items]
    return value

def node(tree, kind, label):
    n = tree.nodes.new(kind)
    n.label = label
    return n

def smooth(t):
    t = min(1, max(0, t))
    return t * t * t * (t * (6 * t - 15) + 10)

earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
radius = earth['scene_radius']
old_center = earth.location.copy()
distance = radius * (1 + 900 / 6371.0084)
angle = math.radians(-5) - math.asin(radius / distance)
center = Vector((0, distance * math.sin(angle), 60 - distance * math.cos(angle)))
earth.location = center
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
atmosphere.location = center
emitter = next(o for o in scene.objects if o.get('emitter_role') == 'continuous_curved_horizon')
emitter.location += center - old_center
fill = next(o for o in scene.objects if o.get('rig_role') == 'restrained_night_surface_fill')
fill.location = center + (Vector((0, 0, 60)) - center).normalized() * radius * 3
fill.rotation_euler = (center - fill.location).to_track_quat('-Z', 'Y').to_euler()
for shell in scene.objects:
    if shell.get('optical_role') != 'earth_limb':
        continue
    shell.location = center
    tree = shell.data.materials[0].node_tree
    sharp = next(n for n in tree.nodes if n.label == 'Smooth optical limb width')
    emission = next(n for n in tree.nodes if n.type == 'EMISSION')
    gain = next((n for n in tree.nodes if n.label == 'Gentle central silver highlight'), None)
    if gain:
        emission.inputs['Color'].default_value = (1, 0.98, 0.95, 1)
        sharp.inputs[1].default_value = 65
        gain.inputs[1].default_value = 12.8
        gain.inputs[2].default_value = 16
        shell['limb_base_strength'] = 16
    else:
        emission.inputs['Color'].default_value = (0.72, 0.76, 0.82, 1)
        emission.inputs['Strength'].default_value = 1
        sharp.inputs[1].default_value = 50
        shell['limb_base_strength'] = 1
    shell['palette_role'] = 'silver optical edge; no separate saturated blue stripe'

planet_records = []
for prefix, side, phase, flux, fill_flux in (
    ('Distant_Banded_Planet', -1, 124, 1.7, 0.034),
    ('Distant_Cobalt_Planet', 1, 132, 1.6, 0.055),
):
    planet = next(o for o in scene.objects if o.name.startswith(prefix))
    view = (Vector((0, 0, 20)) - planet.location).normalized()
    right = Vector((0, 1, 0)).cross(view).normalized()
    key_direction = view * math.cos(math.radians(phase)) + right * side * math.sin(math.radians(phase))
    for lamp in scene.objects:
        if lamp.type != 'LIGHT' or 'planet_depth_base_energy' not in lamp:
            continue
        receiver_collection = lamp.light_linking.receiver_collection
        if not receiver_collection or planet.name not in receiver_collection.objects:
            continue
        key = lamp.get('rig_role') == 'independent_planet_key'
        direction = key_direction if key else view
        light_distance = planet['scene_radius'] * 8
        lamp.location = planet.location + direction * light_distance
        lamp.rotation_euler = (planet.location - lamp.location).to_track_quat('-Z', 'Y').to_euler()
        lamp.data.energy = 4 * math.pi * light_distance ** 2 * (flux if key else fill_flux)
        lamp['planet_depth_base_energy'] = lamp.data.energy
        lamp.data.color = (0.93, 0.96, 1) if key else (0.58, 0.55, 0.5)
        lamp['key_elevation_in_view_basis'] = 0
    halo = next(o for o in scene.objects if o.get('optical_body') == planet.name)
    incidence = next(n for n in halo.data.materials[0].node_tree.nodes
                     if n.label == 'World-specific sunrise incidence')
    incidence.inputs[1].default_value = key_direction
    if side < 0:
        tree = planet.data.materials[0].node_tree
        albedo = next(n for n in tree.nodes if n.label == 'NASA SVS LROC terrain texture, recolored')
        gray = node(tree, 'ShaderNodeRGBToBW', 'Terrain color separates crater plains from orange highlands')
        tree.links.new(albedo.outputs['Color'], gray.inputs[0])
        palette = node(tree, 'ShaderNodeValToRGB', 'Dark brown crater plains and subdued orange highlands')
        ramp = palette.color_ramp
        ramp.interpolation = enum_value(ramp, 'interpolation', 'EASE')
        ramp.elements[0].position = 0.07
        ramp.elements[0].color = (0.055, 0.032, 0.023, 1)
        ramp.elements[1].position = 0.7
        ramp.elements[1].color = (0.36, 0.13, 0.035, 1)
        mid = ramp.elements.new(0.32)
        mid.color = (0.13, 0.075, 0.045, 1)
        tree.links.new(gray.outputs[0], palette.inputs['Fac'])
        shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
        tree.links.new(palette.outputs['Color'], shader.inputs['Base Color'])
        shader.inputs['Specular IOR Level'].default_value = 0.12
        shader.inputs['Coat Weight'].default_value = 0.015
    planet_records.append({'planet': planet.name, 'key_phase_degrees': phase,
                           'illuminated_fraction': (1 + math.cos(math.radians(phase))) / 2,
                           'side': 'left' if side < 0 else 'right',
                           'key_direction': list(key_direction), 'view_basis_elevation': 0,
                           'fill_flux': fill_flux})

# Spatial variation modulates existing city radiance only, never blank terrain.
tree = earth.data.materials[0].node_tree
coords = next(n for n in tree.nodes if n.label == 'Spherical geographic UV')
noise = node(tree, 'ShaderNodeTexNoise', 'Stable settlement warmth variation; no temporal flicker')
noise.noise_dimensions = enum_value(noise, 'noise_dimensions', '3D')
noise.inputs['Scale'].default_value = 180
noise.inputs['Detail'].default_value = 2
tree.links.new(coords.outputs['UV'], noise.inputs['Vector'])
warmth = node(tree, 'ShaderNodeValToRGB', 'Dark orange to warm ivory settlement variation')
warmth.color_ramp.elements[0].color = (0.65, 0.24, 0.055, 1)
warmth.color_ramp.elements[1].color = (1, 0.63, 0.3, 1)
tree.links.new(noise.outputs['Fac'], warmth.inputs['Fac'])
tint = next(n for n in tree.nodes if n.label == 'Restrained warm settlement light')
tree.links.new(warmth.outputs['Color'], tint.inputs[2])

# Measure the actual O outline, including the font's cap overshoot.
letters = [o for o in scene.objects if o.type == 'FONT']
reference = next(o for o in letters if o.data.body == 'L')
glyph_data = reference.data.copy()
glyph_data.body = 'O'
glyph = bpy.data.objects.new('Phengos_Measure_O_v12', glyph_data)
scene.collection.objects.link(glyph)
scene.frame_set(91)
bpy.context.view_layer.update()
y_min = min(p[1] for p in glyph.bound_box)
y_max = max(p[1] for p in glyph.bound_box)
glyph_height = y_max - y_min
glyph_center_y = (y_min + y_max) / 2
assert 0.3 < glyph_height < 0.7
bpy.data.objects.remove(glyph, do_unlink=True)
bpy.data.curves.remove(glyph_data)
for letter in letters:
    letter.location.y = -glyph_center_y
    center_x = (min(p[0] for p in letter.bound_box) + max(p[0] for p in letter.bound_box)) / 2
    letter.location.x -= center_x
    emission = next(n for n in letter.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
    emission.inputs['Color'].default_value = (0.48, 0.70, 1, 1)
    emission.inputs['Strength'].default_value = 2
circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
circle_emission = next(n for n in circle.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
title_scale = glyph_height / (2 * max(v.co.length for v in circle.data.vertices))
scene.frame_set(1)
earth_orientation = earth.rotation_quaternion.copy()
for frame in range(1, scene.frame_end + 1):
    seconds = (frame - 1) / scene.render.fps
    approach = smooth(seconds / 5)
    transition = smooth((seconds - 3.8) / 1.2)
    rise = smooth((seconds - 5) / 3.5)
    scene.camera.location = (0, 3700 * rise, 20 + 40 * approach)
    scene.camera.keyframe_insert('location', frame=frame)
    earth.rotation_quaternion = Quaternion((0, 1, 0), math.radians(0.75 * approach + 0.525 * rise)) @ earth_orientation
    earth.keyframe_insert('rotation_quaternion', frame=frame)
    # During the wordmark, 40 units of camera retreat vs 8 units of relative
    # glyph-plane retreat is the requested 5:1 depth-motion relationship.
    glyph_z = 2 + 32 * approach
    for letter in letters:
        letter.location.z = glyph_z
        letter.keyframe_insert('location', frame=frame)
        emission = next(n for n in letter.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
        emission.inputs['Strength'].default_value = 2 - 0.8 * approach
        emission.inputs['Strength'].keyframe_insert('default_value', frame=frame)
    circle.location = (1.2 * (1 - transition), 3700 * rise, glyph_z + 8 * approach * transition)
    circle.keyframe_insert('location', frame=frame)
    scale = title_scale + (1 - title_scale) * transition
    circle.scale = (scale, scale, scale)
    circle.keyframe_insert('scale', frame=frame)
    circle_emission.inputs['Strength'].default_value = 2 + 6 * transition
    circle_emission.inputs['Strength'].keyframe_insert('default_value', frame=frame)
    radiance = 1 - 0.55 * approach
    for shell in scene.objects:
        if shell.get('optical_role') != 'earth_limb':
            continue
        nodes = shell.data.materials[0].node_tree.nodes
        gain = next((n for n in nodes if n.label == 'Gentle central silver highlight'), None)
        if gain:
            gain.inputs[1].default_value = 12.8 * radiance
            gain.inputs[2].default_value = 16 * radiance
            gain.inputs[1].keyframe_insert('default_value', frame=frame)
            gain.inputs[2].keyframe_insert('default_value', frame=frame)
        else:
            emission = next(n for n in nodes if n.type == 'EMISSION')
            emission.inputs['Strength'].default_value = radiance
            emission.inputs['Strength'].keyframe_insert('default_value', frame=frame)
    for lamp in scene.objects:
        if lamp.type == 'LIGHT' and 'planet_depth_base_energy' in lamp:
            lamp.data.energy = lamp['planet_depth_base_energy'] * (1.15 - 0.4 * approach)
            lamp.data.keyframe_insert('energy', frame=frame)
circle['wordmark_o_height'] = glyph_height
circle['wordmark_baseline'] = -glyph_center_y
circle['wordmark_title_scale'] = title_scale

records = json.loads(source['scale_record'])
scene.frame_set(1)
bpy.context.view_layer.update()
for record in records:
    record['object'] = copies[record['object']].name
    planet = scene.objects[record['object']]
    opening_distance = (scene.camera.location - planet.location).length
    record['opening_camera_distance'] = opening_distance
    record['opening_angular_diameter_degrees'] = math.degrees(2 * math.asin(record['radius'] / opening_distance))
scene['scale_record'] = json.dumps(records)
scene['dawn_rig_record'] = json.dumps(planet_records)
scene['horizon_camera_altitude_km'] = 900
scene['user_setup_source'] = source.name
scene['publication_status'] = '900 km luminous horizon still study; no movie/browser replacement'
scene['city_light_variation'] = 'Stable spatial warmth within existing satellite city mask only'
scene['opening_motion'] = 'Pull back 40 scene units; wordmark relative depth changes 8 units (5:1)'
scene['opening_light_timing'] = 'Shared quintic retreat timing; horizon/title/planet radiance yields to circle'
scene['earth_rotation_timing'] = 'Same quintic phase as camera: 0.75 degrees during retreat, 0.525 during rise'
scene['opening_motion_ratio'] = 'Camera 5 : Earth 5 : wordmark relative motion 1'
scene.frame_set(301)
actual_altitude = ((scene.camera.location - earth.location).length - radius) * scene['shared_scale_km_per_unit']
assert abs(actual_altitude - 900) < 0.01
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v12-luminous-horizon.blend')
print(json.dumps({'scene': scene.name, 'altitude': actual_altitude, 'objects': len(scene.objects),
                  'glyph_o_height': glyph_height, 'circle_title_scale': title_scale,
                  'planet_lighting': planet_records}))
