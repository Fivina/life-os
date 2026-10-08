"""Render composition and clean environment plates from the user's warm revision."""
import bpy

scene = bpy.data.scenes['Phengos_User_Warm_v4']
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.frame_set(91)
scene.render.filepath = 'E:/LifeOS-Art/phengos/warm-v4-title.png'
bpy.ops.render.render(write_still=True, scene=scene.name)
for obj in scene.objects:
    if obj.type == 'FONT' or obj.name.split('.')[0] == 'Phengos':
        obj.hide_render = True
for frame, name in [(1, 'opening'), (301, 'horizon'), (511, 'idle')]:
    scene.frame_set(frame)
    scene.render.filepath = 'E:/LifeOS-Art/phengos/warm-v4-' + name + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_WARM_PREVIEW_COMPLETE')
