"""Render reference checkpoints at useful image resolution and GPU-bounded cost."""
import bpy
import sys
import time

scene = bpy.data.scenes['Phengos_Reference_v16']
bpy.context.window.scene = scene
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'CUDA'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'CUDA'
scene.cycles.device = 'GPU'
scene.render.use_persistent_data = True
scene.cycles.use_denoising = True
scene.cycles.samples = 48
scene.cycles.adaptive_threshold = 0.018
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_percentage = 75
if '--motion' in sys.argv or '--benchmark' in sys.argv:
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 24
    scene.cycles.adaptive_threshold = 0.025
    scene.cycles.denoiser = 'OPTIX'
    scene.cycles.denoising_use_gpu = True
    # View-dependent rim overlays are not illumination sources. Excluding them
    # from direct-light sampling avoids rebuilding a million-emitter light tree.
    for obj in scene.objects:
        if obj.type == 'MESH' and (obj.get('optical_role') or
                                 not (obj.visible_diffuse or obj.visible_glossy)):
            for material in obj.data.materials:
                if material:
                    material.cycles.emission_sampling = 'NONE'
    scene.frame_step = 2
    scene.render.fps = 30
    scene.render.filepath = 'E:/LifeOS-Art/phengos/reference-v16-motion.mp4'
    if '--benchmark' in sys.argv:
        scene.render.image_settings.media_type = 'IMAGE'
        scene.render.image_settings.file_format = 'PNG'
        for frame in (1, 3):
            started = time.perf_counter()
            scene.frame_set(frame)
            scene.render.filepath = 'E:/LifeOS-Art/phengos/reference-v16-benchmark-' + str(frame) + '.png'
            bpy.ops.render.render(write_still=True, scene=scene.name)
            print('PHENGOS_REVIEW_FRAME_SECONDS', frame, time.perf_counter() - started, flush=True)
        raise SystemExit(0)
    bpy.ops.render.render(animation=True, scene=scene.name)
    print('PHENGOS_REFERENCE_MOTION_COMPLETE 1280x720 30fps')
    raise SystemExit(0)
cases = [(1, 'opening')]
if '--checkpoints' in sys.argv:
    cases = [(1, 'opening'), (217, 'fading'), (361, 'climb'), (421, 'flight'), (511, 'idle')]
if '--hero' in sys.argv:
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 128
    scene.cycles.adaptive_threshold = 0.006
for frame, label in cases:
    scene.frame_set(frame)
    scene.render.filepath = 'E:/LifeOS-Art/phengos/reference-v16-' + label + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_REFERENCE_STILLS_COMPLETE', cases)
