"""A/B independent planet lighting at identical geometry, camera and exposure."""
import bpy
import sys

scene = bpy.data.scenes['Phengos_Planet_Depth_v8']
scene.render.resolution_percentage = 50
scene.render.image_settings.file_format = 'PNG'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
lights = [o for o in scene.objects if o.type == 'LIGHT' and 'planet_depth_base_energy' in o]
assert len(lights) == 4
cases = [(301, 'subtle', 1.0), (301, 'readable', 1.7)]
if '--selected' in sys.argv:
    strength = scene['planet_depth_strength']
    cases = [(91, 'title', strength), (301, 'selected', strength),
             (361, 'rise', strength), (511, 'idle', strength)]
for frame, name, strength in cases:
    scene.frame_set(frame)
    for obj in lights:
        obj.data.energy = obj['planet_depth_base_energy'] * strength
    scene.render.resolution_percentage = 100 if name == 'selected' else 50
    scene.cycles.samples = 96 if name == 'selected' else 48
    scene.render.filepath = 'E:/LifeOS-Art/phengos/planet-depth-v8-' + name + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_PLANET_DEPTH_PREVIEW_COMPLETE')
