"""Growing horizon wordmark, visible character-led flight and continuous surrounding sky."""
import bpy
import json
import math
import random
from mathutils import Quaternion, Vector

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.data.scenes['Phengos_Luminous_Horizon_v12']
assert len(source.objects) == 37
assert 'Phengos_Character_Flight_v13' not in bpy.data.scenes
bpy.context.window.scene = source
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Character_Flight_v13'
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
receiver_copies = {}
for original in source.objects:
    receivers = original.light_linking.receiver_collection
    if receivers:
        if receivers.name not in receiver_copies:
            collection = bpy.data.collections.new(receivers.name + '_v13')
            for receiver in receivers.objects:
                collection.objects.link(copies[receiver.name])
            receiver_copies[receivers.name] = collection
        copies[original.name].light_linking.receiver_collection = receiver_copies[receivers.name]
    if original.get('optical_body'):
        copies[original.name]['optical_body'] = copies[original['optical_body']].name
scene.camera = copies[source.camera.name]
scene.camera.data.clip_end = 22000
scene.world = source.world.copy()
scene.compositing_node_group = source.compositing_node_group.copy()
for n in scene.compositing_node_group.nodes:
    if n.type == 'R_LAYERS':
        n.scene = scene
bpy.context.window.scene = scene

def enum_value(owner, key, value):
    assert value in [i.identifier for i in owner.bl_rna.properties[key].enum_items]
    return value

def node(tree, kind, label):
    n = tree.nodes.new(kind)
    n.label = label
    return n

def math_node(tree, operation, label, value=0):
    n = node(tree, 'ShaderNodeMath', label)
    n.operation = enum_value(n, 'operation', operation)
    n.inputs[1].default_value = value
    return n

def material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat, mat.node_tree

def smooth(t):
    t = min(1, max(0, t))
    return t*t*t*(t*(6*t-15)+10)

def tangent(camera_position, center, radius):
    offset = camera_position - center
    distance = offset.length
    view = offset.normalized()
    up = (Vector((0, 1, 0)) - view * view.y).normalized()
    return center + view * (radius*radius/distance) + up * (radius * math.sqrt(1-radius*radius/distance**2))

earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
circle = next(o for o in scene.objects if o.name.startswith('Phengos.'))
letters = [o for o in scene.objects if o.type == 'FONT']
letter_x = {o.name:o.location.x for o in letters}
earth_orientation = earth.rotation_quaternion.copy()
circle_emission = next(n for n in circle.data.materials[0].node_tree.nodes if n.type == 'EMISSION')

# Actual surrounding geometry provides new sky when the camera pans upward.
for obj in scene.objects:
    if obj.name.startswith(('Smooth_Infinite_Space', 'Sparse_Stars')):
        obj.hide_render = True
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=11000)
sky = bpy.context.object
sky.name = 'Phengos_Enclosing_Sky_v13'
sky['art_role'] = 'surrounding sky'
for polygon in sky.data.polygons:
    polygon.use_smooth = True
sky_mat, tree = material('Phengos_Quiet_Spherical_Space_v13')
sky.data.materials.append(sky_mat)
coords = node(tree, 'ShaderNodeTexCoord', 'Continuous spherical direction')
noise = node(tree, 'ShaderNodeTexNoise', 'Extremely smooth distant depth, not textured wallpaper')
noise.noise_dimensions = enum_value(noise, 'noise_dimensions', '3D')
noise.inputs['Scale'].default_value = 2
noise.inputs['Detail'].default_value = 0
tree.links.new(coords.outputs['Normal'], noise.inputs['Vector'])
ramp = node(tree, 'ShaderNodeValToRGB', 'Near-black with a restrained blue undertone')
ramp.color_ramp.elements[0].color = (0.0001, 0.00016, 0.0003, 1)
ramp.color_ramp.elements[1].color = (0.0008, 0.0012, 0.002, 1)
tree.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
emission = node(tree, 'ShaderNodeEmission', 'Quiet space radiance')
tree.links.new(ramp.outputs['Color'], emission.inputs['Color'])
emission.inputs['Strength'].default_value = 1
output = node(tree, 'ShaderNodeOutputMaterial', 'Surrounding space')
tree.links.new(emission.outputs[0], output.inputs['Surface'])
for key in ('visible_diffuse','visible_glossy','visible_transmission','visible_shadow'):
    setattr(sky, key, False)

