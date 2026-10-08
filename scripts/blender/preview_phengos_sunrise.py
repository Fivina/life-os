"""Render the explicit sunrise study, never the file's legacy/default scene."""
import bpy
import sys

scene = bpy.data.scenes['Phengos_Sunrise_v5']
scene.render.resolution_percentage = 50
scene.render.image_settings.file_format = 'PNG'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
frames = [(301, 'horizon')]
if '--sequence' in sys.argv:
    frames = [(91, 'title'), (361, 'rise'), (511, 'idle')]
if '--hero' in sys.argv:
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 96
if '--review' in sys.argv:
    frames = [(91, 'title'), (301, 'horizon'), (361, 'rise'), (511, 'idle')]
for frame, name in frames:
    if '--review' in sys.argv:
        scene.render.resolution_percentage = 100 if name == 'horizon' else 50
        scene.cycles.samples = 72 if name == 'horizon' else 48
    scene.frame_set(frame)
    scene.render.filepath = 'E:/LifeOS-Art/phengos/sunrise-v5-' + name + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_SUNRISE_PREVIEW_COMPLETE')
