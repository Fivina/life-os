"""Persisted-file checks for character-led flight, not a source-scene timing claim."""
import bpy
import json
import math
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

scene=bpy.data.scenes['Phengos_Character_Flight_v13']
source=bpy.data.scenes['Phengos_Luminous_Horizon_v12']
assert len(source.objects)==37 and len(scene.objects)==41
assert scene.camera.data is not source.camera.data
assert scene.camera.animation_data.action is not source.camera.animation_data.action
assert scene.compositing_node_group is not source.compositing_node_group
assert all(n.scene==scene for n in scene.compositing_node_group.nodes if n.type=='R_LAYERS')
bpy.context.window.scene=source
source.frame_set(511)
assert abs(source.camera.location.y-3700)<0.001
bpy.context.window.scene=scene
earth=next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
circle=next(o for o in scene.objects if o.name.startswith('Phengos.'))
letters=[o for o in scene.objects if o.type=='FONT']
sun=scene.objects['Phengos_Central_Sunrise_v13']
light=scene.objects['Phengos_Moving_Light_v13']
reflector=scene.objects['Phengos_Atmospheric_Reflection_v13']
assert light.parent==circle and light.data.type=='POINT'
assert list(light.light_linking.receiver_collection.objects)==[reflector]
assert not any(n.type=='EMISSION' for n in reflector.data.materials[0].node_tree.nodes)
assert scene.objects['Phengos_Enclosing_Sky_v13']['art_role']=='surrounding sky'
assert scene.objects['Phengos_Enclosing_Stars_v13']['art_role']=='surrounding stars'
assert scene.camera.data.clip_end>=22000
assert all(o.hide_render for o in scene.objects
           if o.name.startswith(('Smooth_Infinite_Space','Sparse_Stars')))
initial_earth=earth.location.copy()
initial_planets={o.name:o.location.copy() for o in scene.objects
                 if o.name.startswith(('Distant_Banded_Planet','Distant_Cobalt_Planet'))}

def projection(position):
    return world_to_camera_view(scene,scene.camera,position)

def occluded(target):
    origin=scene.camera.location
    delta=target-origin
    distance=delta.length
    direction=delta.normalized()
    offset=origin-earth.location
    b=offset.dot(direction)
    discriminant=b*b-offset.length_squared+earth['scene_radius']**2
    if discriminant<0:
        return False
    hit=-b-math.sqrt(discriminant)
    return 0<hit<distance

def letter_alpha(letter):
    return next(n for n in letter.data.materials[0].node_tree.nodes
                if n.type=='MIX_SHADER').inputs[0].default_value

heights=[]
for frame in (61,181,241):
    scene.frame_set(frame)
    letter=letters[0]
    corners=[projection(letter.matrix_world@Vector(c)) for c in letter.bound_box]
    heights.append(max(p.y for p in corners)-min(p.y for p in corners))
    assert all(letter_alpha(o)>0.99 for o in letters)
    # Font's measured O includes its natural cap-height overshoot.
    word_size=letter.scale.x
    diameter=2*max(v.co.length for v in circle.data.vertices)*circle.scale.x
    assert abs(diameter-circle['wordmark_o_height']*word_size)<0.002
    assert abs(letter.location.z-circle.location.z)<0.001
assert heights[0]<heights[1]<heights[2], heights

lead_peak=0
previous_camera_z=20
first_sunrise_occluded=None
for frame in range(1,512):
    scene.frame_set(frame)
    assert (earth.location-initial_earth).length<0.0001
    assert all((scene.objects[name].location-pos).length<0.0001
               for name,pos in initial_planets.items())
    assert (light.matrix_world.translation-circle.matrix_world.translation).length<0.0001
    assert scene.camera.location.length<10000
    if frame<=301:
        assert scene.camera.location.z>=previous_camera_z-0.0001
        previous_camera_z=scene.camera.location.z
        if first_sunrise_occluded is None and occluded(sun.location):
            first_sunrise_occluded=frame
    else:
        projected=projection(circle.location)
        assert 0.05<projected.x<0.95 and 0.05<projected.y<0.95
        offset=circle.location-scene.camera.location
        lead=math.degrees(math.atan2(offset.y,-offset.z)-scene.camera.rotation_euler.x)
        lead_peak=max(lead_peak,lead)
assert 12.9<lead_peak<13.1

scene.frame_set(1)
assert not occluded(sun.location), 'Opening sunrise must be visible'
scene.frame_set(301)
assert occluded(sun.location), 'Retreat must hide the sunrise behind Earth'
assert all(occluded(sun.matrix_world@v.co) for v in sun.data.vertices), \
    'Retreat must hide the entire finite sunrise, not only its center'
assert all(letter_alpha(o)==0 for o in letters)
altitude=(scene.camera.location-earth.location).length/earth['scene_radius']*6371-6371
assert abs(altitude-900)<0.01
assert abs(circle.location.y)<0.0001
scene.frame_set(511)
assert abs(circle.location.y-55)<0.001 and abs(scene.camera.location.y-12)<0.001
assert abs(projection(circle.location).y-0.5)<0.001
for name in initial_planets:
    obj=scene.objects[name]
    center=projection(obj.location)
    assert center.y<0, 'Planet must leave through camera framing, not opacity'
    assert not obj.hide_render
assert scene.render.use_persistent_data
print('PHENGOS_FLIGHT_VERIFY_PASS '+json.dumps({
    'frames_checked':511,'wordmark_projected_heights':heights,
    'maximum_character_lead_degrees':lead_peak,'handoff_altitude_km':altitude,
    'source_scene_preserved':True,'sunrise_occlusion':True,
    'sunrise_hidden_at_seconds':(first_sunrise_occluded-1)/60,
    'real_moving_light_and_isolated_receiver':True,
}))
