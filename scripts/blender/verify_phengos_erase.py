"""Verify visible text, spatial erasure, moving receivers and retreat/flight light changes."""
import bpy
import json
import math
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

scene=bpy.data.scenes['Phengos_Blue_Eraser_v14']
source=bpy.data.scenes['Phengos_Character_Flight_v13']
assert len(scene.objects)==42 and len(source.objects)==41
assert scene.camera.data is not source.camera.data
assert scene.camera.animation_data.action is not source.camera.animation_data.action
assert scene.compositing_node_group is not source.compositing_node_group
assert all(n.scene==scene for n in scene.compositing_node_group.nodes if n.type=='R_LAYERS')
bpy.context.window.scene=source
source.frame_set(511)
assert abs(source.camera.location.y-12)<0.001
assert all(not any(n.label=='Phengos spatial erasure frontier'
                   for n in o.data.materials[0].node_tree.nodes)
           for o in source.objects if o.type=='FONT')
bpy.context.window.scene=scene
letters={o.data.body:o for o in scene.objects if o.type=='FONT'}
circle=next(o for o in scene.objects if o.name.startswith('Phengos.'))
earth=next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
planets=[o for o in scene.objects if o.name.startswith(('Distant_Banded_Planet','Distant_Cobalt_Planet'))]
lights=[o for o in scene.objects if o.get('art_role') in (
    'Phengos moving point light','Phengos cinematic distant-planet point light')]
assert len(lights)==2
assert all(o.parent==circle and o.data.type=='POINT' for o in lights)
planet_light=next(o for o in lights if o.get('art_role')=='Phengos cinematic distant-planet point light')
assert set(planet_light.light_linking.receiver_collection.objects)==set(planets)
earth_light=next(o for o in lights if o is not planet_light)
assert all(o.get('art_role')=='restricted atmospheric reflection'
           for o in earth_light.light_linking.receiver_collection.objects)
circle_emission=next(n for n in circle.data.materials[0].node_tree.nodes if n.type=='EMISSION')
assert circle_emission.inputs['Color'].default_value[2]>circle_emission.inputs['Color'].default_value[0]
sky=next(o for o in scene.objects if o.get('art_role')=='surrounding sky')
sky_emission=next(n for n in sky.data.materials[0].node_tree.nodes if n.type=='EMISSION')
silver=next(o for o in scene.objects if o.get('optical_role')=='earth_limb'
            and any(n.label=='Gentle central silver highlight' for n in o.data.materials[0].node_tree.nodes))
gain=next(n for n in silver.data.materials[0].node_tree.nodes if n.label=='Gentle central silver highlight')

def corners(letter):
    return [letter.matrix_world@Vector(c) for c in letter.bound_box]

def visible_state(body):
    letter=letters[body]
    tree=letter.data.materials[0].node_tree
    mix=next(n for n in tree.nodes if n.type=='MIX_SHADER')
    assert mix.inputs[0].is_linked, 'No uniform alpha fade is allowed'
    frontier=mix.inputs[0].links[0].from_node
    assert frontier.label=='Phengos spatial erasure frontier'
    xs=[c.x for c in corners(letter)]
    threshold=frontier.inputs[1].default_value
    if body=='S':
        assert frontier.operation=='GREATER_THAN'
        return 'FULL' if min(xs)>threshold else 'GONE' if max(xs)<=threshold else 'PARTIAL'
    assert frontier.operation=='LESS_THAN'
    return 'FULL' if max(xs)<threshold else 'GONE' if min(xs)>=threshold else 'PARTIAL'

scene.frame_set(1)
assert all(visible_state(body)=='FULL' for body in letters)
projected=[world_to_camera_view(scene,scene.camera,c) for o in letters.values() for c in corners(o)]
opening_width=max(c.x for c in projected)-min(c.x for c in projected)
assert 0.4<opening_width<0.6, opening_width
assert min(c.y for c in projected)>0.45
assert scene.camera.location.z-circle.location.z>200, 'Wordmark belongs deeper in the scene'
initial_sky=sky_emission.inputs['Strength'].default_value
initial_horizon=gain.inputs[2].default_value
initial_planet_light=planet_light.data.energy
initial_directions={o.name:(o.location-planet_light.matrix_world.translation).normalized() for o in planets}
positions={o.name:o.location.copy() for o in planets+[earth]}

scene.frame_set(169)
projected=[world_to_camera_view(scene,scene.camera,c) for o in letters.values() for c in corners(o)]
grown_width=max(c.x for c in projected)-min(c.x for c in projected)
assert grown_width>opening_width
scene.frame_set(202)
assert visible_state('S')=='GONE'
assert all(visible_state(body)=='FULL' for body in 'LIFE')
scene.frame_set(241)
assert visible_state('S')==visible_state('E')=='GONE'
assert all(visible_state(body)=='FULL' for body in 'LIF')
scene.frame_set(280)
assert all(visible_state(body)=='GONE' for body in letters)
scene.frame_set(301)
assert all(visible_state(body)=='GONE' for body in letters)
assert abs(world_to_camera_view(scene,scene.camera,circle.location).x-0.5)<0.001
retreated_horizon=gain.inputs[2].default_value
assert retreated_horizon<0.1*initial_horizon

lead_peak=0
for frame in range(1,512):
    scene.frame_set(frame)
    assert all((scene.objects[name].location-p).length<0.001 for name,p in positions.items())
    assert all((o.matrix_world.translation-circle.matrix_world.translation).length<0.001 for o in lights)
    assert all(not o.hide_render for o in planets)
    if frame<=169:
        diameter=2*max(v.co.length for v in circle.data.vertices)*circle.scale.x
        assert abs(diameter-circle['wordmark_o_height']*letters['L'].scale.x)<0.01
    if frame>=280:
        assert all(visible_state(body)=='GONE' for body in letters), 'Erased text must not reappear'
    if frame>301:
        projected=world_to_camera_view(scene,scene.camera,circle.location)
        assert 0.05<projected.x<0.95 and 0.05<projected.y<0.95
        offset=circle.location-scene.camera.location
        lead_peak=max(lead_peak,math.degrees(math.atan2(offset.y,-offset.z)-scene.camera.rotation_euler.x))
assert 12.9<lead_peak<13.1
scene.frame_set(511)
assert abs(world_to_camera_view(scene,scene.camera,circle.location).y-0.5)<0.001
assert sky_emission.inputs['Strength'].default_value<0.4*initial_sky
assert planet_light.data.energy<0.2*initial_planet_light
direction_changes={o.name:math.degrees(initial_directions[o.name].angle(
    (o.location-planet_light.matrix_world.translation).normalized())) for o in planets}
assert all(angle>1 for angle in direction_changes.values())
for body in planets+[earth]:
    offset=body.location-scene.camera.location
    camera_offset=scene.camera.matrix_world.inverted().to_3x3()@offset
    angle=math.atan2(camera_offset.y,-camera_offset.z)
    radius=body['scene_radius']
    assert angle+math.asin(radius/offset.length)<-scene.camera.data.angle_y/2
print('PHENGOS_BLUE_ERASER_VERIFY_PASS '+json.dumps({
    'frames_checked':511,'opening_wordmark_width':opening_width,'grown_width':grown_width,
    'erasure_order':'S then E/F/I/L; centered by five seconds',
    'horizon_gain':[initial_horizon,retreated_horizon],
    'sky_gain':[initial_sky,sky_emission.inputs['Strength'].default_value],
    'real_planet_light_direction_change_degrees':direction_changes,
    'character_lead_degrees':lead_peak,'source_preserved':True,
}))
