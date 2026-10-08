"""Compare volume and analytical limb at identical 600 km framing and dawn lighting."""
import bpy
import sys

scene = bpy.data.scenes['Phengos_Silver_Horizon_v11']
formats = [i.identifier for i in scene.render.image_settings.bl_rna.properties['file_format'].enum_items]
assert 'PNG' in formats
scene.render.image_settings.file_format = 'PNG'
atmosphere = next(o for o in scene.objects if o.name.startswith('Earth_Thin_Atmosphere'))
earth_limbs = [o for o in scene.objects if o.get('optical_role') == 'earth_limb']
assert len(earth_limbs) == 2
cases = [(301, 'volume', False), (301, 'silver', True)]
if '--selected' in sys.argv:
    cases = [(91, 'title', True), (301, 'selected', True),
             (361, 'rise', True), (511, 'idle', True)]
for frame, label, silver in cases:
    scene.frame_set(frame)
    atmosphere.hide_render = silver
    for limb in earth_limbs:
        limb.hide_render = not silver
    scene.cycles.use_denoising = True
    scene.cycles.samples = 256 if label == 'selected' else 96
    scene.cycles.adaptive_threshold = 0.005 if label == 'selected' else 0.012
    scene.render.resolution_percentage = 100 if label == 'selected' else 50
    scene.render.filepath = 'E:/LifeOS-Art/phengos/silver-horizon-v11-' + label + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
print('PHENGOS_SILVER_HORIZON_PREVIEW_COMPLETE')
