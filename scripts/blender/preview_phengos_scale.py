"""Render framing checkpoints for the common-scale study, without exporting a movie."""
import bpy
import sys

scene = bpy.data.scenes['Phengos_Scale_Study_v9']
formats = [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
assert 'PNG' in formats
scene.render.image_settings.file_format = 'PNG'
scene.cycles.use_denoising = True
cases = [(301, 'draft')]
if '--selected' in sys.argv:
    cases = [(91, 'title'), (301, 'selected'), (361, 'rise'), (511, 'idle')]
for frame, label in cases:
    scene.frame_set(frame)
    scene.render.resolution_percentage = 100 if label == 'selected' else 50
    scene.cycles.samples = 96 if label == 'selected' else 48
    scene.render.filepath = 'E:/LifeOS-Art/phengos/shared-scale-v9-' + label + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_SHARED_SCALE_PREVIEW_COMPLETE')
