"""Render the requested v12 framing and wordmark checkpoints without saving mutations."""
import bpy
import sys

scene = bpy.data.scenes['Phengos_Luminous_Horizon_v12']
bpy.context.window.scene = scene
assert 'PNG' in [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
scene.render.image_settings.file_format = 'PNG'
if '--motion' in sys.argv:
    assert 'VIDEO' in [i.identifier for i in scene.render.image_settings.bl_rna.properties['media_type'].enum_items]
    scene.render.image_settings.media_type = 'VIDEO'
    assert 'FFMPEG' in [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
    scene.render.image_settings.file_format = 'FFMPEG'
    assert 'MPEG4' in [i.identifier for i in scene.render.ffmpeg.bl_rna.properties['format'].enum_items]
    assert 'H264' in [i.identifier for i in scene.render.ffmpeg.bl_rna.properties['codec'].enum_items]
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.resolution_percentage = 25
    scene.cycles.samples = 16
    scene.cycles.adaptive_threshold = 0.03
    scene.cycles.use_denoising = True
    scene.frame_step = 5
    # Every fifth baked 60fps frame plays at 12fps: retain the 8.5-second timing.
    scene.render.fps = 12
    scene.render.filepath = 'E:/LifeOS-Art/phengos/luminous-horizon-v12-motion-draft.mp4'
    bpy.ops.render.render(animation=True, scene=scene.name)
    print('PHENGOS_LUMINOUS_MOTION_DRAFT_COMPLETE: 480x270, 12fps timing preview, not delivery quality')
    raise SystemExit(0)
cases = [(91, 'title'), (301, 'horizon')]
if '--selected' in sys.argv:
    cases += [(361, 'rise'), (511, 'idle')]
for frame, label in cases:
    scene.frame_set(frame)
    full = '--selected' in sys.argv and label in ('title', 'horizon')
    scene.cycles.samples = 256 if full else 96
    scene.cycles.adaptive_threshold = 0.005 if full else 0.012
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = 100 if full else 50
    scene.render.filepath = 'E:/LifeOS-Art/phengos/luminous-horizon-v12-' + label + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_LUMINOUS_HORIZON_PREVIEW_COMPLETE')
