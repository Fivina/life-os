"""Reference-match composition, bounded character lighting and continuous blue sky."""
import bpy
import json
import math
import random
from mathutils import Vector, Quaternion

OUT = 'E:/LifeOS-Art/phengos'
SOURCE = 'Phengos_Cinematic_Hierarchy_v15'
NAME = 'Phengos_Reference_v16'
source = bpy.data.scenes[SOURCE]
bpy.context.window.scene = source
source.frame_set(1)
assert NAME not in bpy.data.scenes
scene = source.copy()
scene.name = NAME
scene.use_fake_user = True
copies = {}
for original in list(scene.objects):
    obj = original.copy()
    if original.data:
        obj.data = original.data.copy()
        if obj.data.animation_data and obj.data.animation_data.action:
            obj.data.animation_data.action = obj.data.animation_data.action.copy()
        for slot in obj.material_slots:
            if slot.material:
                slot.material = slot.material.copy()
                tree = slot.material.node_tree
                if tree.animation_data and tree.animation_data.action:
                    tree.animation_data.action = tree.animation_data.action.copy()
    if obj.animation_data and obj.animation_data.action:
        obj.animation_data.action = obj.animation_data.action.copy()
    scene.collection.objects.link(obj)
    scene.collection.objects.unlink(original)
    copies[original.name] = obj
receivers = {}
for original in source.objects:
    obj = copies[original.name]
    collection = original.light_linking.receiver_collection
    if collection:
        if collection.name not in receivers:
            linked = bpy.data.collections.new(collection.name + '_v16')
            for receiver in collection.objects:
                linked.objects.link(copies[receiver.name])
            receivers[collection.name] = linked
        obj.light_linking.receiver_collection = receivers[collection.name]
    if original.parent:
        obj.parent = copies[original.parent.name]
    if original.get('optical_body'):
        obj['optical_body'] = copies[original['optical_body']].name
scene.camera = copies[source.camera.name]
scene.world = source.world.copy()
scene.compositing_node_group = source.compositing_node_group.copy()
bpy.context.window.scene = scene


def enum(owner, prop, value):
    assert value in [i.identifier for i in owner.bl_rna.properties[prop].enum_items], (prop, value)
    setattr(owner, prop, value)


def node(tree, kind, label=''):
    result = tree.nodes.new(kind)
    result.label = label
    return result


def mathnode(tree, op, value=0, label=''):
    result = node(tree, 'ShaderNodeMath', label)
    enum(result, 'operation', op)
    result.inputs[1].default_value = value
    return result


def material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat, mat.node_tree


def emission(obj):
    return next(n for n in obj.data.materials[0].node_tree.nodes if n.type == 'EMISSION')


def labeled(tree, label):
    return next(n for n in tree.nodes if n.label == label)


def smooth(value):
    t = max(0, min(1, value))
    return t*t*t*(t*(6*t-15)+10)


def tangent(camera, center, radius):
    direction = camera - center
    distance = direction.length
    view = direction.normalized()
    up = (Vector((0, 1, 0)) - view*view.y).normalized()
    return center + view*(radius*radius/distance) + up*(radius*math.sqrt(1-radius*radius/distance**2))


earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
letters = {o.data.body:o for o in scene.objects if o.type == 'FONT'}
planets = [o for o in scene.objects if o.name.startswith(('Distant_Banded_Planet', 'Distant_Cobalt_Planet'))]
camera = scene.camera
camera.animation_data_clear()
camera.data.lens = 31
camera.data.dof.use_dof = False
camera.location = (0, 26, 110)
camera.rotation_euler = (-0.008, 0.025, 0)
initial_camera = camera.location.copy()
initial_rotation = camera.rotation_euler.copy()
earth_orientation = earth.rotation_quaternion.copy()
circle.animation_data_clear()
circle.visible_shadow = False
circle['erasure_contract'] = 'none; LIFE/S opacity fade'

