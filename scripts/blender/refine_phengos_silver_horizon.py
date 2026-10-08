"""600 km camera, camera-only silver limb and contrasting dawn-side fictional worlds."""
import bpy
import json
import math
from mathutils import Vector

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.context.scene
assert source.name == 'Phengos_Natural_Horizon_v10'
assert len(source.collection.objects) == len(source.objects)
assert 'Phengos_Silver_Horizon_v11' not in bpy.data.scenes
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Silver_Horizon_v11'
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
            collection = bpy.data.collections.new(receivers.name + '_v11')
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
    values = [i.identifier for i in owner.bl_rna.properties[key].enum_items]
    assert value in values
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

earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
radius = earth['scene_radius']
old_center = earth.location.copy()
altitude_km = 600
distance = radius * (1 + altitude_km / 6371.0084)
angle = math.radians(-5) - math.asin(radius / distance)
center = Vector((0, distance * math.sin(angle), 20 - distance * math.cos(angle)))
earth.location = center
atmosphere.location = center
emitter = next(o for o in scene.objects if o.get('emitter_role') == 'continuous_curved_horizon')
emitter.location += center - old_center
fill = next(o for o in scene.objects if o.get('rig_role') == 'restrained_night_surface_fill')
fill.location = center + (Vector((0, 0, 20)) - center).normalized() * radius * 3
fill.rotation_euler = (center - fill.location).to_track_quat('-Z', 'Y').to_euler()

def optical_shell(body, name, gap, color, strength, power, light_direction=None, central_gain=False):
    shell = body.copy()
    shell.name = name
    shell.data = body.data.copy()
    shell.animation_data_clear()
    scene.collection.objects.link(shell)
    shell.scale *= 1 + gap / body['scene_radius']
    shell.data.materials.clear()
    material = bpy.data.materials.new(name + '_View_Dependent_Optics')
    material.use_nodes = True
    shell.data.materials.append(material)
    tree = material.node_tree
    tree.nodes.clear()
    geometry = node(tree, 'ShaderNodeNewGeometry', 'Smooth sphere normal; no textured rim')
    facing = node(tree, 'ShaderNodeVectorMath', 'View-angle cosine')
    facing.operation = enum_value(facing, 'operation', 'DOT_PRODUCT')
    tree.links.new(geometry.outputs['Normal'], facing.inputs[0])
    tree.links.new(geometry.outputs['Incoming'], facing.inputs[1])
    absolute = math_node(tree, 'ABSOLUTE', 'Both view conventions')
    tree.links.new(facing.outputs['Value'], absolute.inputs[0])
    grazing = math_node(tree, 'SUBTRACT', 'Silhouette-only falloff')
    grazing.inputs[0].default_value = 1
    tree.links.new(absolute.outputs[0], grazing.inputs[1])
    sharp = math_node(tree, 'POWER', 'Smooth optical limb width', power)
    tree.links.new(grazing.outputs[0], sharp.inputs[0])
    front = math_node(tree, 'SUBTRACT', 'No rear-surface double glow')
    front.inputs[0].default_value = 1
    tree.links.new(geometry.outputs['Backfacing'], front.inputs[1])
    front_limb = math_node(tree, 'MULTIPLY', 'Front optical limb only')
    tree.links.new(sharp.outputs[0], front_limb.inputs[0])
    tree.links.new(front.outputs[0], front_limb.inputs[1])
    mask = front_limb.outputs[0]
    if light_direction is not None:
        incidence = node(tree, 'ShaderNodeVectorMath', 'World-specific sunrise incidence')
        incidence.operation = enum_value(incidence, 'operation', 'DOT_PRODUCT')
        tree.links.new(geometry.outputs['Normal'], incidence.inputs[0])
        incidence.inputs[1].default_value = light_direction
        lit = math_node(tree, 'MAXIMUM', 'Only the sunlit atmospheric side', 0)
        tree.links.new(incidence.outputs['Value'], lit.inputs[0])
        gate = math_node(tree, 'MULTIPLY', 'No full glowing planet ring')
        tree.links.new(mask, gate.inputs[0])
        tree.links.new(lit.outputs[0], gate.inputs[1])
        mask = gate.outputs[0]
    light_path = node(tree, 'ShaderNodeLightPath', 'Presentation only; not another sun')
    camera_gate = math_node(tree, 'MULTIPLY', 'No diffuse, reflection or shadow contribution')
    tree.links.new(mask, camera_gate.inputs[0])
    tree.links.new(light_path.outputs['Is Camera Ray'], camera_gate.inputs[1])
    emission = node(tree, 'ShaderNodeEmission', 'Art-directed atmospheric radiance')
    emission.inputs['Color'].default_value = (*color, 1)
    emission.inputs['Strength'].default_value = strength
    if central_gain:
        separate = node(tree, 'ShaderNodeSeparateXYZ', 'Horizon center accent')
        tree.links.new(geometry.outputs['Position'], separate.inputs[0])
        scale = math_node(tree, 'DIVIDE', 'Broad central sunrise emphasis', radius * 0.4)
        tree.links.new(separate.outputs['X'], scale.inputs[0])
        squared = math_node(tree, 'POWER', 'Continuous central lobe', 2)
        tree.links.new(scale.outputs[0], squared.inputs[0])
        negate = math_node(tree, 'MULTIPLY', 'Gaussian exponent', -1)
        tree.links.new(squared.outputs[0], negate.inputs[0])
        gaussian = math_node(tree, 'EXPONENT', 'No starburst or visible sun disc')
        tree.links.new(negate.outputs[0], gaussian.inputs[0])
        gain = math_node(tree, 'MULTIPLY_ADD', 'Gentle central silver highlight')
        gain.inputs[1].default_value = strength * 0.8
        gain.inputs[2].default_value = strength
        tree.links.new(gaussian.outputs[0], gain.inputs[0])
        tree.links.new(gain.outputs[0], emission.inputs['Strength'])
    transparent = node(tree, 'ShaderNodeBsdfTransparent', 'Unlit regions remain transparent')
    mix = node(tree, 'ShaderNodeMixShader', 'Optical edge over real geometry')
    output = node(tree, 'ShaderNodeOutputMaterial', 'Direct-ray limb, no volume noise')
    tree.links.new(camera_gate.outputs[0], mix.inputs[0])
    tree.links.new(transparent.outputs[0], mix.inputs[1])
    tree.links.new(emission.outputs[0], mix.inputs[2])
    tree.links.new(mix.outputs[0], output.inputs['Surface'])
    shell['optical_role'] = 'earth_limb' if light_direction is None else 'planet_dawn_limb'
    shell['optical_body'] = body.name
    shell['camera_only_art_direction'] = True
    shell['limb_base_strength'] = strength
    return shell