rng = random.Random(6103)
vertices, faces = [], []
for index in range(1800):
    z = 1 - 2*(index+0.5)/1800
    angle = index * math.pi * (3-math.sqrt(5))
    direction = Vector((math.sqrt(1-z*z)*math.cos(angle),
                        math.sqrt(1-z*z)*math.sin(angle),z))
    axis = Vector((0,0,1)) if abs(z) < 0.95 else Vector((0,1,0))
    right = axis.cross(direction).normalized()
    up = direction.cross(right).normalized()
    size = rng.uniform(1.2,3.8) * (1.8 if index % 41 == 0 else 1)
    position = direction * 10000
    offset = len(vertices)
    vertices.extend([position+right*x*size+up*y*size for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))])
    faces.append(tuple(offset+i for i in range(4)))
mesh = bpy.data.meshes.new('Phengos_Spherical_Star_Field_v13')
mesh.from_pydata(vertices, [], faces)
mesh.update()
stars = bpy.data.objects.new('Phengos_Enclosing_Stars_v13', mesh)
scene.collection.objects.link(stars)
stars['art_role'] = 'surrounding stars'
stars_mat, tree = material('Phengos_Distant_Silver_Stars_v13')
stars.data.materials.append(stars_mat)
emission = node(tree, 'ShaderNodeEmission', 'Subordinate pale stars')
emission.inputs['Color'].default_value = (0.7,0.8,1,1)
emission.inputs['Strength'].default_value = 0.65
output = node(tree, 'ShaderNodeOutputMaterial', 'Star points')
tree.links.new(emission.outputs[0], output.inputs['Surface'])
for key in ('visible_diffuse','visible_glossy','visible_transmission','visible_shadow'):
    setattr(stars, key, False)

# Fixed sunrise geometry is actually occluded by Earth during retreat.
initial_limb = tangent(Vector((0,0,20)), earth.location, earth['scene_radius'])
limb_slope = initial_limb.y/(20-initial_limb.z)
sun = next(o for o in scene.objects if o.name.startswith('Distant_White_Sun'))
sun.name = 'Phengos_Central_Sunrise_v13'
sun.hide_render = False
sun.hide_viewport = False
sun.hide_set(False)
sun.location = (0,(limb_slope+0.0028)*820,-800)
old_radius = max(v.co.length for v in sun.data.vertices)
for v in sun.data.vertices:
    v.co *= 1.6/old_radius
sun.scale = (1,1,1)
sun.animation_data_clear()
sun['art_role'] = 'geometrically occluded sunrise'
sun.data.materials.clear()
sun_mat, sun_tree = material('Phengos_Sunrise_Glint_v13')
sun.data.materials.append(sun_mat)
sun_emission = node(sun_tree, 'ShaderNodeEmission', 'Fixed sunrise glint behind horizon')
sun_output = node(sun_tree, 'ShaderNodeOutputMaterial', 'Geometrically occluded glint')
sun_tree.links.new(sun_emission.outputs[0], sun_output.inputs['Surface'])
sun_emission.inputs['Color'].default_value = (1,0.95,0.85,1)
sun_emission.inputs['Strength'].default_value = 80
for key in ('visible_diffuse','visible_glossy','visible_transmission','visible_shadow'):
    setattr(sun, key, False)