# Optical character surface retains cool color at the luminous boundary.
mat, tree = material('Phengos_v16_Luminous_Volume_Impression')
circle.data.materials.clear()
circle.data.materials.append(mat)
geo = node(tree, 'ShaderNodeNewGeometry')
dot = node(tree, 'ShaderNodeVectorMath')
enum(dot, 'operation', 'DOT_PRODUCT')
tree.links.new(geo.outputs['Normal'], dot.inputs[0])
tree.links.new(geo.outputs['Incoming'], dot.inputs[1])
facing = mathnode(tree, 'ABSOLUTE')
tree.links.new(dot.outputs['Value'], facing.inputs[0])
ramp = node(tree, 'ShaderNodeValToRGB', 'Blue boundary through ice blue to hot center')
ramp.color_ramp.elements[0].color = (0.035, 0.17, 0.48, 1)
ramp.color_ramp.elements[1].position = 0.6
ramp.color_ramp.elements[1].color = (0.62, 0.84, 1, 1)
ramp.color_ramp.elements.new(0.18).color = (0.22, 0.5, 0.9, 1)
tree.links.new(facing.outputs[0], ramp.inputs[0])
character_emission = node(tree, 'ShaderNodeEmission', 'Bounded luminous character')
tree.links.new(ramp.outputs[0], character_emission.inputs['Color'])
character_emission.inputs['Strength'].default_value = 7
output = node(tree, 'ShaderNodeOutputMaterial')
edge = node(tree, 'ShaderNodeMapRange', 'Soft luminous circumference')
enum(edge, 'interpolation_type', 'SMOOTHSTEP')
edge.inputs['From Min'].default_value = 0
edge.inputs['From Max'].default_value = 0.3
edge.clamp = True
tree.links.new(facing.outputs[0], edge.inputs['Value'])
transparent = node(tree, 'ShaderNodeBsdfTransparent')
surface = node(tree, 'ShaderNodeMixShader')
tree.links.new(edge.outputs['Result'], surface.inputs[0])
tree.links.new(transparent.outputs[0], surface.inputs[1])
tree.links.new(character_emission.outputs[0], surface.inputs[2])
tree.links.new(surface.outputs[0], output.inputs['Surface'])
for polygon in circle.data.polygons:
    polygon.use_smooth = True
if len(circle.data.vertices) < 12000:
    subdiv = circle.modifiers.new('Smooth luminous silhouette', 'SUBSURF')
    subdiv.levels = 2
    subdiv.render_levels = 2

# True opacity replaces the old spatial clipping graph completely.
opacity = {}
letter_emission = {}
for char, obj in letters.items():
    obj.animation_data_clear()
    mat, tree = material('Phengos_v16_Letter_' + char)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    text_emission = node(tree, 'ShaderNodeEmission')
    text_emission.inputs['Color'].default_value = (0.62, 0.79, 1, 1)
    text_emission.inputs['Strength'].default_value = 2.8
    transparent = node(tree, 'ShaderNodeBsdfTransparent')
    mix = node(tree, 'ShaderNodeMixShader', 'Continuous LIFE/S opacity; no eraser')
    tree.links.new(transparent.outputs[0], mix.inputs[1])
    tree.links.new(text_emission.outputs[0], mix.inputs[2])
    output = node(tree, 'ShaderNodeOutputMaterial')
    tree.links.new(mix.outputs[0], output.inputs['Surface'])
    opacity[char] = mix.inputs[0]
    letter_emission[char] = text_emission.inputs['Strength']
    obj['erasure_contract'] = 'none; continuous opacity'

# Earth's dim settlements are suppressed smoothly, retaining the bright centers.
tree = earth.data.materials[0].node_tree
bsdf = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
cities = labeled(tree, 'Regional satellite detail with global fallback')
city_color = labeled(tree, 'Restrained warm settlement light')
power = mathnode(tree, 'POWER', 1.65, 'Suppress weak city networks; preserve strongest settlements')
threshold = mathnode(tree, 'SUBTRACT', 0.12, 'Quiet low-radiance settlements')
threshold.use_clamp = True
tree.links.new(cities.outputs[0], threshold.inputs[0])
tree.links.new(threshold.outputs[0], power.inputs[0])
tree.links.new(power.outputs[0], city_color.inputs[1])
bsdf.inputs['Emission Strength'].default_value = 0.72
fill = next(o for o in scene.objects if o.get('rig_role') == 'restrained_night_surface_fill')
fill.data.animation_data_clear()
fill.data.energy *= 2.4
fill.data.color = (0.18, 0.34, 0.65)

