"""Controlled exposure comparisons from one explicit scene and camera frame."""
import bpy
import sys

scene = bpy.data.scenes['Phengos_Hidden_Horizon_v6']
scene.render.resolution_percentage = 50
scene.render.image_settings.file_format = 'PNG'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
rig = [o for o in scene.objects if o.type == 'LIGHT' and 'rig_base_energy' in o]
assert len(rig) == 11
cases = [(301, 'restrained', 1.0), (301, 'strong', 2.4)]
if '--selected' in sys.argv:
    cases = [(91, 'title', scene['rig_strength']), (301, 'selected', scene['rig_strength']),
             (361, 'rise', scene['rig_strength']), (511, 'idle', scene['rig_strength'])]
for frame, label, strength in cases:
    if '--selected' in sys.argv:
        scene.render.resolution_percentage = 100 if label == 'selected' else 50
        scene.cycles.samples = 64 if label == 'selected' else 32
    scene.frame_set(frame)
    for obj in rig:
        obj.data.energy = obj['rig_base_energy'] * strength
    scene.render.filepath = 'E:/LifeOS-Art/phengos/hidden-horizon-v6-' + label + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_HIDDEN_HORIZON_PREVIEW_COMPLETE')
