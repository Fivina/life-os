"""Lighting-only cinematic hierarchy; preserve the blue-eraser composition and geometry."""
import bpy
import json

source=bpy.data.scenes['Phengos_Blue_Eraser_v14']
assert len(source.objects)==42
bpy.context.window.scene=source
source.frame_set(1)
scene=source.copy()
scene.name='Phengos_Cinematic_Hierarchy_v15'
scene.use_fake_user=True
copies={}
for original in list(scene.objects):
    obj=original.copy()
    if original.data:
        obj.data=original.data.copy()
        if obj.data.animation_data and obj.data.animation_data.action:
            obj.data.animation_data.action=obj.data.animation_data.action.copy()
        for slot in obj.material_slots:
            if slot.material:
                slot.material=slot.material.copy()
                tree=slot.material.node_tree
                if tree.animation_data and tree.animation_data.action:
                    tree.animation_data.action=tree.animation_data.action.copy()
    if obj.animation_data and obj.animation_data.action:
        obj.animation_data.action=obj.animation_data.action.copy()
    scene.collection.objects.link(obj)
    scene.collection.objects.unlink(original)
    copies[original.name]=obj
collections={}
for original in source.objects:
    receivers=original.light_linking.receiver_collection
    if receivers:
        if receivers.name not in collections:
            collection=bpy.data.collections.new(receivers.name+'_v15')
            for receiver in receivers.objects:
                collection.objects.link(copies[receiver.name])
            collections[receivers.name]=collection
        copies[original.name].light_linking.receiver_collection=collections[receivers.name]
    if original.get('optical_body'):
        copies[original.name]['optical_body']=copies[original['optical_body']].name
    if original.parent:
        copies[original.name].parent=copies[original.parent.name]
scene.camera=copies[source.camera.name]
scene.world=source.world.copy()
scene.compositing_node_group=source.compositing_node_group.copy()
for n in scene.compositing_node_group.nodes:
    if n.type=='R_LAYERS':
        n.scene=scene
bpy.context.window.scene=scene

def emission(obj):
    return next(n for n in obj.data.materials[0].node_tree.nodes if n.type=='EMISSION')

def labeled(tree,label):
    return next(n for n in tree.nodes if n.label==label)

circle=next(o for o in scene.objects if o.name.startswith('Phengos.'))
circle.pass_index=101
circle_emission=emission(circle)
circle_emission.inputs['Color'].default_value=(0.6,0.85,1,1)
letters=[o for o in scene.objects if o.type=='FONT']
for letter in letters:
    letter.pass_index=102
    e=emission(letter)
    e.inputs['Color'].default_value=(0.62,0.8,1,1)
    e.inputs['Strength'].default_value=3.4