# Phengos has no Earth reflection receiver and never illuminates the sky.
planet_receivers = bpy.data.collections.new('Phengos_v16_Only_Planet_Receivers')
for obj in planets:
    planet_receivers.objects.link(obj)
circle.light_linking.receiver_collection = planet_receivers
for obj in scene.objects:
    if obj.get('art_role') in ('restricted atmospheric reflection', 'Phengos moving point light'):
        obj.hide_render = True
        if obj.type == 'LIGHT':
            obj.data.animation_data_clear()
            obj.data.energy = 0
    if obj.get('optical_role') == 'earth_limb':
        tree = obj.data.materials[0].node_tree
        tree.animation_data_clear()
        spark = next((n for n in tree.nodes if n.label == 'Art-directed Phengos atmospheric spark'), None)
        if spark:
            spark.inputs[1].default_value = 0
        primary = any(n.label == 'Gentle central silver highlight' for n in tree.nodes)
        labeled(tree, 'Smooth optical limb width').inputs[1].default_value = 95 if primary else 30
        emission(obj).inputs['Color'].default_value = (0.24, 0.49, 1, 1)
    if obj.get('optical_role') == 'planet_dawn_limb':
        obj.data.materials[0].node_tree.animation_data_clear()
        emission(obj).inputs['Color'].default_value = (0.12, 0.35, 0.9, 1)
        emission(obj).inputs['Strength'].default_value = 0.9 if 'Banded' in obj.name else 1.2
    if obj.type == 'LIGHT' and 'planet_depth_base_energy' in obj:
        obj.data.animation_data_clear()
        obj.data.energy *= 0.5 if '_key' in obj.name else 0.3
planet_light = next(o for o in scene.objects if o.get('art_role') == 'Phengos cinematic distant-planet point light')
planet_light.data.animation_data_clear()
planet_light.light_linking.receiver_collection = planet_receivers
planet_light.data.shadow_soft_size = 12
planet_light.data.color = (0.24, 0.53, 1)

# The enclosing panorama is camera-only, continuous, and independently luminous.
sky = next(o for o in scene.objects if o.get('art_role') == 'surrounding sky')
stars = next(o for o in scene.objects if o.get('art_role') == 'surrounding stars')
sky.hide_render = True
stars.hide_render = True
scene.world = bpy.data.worlds.new('Phengos_v16_Independent_Distant_Space')
scene.world.use_nodes = True
tree = scene.world.node_tree
tree.nodes.clear()
coords = node(tree, 'ShaderNodeTexCoord')
mapping = node(tree, 'ShaderNodeMapping', 'Fixed celestial orientation across the camera flight')
mapping.inputs['Rotation'].default_value = (0.4, 0, 1.0)
tree.links.new(coords.outputs['Normal'], mapping.inputs['Vector'])
env = node(tree, 'ShaderNodeTexEnvironment', 'Blue star clouds, independent of Phengos')
env.image = bpy.data.images.load('D:/Life OS/New Design/phengos-cloud-only-environment-v16.png', check_existing=True)
enum(env, 'interpolation', 'Cubic')
tree.links.new(mapping.outputs[0], env.inputs[0])
background = node(tree, 'ShaderNodeBackground', 'Fixed distant sky radiance')
background.inputs['Strength'].default_value = 0.5
tree.links.new(env.outputs['Color'], background.inputs['Color'])
black = node(tree, 'ShaderNodeBackground')
black.inputs['Strength'].default_value = 0
path = node(tree, 'ShaderNodeLightPath')
mix = node(tree, 'ShaderNodeMixShader')
tree.links.new(path.outputs['Is Camera Ray'], mix.inputs[0])
tree.links.new(black.outputs[0], mix.inputs[1])
tree.links.new(background.outputs[0], mix.inputs[2])
output = node(tree, 'ShaderNodeOutputWorld')
tree.links.new(mix.outputs[0], output.inputs[0])

