"""Centered visible wordmark, Phengos-led erasure and a moving blue cinematic light rig."""
import bpy
import json
import math
from mathutils import Vector, Quaternion

OUT='E:/LifeOS-Art/phengos'
source=bpy.data.scenes['Phengos_Character_Flight_v13']
assert len(source.objects)==41
assert 'Phengos_Blue_Eraser_v14' not in bpy.data.scenes
bpy.context.window.scene=source
source.frame_set(1)
scene=source.copy()
scene.name='Phengos_Blue_Eraser_v14'
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
            collection=bpy.data.collections.new(receivers.name+'_v14')
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

def smooth(t):
    t=max(0,min(1,t))
    return t*t*t*(t*(6*t-15)+10)

def math_node(tree,operation,label):
    n=tree.nodes.new('ShaderNodeMath')
    assert operation in [i.identifier for i in n.bl_rna.properties['operation'].enum_items]
    n.operation=operation
    n.label=label
    return n

def input_node(tree,label):
    return next(n for n in tree.nodes if n.label==label)

earth=next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
earth_orientation=earth.rotation_quaternion.copy()
circle=next(o for o in scene.objects if o.name.startswith('Phengos.'))
letters={o.data.body:o for o in scene.objects if o.type=='FONT'}
base_x={body:o.location.x/0.9 for body,o in letters.items()}
extents={body:(base_x[body]+min(c[0] for c in o.bound_box),
               base_x[body]+max(c[0] for c in o.bound_box)) for body,o in letters.items()}
center=(min(v[0] for v in extents.values())+max(v[1] for v in extents.values()))/2
base_x={body:x-center for body,x in base_x.items()}
extents={body:(a-center,b-center) for body,(a,b) in extents.items()}
o_x=1.8-center
o_radius=circle['wordmark_o_height']/2
s_end=extents['S'][1]+o_radius+0.08
life_end=extents['L'][0]-o_radius-0.08
frontiers={}
for body,letter in letters.items():
    tree=letter.data.materials[0].node_tree
    tree.animation_data_clear()
    emission=next(n for n in tree.nodes if n.type=='EMISSION')
    emission.inputs['Color'].default_value=(0.46,0.72,1,1)
    emission.inputs['Strength'].default_value=2.1
    mix=next(n for n in tree.nodes if n.type=='MIX_SHADER')
    geometry=tree.nodes.new('ShaderNodeNewGeometry')
    geometry.label='World-space letter boundary, not a uniform alpha fade'
    split=tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(geometry.outputs['Position'],split.inputs[0])
    keep=math_node(tree,'GREATER_THAN' if body=='S' else 'LESS_THAN',
                   'Phengos spatial erasure frontier')
    tree.links.new(split.outputs['X'],keep.inputs[0])
    tree.links.new(keep.outputs[0],mix.inputs[0])
    mix.inputs[0].default_value=1
    frontiers[body]=keep.inputs[1]
    letter['erasure_contract']='binary spatial clipping behind the moving circle'

circle_tree=circle.data.materials[0].node_tree
circle_tree.animation_data_clear()
circle_emission=next(n for n in circle_tree.nodes if n.type=='EMISSION')
circle_emission.inputs['Color'].default_value=(0.22,0.5,1,1)
circle['character_color']='ice blue luminous source, not pure-white disk'
glare=next(n for n in scene.compositing_node_group.nodes if n.type=='GLARE')
glare.inputs['Threshold'].default_value=1.2
glare.inputs['Strength'].default_value=0.9
glare.inputs['Size'].default_value=0.22
sky=next(o for o in scene.objects if o.get('art_role')=='surrounding sky')
sky_tree=sky.data.materials[0].node_tree
sky_tree.animation_data_clear()
ramp=next(n for n in sky_tree.nodes if n.type=='VALTORGB')
ramp.color_ramp.elements[0].color=(0.0015,0.0045,0.013,1)
ramp.color_ramp.elements[1].color=(0.009,0.024,0.065,1)
sky_emission=next(n for n in sky_tree.nodes if n.type=='EMISSION')
stars=next(o for o in scene.objects if o.get('art_role')=='surrounding stars')
for polygon in stars.data.polygons:
    midpoint=sum((stars.data.vertices[i].co for i in polygon.vertices),Vector())/4
    for index in polygon.vertices:
        vertex=stars.data.vertices[index]
        vertex.co=midpoint+(vertex.co-midpoint)*1.7