# A transparent, reflective optical layer receives the real moving light only.
reflector = earth.copy()
reflector.name = 'Phengos_Atmospheric_Reflection_v13'
reflector.data = earth.data.copy()
reflector.animation_data_clear()
reflector.scale *= 1+0.5/earth['scene_radius']
reflector.data.materials.clear()
scene.collection.objects.link(reflector)
reflector['art_role'] = 'restricted atmospheric reflection'
reflect_mat, tree = material('Phengos_Thin_Reflective_Optics_v13')
reflector.data.materials.append(reflect_mat)
transparent = node(tree, 'ShaderNodeBsdfTransparent', 'Preserve dark terrain')
specular = node(tree, 'ShaderNodeBsdfPrincipled', 'Only restrained elongated reflection')
specular.inputs['Base Color'].default_value = (0.65,0.75,0.9,1)
specular.inputs['Metallic'].default_value = 1
specular.inputs['Roughness'].default_value = 0.25
specular.inputs['Anisotropic'].default_value = 0.85
specular.inputs['Anisotropic Rotation'].default_value = 0.25
path = node(tree, 'ShaderNodeLightPath', 'No indirect optical layer')
weight = math_node(tree,'MULTIPLY','Restrained direct-camera reflection',0.025)
tree.links.new(path.outputs['Is Camera Ray'],weight.inputs[0])
mix = node(tree, 'ShaderNodeMixShader', 'Thin optical reflection over Earth')
tree.links.new(weight.outputs[0],mix.inputs[0])
tree.links.new(transparent.outputs[0],mix.inputs[1])
tree.links.new(specular.outputs[0],mix.inputs[2])
output = node(tree, 'ShaderNodeOutputMaterial', 'Reflective optics, no surface emission')
tree.links.new(mix.outputs[0],output.inputs['Surface'])
receivers = bpy.data.collections.new('Phengos_v13_Moving_Light_Receivers')
receivers.objects.link(reflector)
light_data = bpy.data.lights.new('Phengos_Moving_Light_v13', enum_value(next(o.data for o in scene.objects if o.type=='LIGHT'),'type','POINT'))
light_data.color = (0.9,0.95,1)
light_data.shadow_soft_size = 0.35
light = bpy.data.objects.new('Phengos_Moving_Light_v13',light_data)
scene.collection.objects.link(light)
light.parent = circle
light.location = (0,0,0)
light.light_linking.receiver_collection = receivers
light['art_role'] = 'Phengos moving point light'

# The smooth rim gets an explicitly artistic linear glint tied to source position.
silver = next(o for o in scene.objects if o.get('optical_role')=='earth_limb'
              and any(n.label=='Gentle central silver highlight' for n in o.data.materials[0].node_tree.nodes))
tree = silver.data.materials[0].node_tree
position = next(n for n in tree.nodes if n.label=='Horizon center accent')
gain = next(n for n in tree.nodes if n.label=='Gentle central silver highlight')
emission = next(n for n in tree.nodes if n.type=='EMISSION')
center_x = math_node(tree,'SUBTRACT','Phengos projected atmospheric glint center')
tree.links.new(position.outputs['X'],center_x.inputs[0])
width = math_node(tree,'DIVIDE','Bounded horizontal glint width',10)
tree.links.new(center_x.outputs[0],width.inputs[0])
square = math_node(tree,'POWER','Smooth localized glint',2)
tree.links.new(width.outputs[0],square.inputs[0])
negative = math_node(tree,'MULTIPLY','Negative glint exponent',-1)
tree.links.new(square.outputs[0],negative.inputs[0])
gaussian = math_node(tree,'EXPONENT','Continuous glint, not grain')
tree.links.new(negative.outputs[0],gaussian.inputs[0])
spark = math_node(tree,'MULTIPLY','Art-directed Phengos atmospheric spark',10)
tree.links.new(gaussian.outputs[0],spark.inputs[0])
addition = math_node(tree,'ADD','Existing silver rim plus source-linked glint')
tree.links.new(gain.outputs[0],addition.inputs[0])
tree.links.new(spark.outputs[0],addition.inputs[1])
tree.links.new(addition.outputs[0],emission.inputs['Strength'])