# The film samples a bounded inner spherical dome at useful texel density.
# Its edges are outside every verified camera frustum throughout the ascent.
sky.hide_render = False
vertices, faces, uv_values = [], [], []
columns, rows = 160, 128
for row in range(rows+1):
    v = row/rows
    latitude = math.radians(-38+128*v)
    for column in range(columns+1):
        u = column/columns
        longitude = math.radians(-55+110*u)
        vertices.append((11000*math.cos(latitude)*math.sin(longitude),
                         11000*math.sin(latitude),
                         -11000*math.cos(latitude)*math.cos(longitude)))
        # Angular UV scale keeps stars round near the optical axis. The final
        # camera move stays below the quiet clamped upper edge of this plate.
        uv_values.append((0.5+(-55+110*u)/190, 0.5+(-38+128*v-14)/95))
for row in range(rows):
    for column in range(columns):
        a = row*(columns+1)+column
        faces.append((a, a+1, a+columns+2, a+columns+1))
mesh = bpy.data.meshes.new('Phengos_v16_Inner_Celestial_Dome')
mesh.from_pydata(vertices, [], faces)
mesh.update()
uv = mesh.uv_layers.new(name='Continuous cinematic sky')
for poly in mesh.polygons:
    poly.use_smooth = True
    for loop_index in poly.loop_indices:
        uv.data[loop_index].uv = uv_values[mesh.loops[loop_index].vertex_index]
sky.data = mesh
mat, tree = material('Phengos_v16_Quiet_Azure_Dome')
sky.data.materials.append(mat)
texture = node(tree, 'ShaderNodeTexImage', 'Clean blue clouds with brighter inner tones')
texture.image = env.image
enum(texture, 'interpolation', 'Cubic')
enum(texture, 'extension', 'EXTEND')
sky_emission = node(tree, 'ShaderNodeEmission', 'Independent distant celestial radiance')
sky_emission.inputs['Strength'].default_value = 0.5
# Filter baked pinpoints and fine grain in the cloud plate. Crisp distant stars
# are supplied independently at native render resolution below.
uv_coord = node(tree, 'ShaderNodeTexCoord')
average = None
for dx, dy, weight in ((0,0,4), (-1,0,2), (1,0,2), (0,-1,2), (0,1,2),
                       (-1,-1,1), (-1,1,1), (1,-1,1), (1,1,1)):
    tap = texture if average is None else node(tree, 'ShaderNodeTexImage')
    tap.image = env.image
    enum(tap, 'interpolation', 'Cubic')
    enum(tap, 'extension', 'EXTEND')
    offset = node(tree, 'ShaderNodeVectorMath')
    enum(offset, 'operation', 'ADD')
    offset.inputs[1].default_value = (dx*0.005, dy*0.01, 0)
    tree.links.new(uv_coord.outputs['UV'], offset.inputs[0])
    tree.links.new(offset.outputs[0], tap.inputs['Vector'])
    weighted = node(tree, 'ShaderNodeVectorMath')
    enum(weighted, 'operation', 'SCALE')
    weighted.inputs['Scale'].default_value = weight/16
    tree.links.new(tap.outputs['Color'], weighted.inputs[0])
    if average is None:
        average = weighted.outputs[0]
    else:
        add_cloud = node(tree, 'ShaderNodeVectorMath')
        enum(add_cloud, 'operation', 'ADD')
        tree.links.new(average, add_cloud.inputs[0])
        tree.links.new(weighted.outputs[0], add_cloud.inputs[1])
        average = add_cloud.outputs[0]
tree.links.new(average, sky_emission.inputs['Color'])
output = node(tree, 'ShaderNodeOutputMaterial')
tree.links.new(sky_emission.outputs[0], output.inputs['Surface'])
for prop in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_shadow'):
    setattr(sky, prop, False)
background.inputs['Strength'].default_value = 0
sky['projection_contract'] = 'Concave spherical dome; visible flight arc mapped without a polar pinch'

# Fine subpixel highlights carry depth without a patterned star distribution.
rng = random.Random(16002)
vertices, faces = [], []
for index in range(950):
    longitude = math.radians(rng.uniform(-54, 54))
    latitude = math.radians(rng.uniform(-36, 85))
    direction = Vector((math.cos(latitude)*math.sin(longitude), math.sin(latitude),
                        -math.cos(latitude)*math.cos(longitude)))
    right = direction.cross(Vector((0,1,0))).normalized()
    up = right.cross(direction).normalized()
    center = direction*10000
    radius = rng.uniform(2, 4.5)
    start = len(vertices)
    vertices.extend([center+radius*(right*math.cos(a*math.pi/4)+up*math.sin(a*math.pi/4)) for a in range(8)])
    faces.append(tuple(range(start, start+8)))