earth=next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
earth.pass_index=103
principled=next(n for n in earth.data.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
principled.inputs['Emission Strength'].default_value=0.82
sky=next(o for o in scene.objects if o.get('art_role')=='surrounding sky')
sky.pass_index=106
sky_emission=emission(sky)
stars=next(o for o in scene.objects if o.get('art_role')=='surrounding stars')
stars.pass_index=107
emission(stars).inputs['Strength'].default_value=0.65
reflector=next(o for o in scene.objects if o.get('art_role')=='restricted atmospheric reflection')
reflect_tree=reflector.data.materials[0].node_tree
labeled(reflect_tree,'Restrained direct-camera reflection').inputs[1].default_value=0.003
reflect_bsdf=next(n for n in reflect_tree.nodes if n.type=='BSDF_PRINCIPLED')
reflect_bsdf.inputs['Anisotropic'].default_value=0.2
reflect_bsdf.inputs['Roughness'].default_value=0.4
# The hot mesh must not wash daylight over Earth's night terrain.
character_receivers=bpy.data.collections.new('Phengos_v15_Luminous_Source_Receivers')
character_receivers.objects.link(reflector)
for obj in scene.objects:
    if obj.name.startswith(('Distant_Banded_Planet','Distant_Cobalt_Planet')):
        character_receivers.objects.link(obj)
circle.light_linking.receiver_collection=character_receivers
sun=next(o for o in scene.objects if o.get('art_role')=='geometrically occluded sunrise')
emission(sun).inputs['Strength'].default_value=4
for obj in scene.objects:
    if obj.name.startswith(('Distant_Banded_Planet','Distant_Cobalt_Planet')):
        obj.pass_index=105
    if obj.get('optical_role')=='planet_dawn_limb':
        obj.pass_index=105
        e=emission(obj)
        e.inputs['Color'].default_value=(0.12,0.32,0.65,1)
        e.inputs['Strength'].default_value=0.15 if 'Banded' in obj.name else 0.22
    if obj.get('optical_role')=='earth_limb':
        obj.pass_index=104
        labeled(obj.data.materials[0].node_tree,'Smooth optical limb width').inputs[1].default_value=100
        emission(obj).inputs['Color'].default_value=(0.42,0.68,1,1)

# Index-isolated glare adds only Phengos's halo to the unblurred render.
for layer in scene.view_layers:
    layer.use_pass_object_index=True
    layer.update_render_passes()
tree=scene.compositing_node_group
render=next(n for n in tree.nodes if n.type=='R_LAYERS')
glare=next(n for n in tree.nodes if n.type=='GLARE')
output=next(n for n in tree.nodes if n.type=='GROUP_OUTPUT')
mask=tree.nodes.new('CompositorNodeIDMask')
mask.label='Phengos only; preserve typography and city sharpness'
mask.inputs['Index'].default_value=101
mask.inputs['Anti-Alias'].default_value=True
tree.links.new(render.outputs['Object Index'],mask.inputs['ID value'])

def color_mix(mode,label):
    node=tree.nodes.new('ShaderNodeMix')
    assert 'RGBA' in [i.identifier for i in node.bl_rna.properties['data_type'].enum_items]
    assert mode in [i.identifier for i in node.bl_rna.properties['blend_type'].enum_items]
    node.data_type='RGBA'
    node.blend_type=mode
    node.clamp_result=False
    node.label=label
    next(i for i in node.inputs if i.name=='Factor' and i.type=='VALUE').default_value=1
    return node

def rgba(sockets,name):
    return next(i for i in sockets if i.name==name and i.type=='RGBA')

isolate=color_mix('MULTIPLY','Isolate the luminous character before bloom')
tree.links.new(render.outputs['Image'],rgba(isolate.inputs,'A'))
tree.links.new(mask.outputs[0],rgba(isolate.inputs,'B'))
tree.links.new(rgba(isolate.outputs,'Result'),glare.inputs['Image'])
glare.inputs['Threshold'].default_value=1.2
glare.inputs['Strength'].default_value=1.7
glare.inputs['Size'].default_value=0.42
glare.inputs['Tint'].default_value=(0.3,0.6,1,1)
add=color_mix('ADD','Original crisp image plus restrained blue Phengos halo')
tree.links.new(render.outputs['Image'],rgba(add.inputs,'A'))
tree.links.new(glare.outputs['Glare'],rgba(add.inputs,'B'))
tree.links.new(rgba(add.outputs,'Result'),output.inputs['Image'])

for frame in range(1,512):
    source.frame_set(frame)
    scene.frame_set(frame)
    source_circle=next(o for o in source.objects if o.name.startswith('Phengos.'))
    circle_emission.inputs['Strength'].default_value=emission(source_circle).inputs['Strength'].default_value*1.7
    circle_emission.inputs['Strength'].keyframe_insert('default_value',frame=frame)
    sky_emission.inputs['Strength'].default_value=emission(next(o for o in source.objects if o.get('art_role')=='surrounding sky')).inputs['Strength'].default_value*0.12
    sky_emission.inputs['Strength'].keyframe_insert('default_value',frame=frame)
    for original in source.objects:
        obj=copies[original.name]
        if obj.type=='LIGHT' and 'planet_depth_base_energy' in obj:
            large='Banded' in obj.name
            factor=(0.15 if large else 0.22) if '_key' in obj.name else (0.08 if large else 0.12)
            obj.data.energy=original.data.energy*factor
            obj.data.color=(0.5,0.72,1) if '_key' in obj.name else (0.24,0.4,1)
            obj.data.keyframe_insert('energy',frame=frame)
        if obj.get('art_role')=='Phengos cinematic distant-planet point light':
            obj.data.energy=original.data.energy*0.08
            obj.data.keyframe_insert('energy',frame=frame)
        if obj.get('art_role')=='Phengos moving point light':
            obj.data.energy=original.data.energy*0.35
            obj.data.keyframe_insert('energy',frame=frame)
        if obj.get('optical_role')=='earth_limb':
            nodes=obj.data.materials[0].node_tree.nodes
            gain=next((n for n in nodes if n.label=='Gentle central silver highlight'),None)
            retreat=(scene.camera.location.z-20)/40
            if gain:
                gain.inputs[1].default_value=2*(1-0.8*retreat)
                gain.inputs[2].default_value=16*(1-0.75*retreat)
                gain.inputs[1].keyframe_insert('default_value',frame=frame)
                gain.inputs[2].keyframe_insert('default_value',frame=frame)
                spark=labeled(obj.data.materials[0].node_tree,'Art-directed Phengos atmospheric spark').inputs[1]
                original_spark=labeled(original.data.materials[0].node_tree,'Art-directed Phengos atmospheric spark').inputs[1]
                spark.default_value=original_spark.default_value*0.125
                spark.keyframe_insert('default_value',frame=frame)
            else:
                e=emission(obj)
                e.inputs['Strength'].default_value=0.65*(1-0.8*retreat)
                e.inputs['Strength'].keyframe_insert('default_value',frame=frame)

scene['composition_source']=source.name
scene['object_copy_map']=json.dumps({name:obj.name for name,obj in copies.items()})
scene['luminance_hierarchy']='black space < dark planets < warm cities < cool Earth rim < crisp typography < blue-white Phengos'
scene['bloom_contract']='Object-index 101 isolated character halo; no general-image or typography bloom'
scene['geometry_contract']='No mesh, position, camera, layout, orbit or eraser-motion edits'
scene['publication_status']='Cinematic luminance preview only; browser film not replaced'
scene.frame_set(1)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath='E:/LifeOS-Art/phengos/phengos-intro-v15-cinematic-hierarchy.blend')
print('PHENGOS_CINEMATIC_HIERARCHY_AUTHORED '+json.dumps({'objects':len(scene.objects),'source':source.name}))
