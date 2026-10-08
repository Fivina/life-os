"""Compare curved-emitter strength without changing geometry or exposure."""
import bpy
import sys

scene = bpy.data.scenes['Phengos_Curved_Source_v7']
scene.render.resolution_percentage = 50
scene.render.image_settings.file_format = 'PNG'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
emitter = next(o for o in scene.objects if o.get('emitter_role') == 'continuous_curved_horizon')
emission = next(n for n in emitter.data.materials[0].node_tree.nodes if n.type == 'EMISSION')
cases = [(301, 'soft', 160), (301, 'strong', 400)]
if '--selected' in sys.argv:
    strength = scene['curved_source_strength']
    cases = [(91, 'title', strength), (301, 'selected', strength),
             (361, 'rise', strength), (511, 'idle', strength)]
for frame, label, strength in cases:
    scene.frame_set(frame)
    emission.inputs['Strength'].default_value = strength
    scene.render.resolution_percentage = 100 if label == 'selected' else 50
    scene.cycles.samples = 96 if label == 'selected' else 48
    scene.render.filepath = 'E:/LifeOS-Art/phengos/curved-source-v7-' + label + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_CURVED_SOURCE_PREVIEW_COMPLETE')