# This is intentionally an optical art layer, not an atmospheric simulation.
optical_shell(earth, 'Phengos_Silver_Limb_v11', 0.3, (0.76, 0.86, 1), 6, 80, central_gain=True)
optical_shell(earth, 'Phengos_Blue_Limb_Falloff_v11', 0.75, (0.09, 0.28, 0.85), 0.7, 70)
atmosphere.hide_render = True

color_map = bpy.data.images.load(OUT + '/textures/nasa-lroc-color-4k.tif', check_existing=True)
height_map = bpy.data.images.load(OUT + '/textures/nasa-lola-height-16ppd.tif', check_existing=True)
height_map.colorspace_settings.name = enum_value(height_map.colorspace_settings, 'name', 'Non-Color')
planet_records = []
for prefix, side, phase, elevation, flux, fill_flux, tint, uv_offset, halo_color in (
    ('Distant_Banded_Planet', -1, 124, 0.38, 2.0, 0.028, (0.65, 0.24, 0.06, 1), 0.31, (0.35, 0.58, 0.95)),
    ('Distant_Cobalt_Planet', 1, 132, -0.30, 1.6, 0.015, (0.45, 0.03, 0.025, 1), -0.17, (0.95, 0.49, 0.38)),
):
    planet = next(o for o in scene.objects if o.name.startswith(prefix))
    mesh_radius = max(v.co.length for v in planet.data.vertices)
    materials = list(planet.data.materials)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=mesh_radius)
    temporary = bpy.context.object
    planet.data = temporary.data
    bpy.data.objects.remove(temporary, do_unlink=True)
    for material in materials:
        planet.data.materials.append(material)
    for polygon in planet.data.polygons:
        polygon.use_smooth = True
    tree = planet.data.materials[0].node_tree
    shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    coords = node(tree, 'ShaderNodeTexCoord', 'Fictional terrain spherical UV')
    offset = node(tree, 'ShaderNodeVectorMath', 'Distinct terrain region on each world')
    offset.operation = enum_value(offset, 'operation', 'ADD')
    offset.inputs[1].default_value = (uv_offset, 0, 0)
    tree.links.new(coords.outputs['UV'], offset.inputs[0])
    albedo = node(tree, 'ShaderNodeTexImage', 'NASA SVS LROC terrain texture, recolored')
    albedo.image = color_map
    albedo.interpolation = enum_value(albedo, 'interpolation', 'Cubic')
    tree.links.new(offset.outputs[0], albedo.inputs['Vector'])
    color = node(tree, 'ShaderNodeMixRGB', 'Fictional palette, photographic geology')
    color.blend_type = enum_value(color, 'blend_type', 'MULTIPLY')
    color.inputs[0].default_value = 1
    color.inputs[2].default_value = tint
    tree.links.new(albedo.outputs['Color'], color.inputs[1])
    tree.links.new(color.outputs[0], shader.inputs['Base Color'])
    height = node(tree, 'ShaderNodeTexImage', 'NASA SVS LOLA elevation, bounded bump only')
    height.image = height_map
    height.interpolation = enum_value(height, 'interpolation', 'Cubic')
    tree.links.new(offset.outputs[0], height.inputs['Vector'])
    bump = node(tree, 'ShaderNodeBump', 'Subtle crater relief, no displaced silhouette')
    bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.8 if side < 0 else 0.6
    tree.links.new(height.outputs['Color'], bump.inputs['Height'])
    tree.links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    for link in list(shader.inputs['Roughness'].links):
        tree.links.remove(link)
    shader.inputs['Roughness'].default_value = 0.76
    shader.inputs['Specular IOR Level'].default_value = 0.2
    shader.inputs['Coat Weight'].default_value = 0.04
    shader.inputs['Coat Roughness'].default_value = 0.35
    shader.inputs['Emission Strength'].default_value = 0
    view = (scene.camera.location - planet.location).normalized()
    right = Vector((0, 1, 0)).cross(view).normalized()
    up = view.cross(right).normalized()
    lateral = (right * side + up * elevation).normalized()
    key_direction = view * math.cos(math.radians(phase)) + lateral * math.sin(math.radians(phase))
    for lamp in scene.objects:
        if lamp.type != 'LIGHT' or 'planet_depth_base_energy' not in lamp:
            continue
        receivers = lamp.light_linking.receiver_collection
        if not receivers or planet.name not in receivers.objects:
            continue
        key = lamp.get('rig_role') == 'independent_planet_key'
        direction = key_direction if key else view
        distance_to_light = planet['scene_radius'] * 8
        lamp.location = planet.location + direction * distance_to_light
        lamp.rotation_euler = (planet.location - lamp.location).to_track_quat('-Z', 'Y').to_euler()
        energy = 4 * math.pi * distance_to_light ** 2 * (flux if key else fill_flux)
        lamp['planet_depth_base_energy'] = energy
        lamp.data.energy = energy
        lamp.data.size = planet['scene_radius'] * (0.45 if key else 3.0)
        lamp.data.color = (0.90, 0.95, 1) if key else (0.40, 0.53, 0.72)
        lamp['nominal_phase_angle'] = phase if key else 0
    optical_shell(planet, 'Phengos_Dawn_Optics_' + prefix + '_v11',
                  planet['scene_radius'] * 0.009, halo_color, 1.5, 20, key_direction)
    planet['surface_source'] = 'NASA SVS CGI Moon Kit LROC/LOLA; fictional recolored terrain'
    planet_records.append({'planet':planet.name,'key_phase_degrees':phase,
                           'illuminated_fraction':(1 + math.cos(math.radians(phase))) / 2,
                           'side':'left' if side < 0 else 'right','key_direction':list(key_direction)})

records = json.loads(source['scale_record'])
for record in records:
    record['object'] = copies[record['object']].name
scene['scale_record'] = json.dumps(records)
scene['dawn_rig_record'] = json.dumps(planet_records)
scene['planet_depth_strength'] = 1.0
scene['horizon_camera_altitude_km'] = altitude_km
scene['horizon_mode'] = 'SILVER_OPTICS'
scene['horizon_optics_note'] = 'Camera-only smooth limb shells; art-directed, not physical scattering'
scene['user_setup_source'] = source.name
scene['publication_status'] = '600 km silver horizon still study; no movie/browser replacement'
scene.cycles.samples = 128
scene.cycles.adaptive_threshold = 0.008
scene.frame_set(301)
actual_altitude = ((scene.camera.location - earth.location).length - radius) * scene['shared_scale_km_per_unit']
assert abs(actual_altitude - 600) < 0.01
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v11-silver-horizon.blend')
print(json.dumps({'scene':scene.name,'altitude_km':actual_altitude,
                  'planet_dawn':planet_records,'objects':len(scene.objects),'optical_shells':4}))