star_emission=next(n for n in stars.data.materials[0].node_tree.nodes if n.type=='EMISSION')
star_emission.inputs['Color'].default_value=(0.5,0.72,1,1)
star_emission.inputs['Strength'].default_value=1.5

earth_light=next(o for o in scene.objects if o.get('art_role')=='Phengos moving point light')
earth_light.data.color=(0.32,0.65,1)
earth_light.data.animation_data_clear()
reflector=next(o for o in scene.objects if o.get('art_role')=='restricted atmospheric reflection')
reflect_tree=reflector.data.materials[0].node_tree
input_node(reflect_tree,'Restrained direct-camera reflection').inputs[1].default_value=0.045
planet_receivers=bpy.data.collections.new('Phengos_v14_Planet_Source_Receivers')
planets=[o for o in scene.objects if o.name.startswith(('Distant_Banded_Planet','Distant_Cobalt_Planet'))]
for planet in planets:
    planet_receivers.objects.link(planet)
planet_light_data=bpy.data.lights.new('Phengos_Blue_Planet_Source_v14','POINT')
planet_light_data.color=(0.32,0.65,1)
planet_light_data.shadow_soft_size=2
planet_light=bpy.data.objects.new('Phengos_Blue_Planet_Source_v14',planet_light_data)
scene.collection.objects.link(planet_light)
planet_light.parent=circle
planet_light.location=(0,0,0)
planet_light.light_linking.receiver_collection=planet_receivers
planet_light['art_role']='Phengos cinematic distant-planet point light'
planet_light['lighting_contract']='real source position; receiver-isolated cinematic gain, not astronomical luminosity'

silver=next(o for o in scene.objects if o.get('optical_role')=='earth_limb'
            and any(n.label=='Gentle central silver highlight' for n in o.data.materials[0].node_tree.nodes))
silver_tree=silver.data.materials[0].node_tree
silver_emission=next(n for n in silver_tree.nodes if n.type=='EMISSION')
silver_emission.inputs['Color'].default_value=(0.5,0.72,1,1)
glint_x=input_node(silver_tree,'Phengos projected atmospheric glint center').inputs[1]
glint_strength=input_node(silver_tree,'Art-directed Phengos atmospheric spark').inputs[1]
glint_width=input_node(silver_tree,'Bounded horizontal glint width').inputs[1]
glint_width.default_value=18