mesh = bpy.data.meshes.new('Phengos_v16_Irregular_Faint_Stars')
mesh.from_pydata(vertices, [], faces)
mesh.update()
stars.data = mesh
stars.hide_render = False
for strength in (0.3, 0.65, 1.1, 2.0):
    mat, tree = material('Phengos_v16_Faint_Stars_'+str(strength))
    light = node(tree, 'ShaderNodeEmission')
    light.inputs['Color'].default_value = (0.28, 0.52, 0.85, 1)
    light.inputs['Strength'].default_value = strength
    output = node(tree, 'ShaderNodeOutputMaterial')
    tree.links.new(light.outputs[0], output.inputs['Surface'])
    mesh.materials.append(mat)
for poly in mesh.polygons:
    poly.material_index = rng.choices(range(4), weights=(5,3,2,1))[0]

# Keep the finite source geometrically behind the opening horizon.
sun = next(o for o in scene.objects if o.get('art_role') == 'geometrically occluded sunrise')
sun.animation_data_clear()
sun.data.materials[0].node_tree.animation_data_clear()
limb = tangent(initial_camera, earth.location, 480)
slope = (limb.y-initial_camera.y)/(initial_camera.z-limb.z)
sun.location = (0, initial_camera.y+(slope+0.0015)*8100, initial_camera.z-8100)
sun.scale = (8, 8, 8)
emission(sun).inputs['Strength'].default_value = 1800
sun.pass_index = 104

# Thin bounded volume provides actual scattered backlight beneath the optical rim.
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
atmosphere.hide_render = False
atmosphere.location = earth.location
radius = max(v.co.length for v in atmosphere.data.vertices)
atmosphere.scale = (482.2/radius,)*3
mat, tree = material('Phengos_v16_Thin_Exponential_Atmosphere')
atmosphere.data.materials.clear()
atmosphere.data.materials.append(mat)
geo = node(tree, 'ShaderNodeNewGeometry')
distance = node(tree, 'ShaderNodeVectorMath')
enum(distance, 'operation', 'DISTANCE')
tree.links.new(geo.outputs['Position'], distance.inputs[0])
distance.inputs[1].default_value = earth.location
height = mathnode(tree, 'SUBTRACT', 480)
tree.links.new(distance.outputs['Value'], height.inputs[0])
bounded_height = mathnode(tree, 'MAXIMUM', 0, 'Bound density inside the opaque planet')
tree.links.new(height.outputs[0], bounded_height.inputs[0])
decay = mathnode(tree, 'MULTIPLY', -1.4)
tree.links.new(bounded_height.outputs[0], decay.inputs[0])
exp = mathnode(tree, 'EXPONENT')
tree.links.new(decay.outputs[0], exp.inputs[0])
density = mathnode(tree, 'MULTIPLY', 0.005)
tree.links.new(exp.outputs[0], density.inputs[0])
scatter = node(tree, 'ShaderNodeVolumeScatter', 'Real low-density atmospheric scatter')
scatter.inputs['Color'].default_value = (0.22, 0.45, 0.85, 1)
scatter.inputs['Anisotropy'].default_value = 0.35
tree.links.new(density.outputs[0], scatter.inputs['Density'])
output = node(tree, 'ShaderNodeOutputMaterial')
tree.links.new(scatter.outputs[0], output.inputs['Volume'])
atmosphere.pass_index = 104
data = bpy.data.lights.new('Phengos_v16_Distant_Solar_Backlight', 'SUN')
data.energy = 3.5
data.angle = math.radians(0.53)
solar_light = bpy.data.objects.new(data.name, data)
scene.collection.objects.link(solar_light)
solar_light.rotation_euler = (earth.location-sun.location).to_track_quat('-Z', 'Y').to_euler()
solar_receivers = bpy.data.collections.new('Phengos_v16_Solar_Atmosphere')
solar_receivers.objects.link(earth)
solar_receivers.objects.link(atmosphere)
solar_light.light_linking.receiver_collection = solar_receivers
solar_light['art_role'] = 'distant directional atmosphere illumination'

