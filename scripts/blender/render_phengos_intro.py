"""Render the authored shot and matching rest/idle plates, without altering the .blend.

blender --background E:/LifeOS-Art/phengos/phengos-intro-v4-user-warm.blend \
  --python scripts/blender/render_phengos_intro.py
"""
import bpy

# Background Blender may select an older scene in a multi-scene artist file.
scene = bpy.data.scenes['Phengos_User_Warm_v4']
for node in scene.compositing_node_group.nodes:
    if node.type == 'R_LAYERS':
        assert node.scene == scene, 'Compositor must render the selected revision'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.fps = 60
# The app owns the only circle and letters, including during the opening.
for obj in scene.objects:
    if obj.type == 'FONT' or obj.name.split('.')[0] == 'Phengos':
        obj.hide_render = True
media = [item.identifier for item in scene.render.image_settings.bl_rna.properties['media_type'].enum_items]
assert 'VIDEO' in media
scene.render.image_settings.media_type = 'VIDEO'
scene.render.image_settings.file_format = "FFMPEG"
formats = [item.identifier for item in scene.render.ffmpeg.bl_rna.properties['format'].enum_items]
codecs = [item.identifier for item in scene.render.ffmpeg.bl_rna.properties['codec'].enum_items]
assert 'MPEG4' in formats and 'H264' in codecs
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
quality = [item.identifier for item in scene.render.ffmpeg.bl_rna.properties['constant_rate_factor'].enum_items]
assert 'PERC_LOSSLESS' in quality
scene.render.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'
scene.render.filepath = 'E:/LifeOS-Art/phengos/environment-v4.mp4'
bpy.ops.render.render(animation=True, scene=scene.name)

# Poster plates exclude the character so the app can use a real interactive actor.
for obj in scene.objects:
    if obj.name.startswith('Life_OS_') or obj.name.split('.')[0] == 'Phengos':
        obj.hide_render = True
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'WEBP'
scene.render.image_settings.quality = 95
for frame, name in [(1, 'opening-plate'), (301, 'horizon-plate'), (511, 'idle-plate')]:
    scene.frame_set(frame)
    scene.render.filepath = 'E:/LifeOS-Art/phengos/' + name + '-v4.webp'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_RENDER_COMPLETE: 511 frames / 60fps; environment-only film and matching plates')
