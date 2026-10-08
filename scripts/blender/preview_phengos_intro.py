"""Quick environment-only composition review before an expensive animation render."""
import bpy

scene = bpy.context.scene
scene.render.resolution_percentage = 67
scene.render.image_settings.file_format = "PNG"
for obj in scene.objects:
    if obj.type == 'FONT' or obj.name.split('.')[0] == 'Phengos':
        obj.hide_render = True
for frame, name in [(1, 'opening'), (301, 'horizon'), (511, 'idle')]:
    scene.frame_set(frame)
    scene.render.filepath = 'E:/LifeOS-Art/phengos/preview-v3-' + name + '.png'
    bpy.ops.render.render(write_still=True)
print('PHENGOS_PREVIEW_COMPLETE')