# Isolated glow paths preserve the sharp title and warm city accents.
tree = scene.compositing_node_group
tree.nodes.clear()
render = node(tree, 'CompositorNodeRLayers')
render.scene = scene
output = node(tree, 'NodeGroupOutput')
for layer in scene.view_layers:
    layer.use_pass_object_index = True
    layer.update_render_passes()


def rgba(sockets, name):
    return next(s for s in sockets if s.name == name and s.type == 'RGBA')


def color_mix(mode):
    n = node(tree, 'ShaderNodeMix')
    enum(n, 'data_type', 'RGBA')
    enum(n, 'blend_type', mode)
    n.clamp_result = False
    next(s for s in n.inputs if s.name == 'Factor' and s.type == 'VALUE').default_value = 1
    return n


def halo(index, strength, size, tint, label):
    mask = node(tree, 'CompositorNodeIDMask', label)
    mask.inputs['Index'].default_value = index
    mask.inputs['Anti-Alias'].default_value = True
    tree.links.new(render.outputs['Object Index'], mask.inputs['ID value'])
    isolate = color_mix('MULTIPLY')
    tree.links.new(render.outputs['Image'], rgba(isolate.inputs, 'A'))
    tree.links.new(mask.outputs[0], rgba(isolate.inputs, 'B'))
    glare = node(tree, 'CompositorNodeGlare', label)
    original_glare = next(n for n in source.compositing_node_group.nodes if n.type == 'GLARE')
    glare.inputs['Type'].default_value = original_glare.inputs['Type'].default_value
    glare.inputs['Quality'].default_value = 'High'
    glare.inputs['Threshold'].default_value = 0.8
    glare.inputs['Strength'].default_value = strength
    glare.inputs['Size'].default_value = size
    glare.inputs['Tint'].default_value = tint
    tree.links.new(rgba(isolate.outputs, 'Result'), glare.inputs['Image'])
    return glare.outputs['Glare']


circle_halo = halo(101, 1.3, 0.25, (0.28, 0.56, 1, 1), 'Phengos soft cool halo')
outer_halo = halo(101, 0.25, 0.5, (0.10, 0.28, 0.65, 1), 'Phengos broad faint blue falloff')
earth_halo = halo(104, 2.8, 0.35, (0.22, 0.46, 1, 1), 'Atmospheric sunrise halo')
add = color_mix('ADD')
tree.links.new(render.outputs['Image'], rgba(add.inputs, 'A'))
tree.links.new(circle_halo, rgba(add.inputs, 'B'))
add2 = color_mix('ADD')
tree.links.new(rgba(add.outputs, 'Result'), rgba(add2.inputs, 'A'))
tree.links.new(earth_halo, rgba(add2.inputs, 'B'))
add3 = color_mix('ADD')
tree.links.new(rgba(add2.outputs, 'Result'), rgba(add3.inputs, 'A'))
tree.links.new(outer_halo, rgba(add3.inputs, 'B'))
tree.links.new(rgba(add3.outputs, 'Result'), output.inputs['Image'])

positions = {}
cursor = 0
for char in ('L', 'I', 'F', 'E', 'O', 'S'):
    if char == 'O':
        diameter = circle['wordmark_o_height']*1.1
        o_x = cursor+diameter/2
        cursor += diameter
    else:
        bounds = [v[0] for v in letters[char].bound_box]
        positions[char] = cursor-min(bounds)*0.9
        cursor += (max(bounds)-min(bounds))*0.9
    cursor += 0.46