trace = []
for frame in range(1,512):
    seconds = (frame-1)/60
    retreat = smooth(seconds/5)
    handoff = smooth((seconds-4)/1)
    flight_time = min(1,max(0,(seconds-5)/3.5))
    flight = smooth(flight_time)
    camera_trail = smooth((seconds-5.4)/3.1)
    scene.camera.location = (0,12*camera_trail,20+40*retreat)
    word_depth = 30-12*retreat
    word_size = 0.9+0.5*retreat
    word_y = -2.8*(1-retreat)
    glyph_z = scene.camera.location.z-word_depth
    for letter in letters:
        letter.scale = (word_size,word_size,word_size)
        letter.location = ((letter_x[letter.name]+0.6)*word_size,
                           word_y+circle['wordmark_baseline']*word_size,glyph_z)
        letter.keyframe_insert('location',frame=frame)
        letter.keyframe_insert('scale',frame=frame)
        nodes = letter.data.materials[0].node_tree.nodes
        fade = next(n for n in nodes if n.type=='MIX_SHADER')
        fade.inputs[0].default_value = smooth(seconds/1)*(1-handoff)
        fade.inputs[0].keyframe_insert('default_value',frame=frame)
    if seconds <= 5:
        circle.location = (1.8*word_size*(1-handoff),word_y,glyph_z)
        scale = circle['wordmark_title_scale']*word_size*(1-handoff)+handoff
        circle.scale = (scale,scale,scale)
        scene.camera.rotation_euler = (0,0,0)
    else:
        circle.location = (0,55*flight,42-36*flight)
        offset = circle.location-scene.camera.location
        actual_angle = math.atan2(offset.y,-offset.z)
        desired_lead = math.radians(13)*math.sin(math.pi*flight_time)**2
        pitch = max(0,actual_angle-desired_lead)
        scene.camera.rotation_euler = (pitch,0,0)
        # Preserve the character's readable angular size during real world-space flight.
        scale = offset.length/18
        circle.scale = (scale,scale,scale)
    scene.camera.keyframe_insert('location',frame=frame)
    scene.camera.keyframe_insert('rotation_euler',frame=frame)
    circle.keyframe_insert('location',frame=frame)
    circle.keyframe_insert('scale',frame=frame)
    circle_emission.inputs['Strength'].default_value = 2+6*handoff
    circle_emission.inputs['Strength'].keyframe_insert('default_value',frame=frame)
    light_data.energy = 40000*(1+3*handoff)
    light_data.keyframe_insert('energy',frame=frame)
    earth.rotation_quaternion = Quaternion((0,1,0),math.radians(0.75*retreat+0.525*flight))@earth_orientation
    earth.keyframe_insert('rotation_quaternion',frame=frame)
    for obj in scene.objects:
        if obj.get('optical_role')=='earth_limb':
            nodes = obj.data.materials[0].node_tree.nodes
            current_gain = next((n for n in nodes if n.label=='Gentle central silver highlight'),None)
            if current_gain:
                current_gain.inputs[1].default_value = 12.8*(1-0.65*retreat)
                current_gain.inputs[2].default_value = 16*(1-0.65*retreat)
                current_gain.inputs[1].keyframe_insert('default_value',frame=frame)
                current_gain.inputs[2].keyframe_insert('default_value',frame=frame)
            else:
                current_emission = next(n for n in nodes if n.type=='EMISSION')
                current_emission.inputs['Strength'].default_value = 1-0.65*retreat
                current_emission.inputs['Strength'].keyframe_insert('default_value',frame=frame)
        if obj.type=='LIGHT' and 'planet_depth_base_energy' in obj:
            obj.data.energy = obj['planet_depth_base_energy']*(1.15-0.4*retreat)
            obj.data.keyframe_insert('energy',frame=frame)
    rim = tangent(scene.camera.location,earth.location,earth['scene_radius'])
    center_x.inputs[1].default_value = circle.location.x/max(word_depth,18)*(scene.camera.location.z-rim.z)
    center_x.inputs[1].keyframe_insert('default_value',frame=frame)
    spark.inputs[1].default_value = 10*(1-flight)
    spark.inputs[1].keyframe_insert('default_value',frame=frame)
    if frame in (1,91,181,241,301,331,361,391,421,451,511):
        trace.append({'frame':frame,'camera':list(scene.camera.location),'circle':list(circle.location),
                      'pitch_degrees':math.degrees(scene.camera.rotation_euler.x)})

records = json.loads(source['scale_record'])
for record in records:
    record['object'] = copies[record['object']].name
scene['scale_record'] = json.dumps(records)
scene['user_setup_source'] = source.name
scene['flight_trace'] = json.dumps(trace)
scene['opening_motion'] = 'Camera retreats; near-horizon wordmark visibly grows toward center'
scene['character_flight'] = 'Circle leads by up to 13 degrees; camera trails and pans upward'
scene['background_contract'] = 'Enclosing 11000-unit sky sphere and 10000-unit star shell'
scene['sunrise_contract'] = 'Fixed finite sunrise is hidden by Earth geometry during retreat'
scene['reflection_contract'] = 'Receiver-linked moving point source plus explicitly artistic rim glint'
scene['publication_status'] = 'Character-led flight preview; browser film not replaced'
scene.render.use_persistent_data = True
scene.frame_set(301)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/phengos-intro-v13-character-flight.blend')
print('PHENGOS_FLIGHT_AUTHORED '+json.dumps({'scene':scene.name,'objects':len(scene.objects),'trace':trace}))
