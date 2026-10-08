"""Inspect the natural horizon at draft and acceptance checkpoint resolutions."""
import bpy
import sys
import math
from mathutils import Vector

scene = bpy.data.scenes['Phengos_Natural_Horizon_v10']
formats = [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
assert 'PNG' in formats
scene.render.image_settings.file_format = 'PNG'
scene.cycles.use_denoising = True
cases = [(301, 'draft')]
if '--compare-sun' in sys.argv:
    cases = [(301, 'curved'), (301, 'sun')]
if '--sun-only' in sys.argv:
    cases = [(301, 'sun')]
if '--selected' in sys.argv:
    cases = [(91, 'title'), (301, 'selected'), (361, 'rise'), (511, 'idle')]
for frame, label in cases:
    scene.frame_set(frame)
    if '--compare-sun' in sys.argv or '--sun-only' in sys.argv:
        emitter = next(o for o in scene.objects if o.get('emitter_role') == 'continuous_curved_horizon')
        emission = next(n for n in emitter.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
        sun = next(o for o in scene.objects if o.type == 'LIGHT' and o.data.type == 'SUN')
        sun.animation_data_clear()
        earth = next(o for o in scene.objects if o.name.startswith('Earth_Horizon'))
        atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
        receivers = bpy.data.collections.new('Natural_Horizon_Sun_Comparison_Receivers')
        receivers.objects.link(earth)
        receivers.objects.link(atmosphere)
        sun.light_linking.receiver_collection = receivers
        incoming = Vector((0, math.sin(math.radians(3.8)), math.cos(math.radians(3.8))))
        sun.rotation_euler = incoming.to_track_quat('-Z', 'Y').to_euler()
        sun.data.angle = math.radians(0.53)
        sun.data.color = (0.98, 0.99, 1)
        sun.data.energy = 10 if label == 'sun' else 0
        emission.inputs['Strength'].default_value = 0 if label == 'sun' else 500
    scene.render.resolution_percentage = 100 if label == 'selected' else 50
    scene.cycles.samples = 256 if label == 'selected' else 96
    scene.cycles.adaptive_threshold = 0.006 if label == 'selected' else 0.012
    scene.render.filepath = 'E:/LifeOS-Art/phengos/natural-horizon-v10-' + label + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_NATURAL_HORIZON_PREVIEW_COMPLETE')