center = (cursor-0.46)/2
positions = {char:x-center for char,x in positions.items()}
o_x -= center
end_scale = circle['wordmark_title_scale']*40*1.4
for frame in range(1, 512):
    seconds = (frame-1)/60
    retreat = smooth(seconds/5)
    flight_time = max(0, min(1, (seconds-5)/3.5))
    flight = smooth(flight_time)
    trail = smooth((seconds-5.4)/3.1)
    camera.location = (0, 26+120*trail, 110+35*retreat)
    camera.rotation_euler = initial_rotation
    size = 34+6*retreat
    depth = 260-30*retreat
    # Local camera-plane staging preserves the O's initial role in LIFE OS.
    word_y = 1.5*(1-retreat)
    center_shift = -o_x*smooth((seconds-3.5)/1.5)
    for char, obj in letters.items():
        local = Vector(((positions[char]+center_shift)*size,
                        word_y+circle['wordmark_baseline']*size*0.9, -depth))
        obj.location = camera.location + initial_rotation.to_matrix() @ local
        obj.rotation_euler = initial_rotation
        obj.scale = (size*0.9,)*3
        obj.keyframe_insert('location', frame=frame)
        obj.keyframe_insert('scale', frame=frame)
        visibility = 1-smooth((seconds-2.6)/2.2)
        opacity[char].default_value = visibility
        opacity[char].keyframe_insert('default_value', frame=frame)
        letter_emission[char].default_value = 2.8*visibility**1.2
        letter_emission[char].keyframe_insert('default_value', frame=frame)
    if seconds <= 5:
        local = Vector(((o_x+center_shift)*size, word_y, -depth))
        circle.location = camera.location + initial_rotation.to_matrix() @ local
        scale = circle['wordmark_title_scale']*size*(1.1+0.3*smooth((seconds-2.6)/2.4))
    else:
        start = Vector((0, 26, 145)) + initial_rotation.to_matrix() @ Vector((0, 0, -230))
        circle.location = start + Vector((0, 550*flight, -320*flight))
        offset = circle.location-camera.location
        lead = math.radians(11)*math.sin(math.pi*flight_time)**2
        camera.rotation_euler = (math.atan2(offset.y,-offset.z)-lead,
                                 -math.atan2(offset.x,-offset.z), 0)
        scale = end_scale*offset.length/230
    circle.scale = (scale,)*3
    circle.keyframe_insert('location', frame=frame)
    circle.keyframe_insert('scale', frame=frame)
    camera.keyframe_insert('location', frame=frame)
    camera.keyframe_insert('rotation_euler', frame=frame)
    character_emission.inputs['Strength'].default_value = 7+4*smooth((seconds-2.6)/2.4)
    character_emission.inputs['Strength'].keyframe_insert('default_value', frame=frame)
    planet_light.data.energy = 2800000*(1+0.4*smooth((seconds-2.6)/2.4))
    planet_light.data.keyframe_insert('energy', frame=frame)
    emission(sun).inputs['Strength'].default_value = 1800*(1-retreat)**2
    emission(sun).inputs['Strength'].keyframe_insert('default_value', frame=frame)
    data.energy = 3.5*(1-0.8*retreat)
    data.keyframe_insert('energy', frame=frame)
    earth.rotation_quaternion = Quaternion((0,1,0), math.radians(0.75*retreat+0.525*flight)) @ earth_orientation
    earth.keyframe_insert('rotation_quaternion', frame=frame)
    for obj in scene.objects:
        if obj.get('optical_role') == 'earth_limb':
            tree = obj.data.materials[0].node_tree
            gain = next((n for n in tree.nodes if n.label == 'Gentle central silver highlight'), None)
            if gain:
                gain.inputs[1].default_value = 24*(1-0.92*retreat)
                gain.inputs[2].default_value = 12*(1-0.7*retreat)
                gain.inputs[1].keyframe_insert('default_value', frame=frame)
                gain.inputs[2].keyframe_insert('default_value', frame=frame)
            else:
                strength = emission(obj).inputs['Strength']
                strength.default_value = 3.1*(1-0.7*retreat)
                strength.keyframe_insert('default_value', frame=frame)

scene.frame_set(1)
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.fps = 60
scene.render.use_persistent_data = True
scene.cycles.use_denoising = True
scene.cycles.samples = 96
scene.cycles.adaptive_threshold = 0.01
scene['source_scene'] = SOURCE
scene['object_copy_map'] = json.dumps({name:obj.name for name,obj in copies.items()})
scene['latest_contract'] = 'LIFE/S fade, visible climb then camera follows; no Earth reflection; camera-only fixed sky'
scene['opening_altitude_km'] = ((camera.location-earth.location).length/480-1)*6371.0084
scene['publication_status'] = 'Reference-match review; not deployed'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/phengos-intro-v16-reference.blend')
print('PHENGOS_REFERENCE_AUTHORED', json.dumps({'scene':scene.name, 'objects':len(scene.objects),
                                             'altitude_km':scene['opening_altitude_km'],
                                             'environment_size':list(env.image.size)}))
