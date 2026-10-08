"""Render isolated v17 proofs, film, and circle-free idle to the art directory.

Run with -- --proof, -- --film, -- --idle, or -- --rest. Never changes a saved scene.
"""
import bpy
import sys
import time

OUT = 'E:/LifeOS-Art/phengos'
scene = bpy.data.scenes['Phengos_Smooth_Sky_v17']
bpy.context.window.scene = scene
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'OPTIX'
scene.cycles.device = 'GPU'
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPTIX'
scene.cycles.denoising_use_gpu = True
scene.cycles.samples = 24
scene.cycles.adaptive_threshold = 0.025
scene.render.use_persistent_data = True
scene.render.resolution_percentage = 100
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
for obj in scene.objects:
    if obj.type == 'MESH' and (obj.get('optical_role') or not (obj.visible_diffuse or obj.visible_glossy)):
        for mat in obj.data.materials:
            if mat:
                mat.cycles.emission_sampling = 'NONE'
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'PNG'
if '--proof' in sys.argv:
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.cycles.samples = 64
    scene.cycles.adaptive_threshold = 0.01
    for frame, label in ((1, 'opening'), (511, 'idle')):
        started = time.perf_counter()
        scene.frame_set(frame)
        scene.render.filepath = OUT+'/smooth-sky-v17-'+label+'.png'
        bpy.ops.render.render(write_still=True, scene=scene.name)
        print('PHENGOS_V17_PROOF', label, time.perf_counter()-started, flush=True)
elif '--idle' in sys.argv or '--rest' in sys.argv:
    next(o for o in scene.objects if o.name.startswith('Phengos.')).hide_render = True
    rest = '--rest' in sys.argv
    scene.frame_set(1 if rest else 511)
    scene.render.filepath = OUT+('/rest-environment-v17.png' if rest else '/idle-environment-v17.png')
    bpy.ops.render.render(write_still=True, scene=scene.name)
    print('PHENGOS_V17_REST_COMPLETE' if rest else 'PHENGOS_V17_IDLE_COMPLETE', flush=True)
elif '--film' in sys.argv:
    scene.frame_step = 1
    scene.render.fps = 60
    scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.filepath = OUT+'/environment-v17-60.mp4'
    bpy.ops.render.render(animation=True, scene=scene.name)
    print('PHENGOS_V17_FILM_COMPLETE', flush=True)
else:
    raise SystemExit('Pass -- --proof, -- --film, -- --idle or -- --rest')
