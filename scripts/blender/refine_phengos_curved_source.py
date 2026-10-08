"""Test one continuous, camera-hidden hemispherical source behind the horizon."""
import bpy
import math
import json

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.context.scene
assert source.name == 'Phengos_Hidden_Horizon_v6'
assert len(source.collection.objects) == len(source.objects)
assert 'Phengos_Curved_Source_v7' not in bpy.data.scenes
source.frame_set(1)
scene = source.copy()
scene.name = 'Phengos_Curved_Source_v7'
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

# Light-link collections are not scene collections; explicitly remap their
# receivers, otherwise copied lights still target the prior revision's objects.
receiver_copies = {}
for original in source.objects:
    collection = original.light_linking.receiver_collection
    if collection:
        if collection.name not in receiver_copies:
            replacement = bpy.data.collections.new(collection.name + '_v7')
            for receiver in collection.objects:
                assert receiver.name in copies
                replacement.objects.link(copies[receiver.name])
            receiver_copies[collection.name] = replacement
        copies[original.name].light_linking.receiver_collection = receiver_copies[collection.name]

scene.camera = copies[source.camera.name]
scene.world = source.world.copy()
scene.compositing_node_group = source.compositing_node_group.copy()
for node in scene.compositing_node_group.nodes:
    if node.type == 'R_LAYERS':
        node.scene = scene
if bpy.context.window:
    bpy.context.window.scene = scene

for obj in scene.objects:
    if obj.type == 'LIGHT' and obj.get('rig_role') != 'planet_detail':
        obj.data.energy = 0

# Upper hemisphere: its nearest vertex is behind Earth's entire far surface.
# This is an invisible studio emitter, not a visible celestial body or shell.
radius = 190
segments = 96
rings = 32
vertices = [(0, radius, 0)]
for ring in range(1, rings + 1):
    theta = (math.pi / 2) * ring / rings
    for segment in range(segments):
        phi = 2 * math.pi * segment / segments
        vertices.append((radius * math.sin(theta) * math.cos(phi),
                         radius * math.cos(theta),
                         radius * math.sin(theta) * math.sin(phi)))
faces = []
for segment in range(segments):
    faces.append((0, 1 + segment, 1 + (segment + 1) % segments))
for ring in range(rings - 1):
    base = 1 + ring * segments
    following = base + segments
    for segment in range(segments):
        nxt = (segment + 1) % segments
        faces.append((base + segment, following + segment, following + nxt, base + nxt))
mesh = bpy.data.meshes.new('Phengos_Hemisphere_Emitter_Mesh')
mesh.from_pydata(vertices, [], faces)
mesh.update()
for polygon in mesh.polygons:
    polygon.use_smooth = True
emitter = bpy.data.objects.new('Phengos_Hidden_Hemisphere_v7', mesh)
scene.collection.objects.link(emitter)
emitter.location = (0, -176, -390)
emitter.visible_camera = False
emitter.visible_glossy = False
emitter.visible_transmission = False
emitter.display_type = 'WIRE'
receivers = bpy.data.collections.new('Phengos_v7_Curved_Source_Receivers')
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
receivers.objects.link(atmosphere)
emitter.light_linking.receiver_collection = receivers
material = bpy.data.materials.new('Phengos_Curved_Source_Emission_v7')
material.use_nodes = True
tree = material.node_tree
tree.nodes.clear()
emission = tree.nodes.new('ShaderNodeEmission')
emission.inputs['Color'].default_value = (0.92, 0.96, 1, 1)
emission.inputs['Strength'].default_value = 400
output = tree.nodes.new('ShaderNodeOutputMaterial')
tree.links.new(emission.outputs[0], output.inputs['Surface'])
emitter.data.materials.append(material)
emitter['emitter_role'] = 'continuous_curved_horizon'
emitter['source_radius'] = radius
scene['curved_source_strength'] = 400
scene['lighting_experiment'] = 'Single continuous hidden upper hemisphere; no horizon lamp row'
scene['publication_status'] = 'Curved-source lighting comparison only; not installed in app'
scene['user_setup_source'] = source.name
scene.frame_set(301)
bpy.ops.wm.save_as_mainfile(filepath=OUT + '/phengos-intro-v7-curved-source.blend')
print(json.dumps({'scene':scene.name, 'emitter_vertices':len(vertices), 'emitter_faces':len(faces),
                  'camera_visible':emitter.visible_camera, 'receiver':atmosphere.name,
                  'emitter_z_bounds':[-580,-200], 'row_sources_disabled':True}))
