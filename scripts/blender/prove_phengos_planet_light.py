"""Controlled same-seed on/off render demonstrates actual planetary illumination."""
import bpy
import json
from bpy_extras.object_utils import world_to_camera_view

scene = bpy.data.scenes['Phengos_Reference_v16']
bpy.context.window.scene = scene
scene.frame_set(361)
light = next(o for o in scene.objects if o.get('art_role') == 'Phengos cinematic distant-planet point light')
planet = next(o for o in scene.objects if o.name.startswith('Distant_Banded_Planet'))
point = world_to_camera_view(scene, scene.camera, planet.location)
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'CUDA'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'CUDA'
scene.cycles.device = 'GPU'
scene.cycles.samples = 64
scene.cycles.seed = 16
scene.cycles.use_animated_seed = False
scene.cycles.use_denoising = False
scene.render.use_persistent_data = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.use_border = True
scene.render.use_crop_to_border = True
scene.render.border_min_x = max(0, point.x-.085)
scene.render.border_max_x = min(1, point.x+.085)
scene.render.border_min_y = max(0, point.y-.15)
scene.render.border_max_y = min(1, point.y+.15)
scene.render.use_compositing = False
scene.render.image_settings.file_format = 'PNG'
results = {}
for label, hidden in [('on', False), ('off', True)]:
    light.hide_render = hidden
    scene.render.filepath = 'E:/LifeOS-Art/phengos/reference-v16-planet-light-'+label+'.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    results[label] = list(image.pixels)
    dimensions = list(image.size)
    bpy.data.images.remove(image)
delta = [max(abs(a-b) for a,b in zip(results['on'][i:i+3],results['off'][i:i+3]))
         for i in range(0,len(results['on']),4)]
changed = sum(d > .002 for d in delta)
assert changed > 100, 'Moving light has no measurable effect on the planet'
mean_increase = sum(sum(results['on'][i:i+3])-sum(results['off'][i:i+3])
                    for i in range(0,len(results['on']),4))/(3*len(delta))
assert mean_increase > .0001, 'Light must increase planetary radiance, not merely sampling noise'
print('PHENGOS_PLANET_LIGHT_PROOF_PASS', json.dumps({'changed_pixels':changed,
      'mean_max_rgb_delta':sum(delta)/len(delta), 'crop_size':dimensions,
      'mean_rgb_increase':mean_increase,
      'source_energy':light.data.energy, 'frame':361}))
