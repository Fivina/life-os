"""Ensure the luminance pass cannot change meshes, camera or character choreography."""
import bpy
import json
from array import array

scene=bpy.data.scenes['Phengos_Cinematic_Hierarchy_v15']
source=bpy.data.scenes['Phengos_Blue_Eraser_v14']
mapping=json.loads(scene['object_copy_map'])
assert len(scene.objects)==len(source.objects)==len(mapping)==42
assert scene.camera.data.lens==source.camera.data.lens
assert scene.camera.data.sensor_width==source.camera.data.sensor_width
for name,copied_name in mapping.items():
    original=source.objects[name]
    obj=scene.objects[copied_name]
    assert obj.type==original.type
    if obj.type=='MESH':
        assert len(obj.data.vertices)==len(original.data.vertices)
        assert len(obj.data.polygons)==len(original.data.polygons)
        expected=array('f',[0])*len(original.data.vertices)*3
        actual=array('f',[0])*len(obj.data.vertices)*3
        original.data.vertices.foreach_get('co',expected)
        obj.data.vertices.foreach_get('co',actual)
        assert actual==expected, 'Mesh changed: '+name

def activate(s,frame):
    bpy.context.window.scene=s
    s.frame_set(frame)

def matrix_snapshot(s):
    return {o.name:[v for row in o.matrix_basis for v in row] for o in s.objects}

max_delta=0
for frame in range(1,512):
    activate(source,frame)
    expected=matrix_snapshot(source)
    activate(scene,frame)
    actual=matrix_snapshot(scene)
    for name,copied_name in mapping.items():
        delta=max(abs(a-b) for a,b in zip(expected[name],actual[copied_name]))
        max_delta=max(max_delta,delta)
        assert delta<0.00001, 'Motion changed: '+name+' frame '+str(frame)

circle=next(o for o in scene.objects if o.name.startswith('Phengos.'))
assert circle.pass_index==101
assert circle.light_linking.receiver_collection is not None
assert all(not o.name.startswith('Earth_Horizon')
           for o in circle.light_linking.receiver_collection.objects)
assert len(circle.light_linking.receiver_collection.objects)==3
assert all(o.pass_index!=101 for o in scene.objects if o is not circle)
tree=scene.compositing_node_group
mask=next(n for n in tree.nodes if n.type=='ID_MASK')
assert mask.inputs['Index'].default_value==101 and mask.inputs['Anti-Alias'].default_value
glare=next(n for n in tree.nodes if n.type=='GLARE')
isolated=glare.inputs['Image'].links[0].from_node
assert isolated.label=='Isolate the luminous character before bloom'
assert isolated.blend_type=='MULTIPLY'
assert next(i for i in isolated.inputs if i.name=='B' and i.type=='RGBA').links[0].from_node==mask
output=next(n for n in tree.nodes if n.type=='GROUP_OUTPUT')
add=output.inputs['Image'].links[0].from_node
assert add.blend_type=='ADD'
assert next(i for i in add.inputs if i.name=='A' and i.type=='RGBA').links[0].from_node.type=='R_LAYERS'
assert next(i for i in add.inputs if i.name=='B' and i.type=='RGBA').links[0].from_socket.name=='Glare'
checks=[]
for frame in (1,169,301,391,511):
    activate(source,frame)
    energies={o.name:o.data.energy for o in source.objects if o.type=='LIGHT'}
    original_circle=next(o for o in source.objects if o.name.startswith('Phengos.'))
    old_circle_strength=next(n for n in original_circle.data.materials[0].node_tree.nodes if n.type=='EMISSION').inputs['Strength'].default_value
    activate(scene,frame)
    circle_strength=next(n for n in circle.data.materials[0].node_tree.nodes if n.type=='EMISSION').inputs['Strength'].default_value
    assert abs(circle_strength-old_circle_strength*1.7)<0.001
    for name,copied_name in mapping.items():
        obj=scene.objects[copied_name]
        if obj.type=='LIGHT' and 'planet_depth_base_energy' in obj:
            large='Banded' in obj.name
            factor=(0.15 if large else 0.22) if '_key' in obj.name else (0.08 if large else 0.12)
            assert abs(obj.data.energy/energies[name]-factor)<0.001
    for letter in (o for o in scene.objects if o.type=='FONT'):
        mix=next(n for n in letter.data.materials[0].node_tree.nodes if n.type=='MIX_SHADER')
        assert mix.inputs[0].is_linked
        assert mix.inputs[0].links[0].from_node.label=='Phengos spatial erasure frontier'
    checks.append({'frame':frame,'circle_strength':circle_strength})
print('PHENGOS_COMPOSITING_VERIFY_PASS '+json.dumps({
    'frames_checked':511,'objects_preserved':42,'max_transform_delta':max_delta,
    'all_mesh_coordinates_identical':True,'bloom_isolated_to_character':True,
    'lighting_samples':checks,
}))