trace=[]
# Preserve the screen composition while putting the title deeper in the scene.
title_depth_scale=10
for frame in range(1,512):
    seconds=(frame-1)/60
    retreat=smooth(seconds/5)
    flight_time=max(0,min(1,(seconds-5)/3.5))
    flight=smooth(flight_time)
    camera_trail=smooth((seconds-5.4)/3.1)
    scene.camera.location=(0,12*title_depth_scale*camera_trail,20+40*retreat)
    word_depth=(26-4*retreat)*title_depth_scale
    word_size=(2.1+0.4*retreat)*title_depth_scale
    word_y=0.3*title_depth_scale*(1-retreat)
    glyph_z=scene.camera.location.z-word_depth
    if seconds<=2.8:
        eraser_x=o_x
    elif seconds<=3.35:
        eraser_x=o_x+(s_end-o_x)*smooth((seconds-2.8)/0.55)
    elif seconds<=4.65:
        eraser_x=s_end+(life_end-s_end)*smooth((seconds-3.35)/1.3)
    else:
        eraser_x=life_end*(1-smooth((seconds-4.65)/0.35))
    s_front=-100000 if seconds<2.8 else (
        eraser_x+o_radius if seconds<=3.35 else s_end+o_radius)
    life_front=100000 if seconds<3.35 else (
        eraser_x-o_radius if seconds<=4.65 else life_end-o_radius)
    for body,letter in letters.items():
        letter.location=(base_x[body]*word_size,
                         word_y+circle['wordmark_baseline']*word_size,glyph_z)
        letter.scale=(word_size,)*3
        letter.keyframe_insert('location',frame=frame)
        letter.keyframe_insert('scale',frame=frame)
        frontiers[body].default_value=(s_front if body=='S' else life_front)*word_size
        frontiers[body].keyframe_insert('default_value',frame=frame)
    end_scale=circle['wordmark_title_scale']*2.5*title_depth_scale
    if seconds<=5:
        circle.location=(eraser_x*word_size,word_y,glyph_z)
        circle.scale=(circle['wordmark_title_scale']*word_size,)*3
        scene.camera.rotation_euler=(0,0,0)
    else:
        circle.location=(0,55*title_depth_scale*flight,60-(22+32*flight)*title_depth_scale)
        offset=circle.location-scene.camera.location
        lead=math.radians(13)*math.sin(math.pi*flight_time)**2
        scene.camera.rotation_euler=(max(0,math.atan2(offset.y,-offset.z)-lead),0,0)
        circle.scale=(end_scale*offset.length/(22*title_depth_scale),)*3
    scene.camera.keyframe_insert('location',frame=frame)
    scene.camera.keyframe_insert('rotation_euler',frame=frame)
    circle.keyframe_insert('location',frame=frame)
    circle.keyframe_insert('scale',frame=frame)
    circle_emission.inputs['Strength'].default_value=8+6*smooth((seconds-2.8)/2.2)
    circle_emission.inputs['Strength'].keyframe_insert('default_value',frame=frame)
    earth_light.data.energy=80000*(1-0.65*flight)
    earth_light.data.keyframe_insert('energy',frame=frame)
    planet_light_data.energy=150000000*(1-0.85*flight)
    planet_light_data.keyframe_insert('energy',frame=frame)
    sky_emission.inputs['Strength'].default_value=(1-0.2*retreat)*(1-0.6*flight)
    sky_emission.inputs['Strength'].keyframe_insert('default_value',frame=frame)
    earth.rotation_quaternion=Quaternion((0,1,0),math.radians(0.75*retreat+0.525*flight))@earth_orientation
    earth.keyframe_insert('rotation_quaternion',frame=frame)
    for obj in scene.objects:
        if obj.get('optical_role')=='earth_limb':
            nodes=obj.data.materials[0].node_tree.nodes
            gain=next((n for n in nodes if n.label=='Gentle central silver highlight'),None)
            if gain:
                gain.inputs[1].default_value=18*(1-0.94*retreat)
                gain.inputs[2].default_value=12*(1-0.94*retreat)
                gain.inputs[1].keyframe_insert('default_value',frame=frame)
                gain.inputs[2].keyframe_insert('default_value',frame=frame)
            else:
                e=next(n for n in nodes if n.type=='EMISSION')
                e.inputs['Color'].default_value=(0.18,0.4,1,1)
                e.inputs['Strength'].default_value=1.8*(1-0.92*retreat)
                e.inputs['Strength'].keyframe_insert('default_value',frame=frame)
        if obj.type=='LIGHT' and 'planet_depth_base_energy' in obj:
            obj.data.energy=obj['planet_depth_base_energy']*(1.15-0.4*retreat)*(1-0.65*flight)
            obj.data.keyframe_insert('energy',frame=frame)
    glint_x.default_value=circle.location.x/word_depth*200
    glint_x.keyframe_insert('default_value',frame=frame)
    glint_strength.default_value=20*(1-0.9*retreat)*(1-flight)
    glint_strength.keyframe_insert('default_value',frame=frame)
    if frame in (1,121,169,193,202,241,280,301,361,391,511):
        trace.append({'frame':frame,'camera':list(scene.camera.location),'circle':list(circle.location),
                      'S_front':s_front,'LIFE_front':life_front,'sky_gain':sky_emission.inputs['Strength'].default_value})

records=json.loads(source['scale_record'])
for record in records:
    record['object']=copies[record['object']].name
scene['scale_record']=json.dumps(records)
scene['user_setup_source']=source.name
scene['flight_trace']=json.dumps(trace)
scene['opening_motion']='Large centered wordmark visible at frame one; grows during retreat'
scene['letter_removal']='Circle wipes S rightwards, LIFE leftwards, returns to center; no alpha fade'
scene['lighting_contract']='Blue character point sources move through real geometry; cinematic receiver gain; dimming horizon and sky'
scene['title_depth_scale']=title_depth_scale
scene['publication_status']='Blue eraser preview; browser film not replaced'
scene.render.use_persistent_data=True
scene.frame_set(1)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/phengos-intro-v14-blue-eraser.blend')
print('PHENGOS_BLUE_ERASER_AUTHORED '+json.dumps({'objects':len(scene.objects),'trace':trace}))
