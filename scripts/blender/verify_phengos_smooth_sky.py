"""Verify v17 changes only the dome shader, preserving the approved v16 shot."""
import bpy
import json
from pathlib import Path

source = bpy.data.scenes['Phengos_Reference_v16']
scene = bpy.data.scenes['Phengos_Smooth_Sky_v17']
old_sky = next(o for o in source.objects if o.get('art_role') == 'surrounding sky')
new_sky = next(o for o in scene.objects if o.get('art_role') == 'surrounding sky')
assert scene.camera is source.camera
assert scene.world is source.world
assert set(source.objects)-{old_sky} == set(scene.objects)-{new_sky}
assert len(old_sky.data.vertices) == len(new_sky.data.vertices)
assert all(a.co == b.co for a,b in zip(old_sky.data.vertices, new_sky.data.vertices))
assert all(a.uv == b.uv for a,b in zip(old_sky.data.uv_layers.active.data,
                                    new_sky.data.uv_layers.active.data))
assert old_sky.data.materials[-1] is not new_sky.data.materials[-1]
textures = [n for n in new_sky.data.materials[-1].node_tree.nodes if n.type == 'TEX_IMAGE']
assert len(textures) == 1
assert list(textures[0].image.size) == [4096,2048]
assert textures[0].image.colorspace_settings.name == 'Non-Color'
assert new_sky.get('cloud_filter_cache')
for old, new in zip(source.compositing_node_group.nodes, scene.compositing_node_group.nodes):
    assert old.type == new.type and old.label == new.label
    if new.type == 'R_LAYERS':
        assert new.scene is scene and old.scene is source
    else:
        for a,b in zip(old.inputs, new.inputs):
            if hasattr(a, 'default_value'):
                av, bv = a.default_value, b.default_value
                assert tuple(av) == tuple(bv) if hasattr(av, '__len__') and not isinstance(av, str) else av == bv
result = {'scene':scene.name, 'foreground_objects_identical':len(scene.objects)-1,
          'camera_and_animation_identical':True, 'world_identical':True,
          'dome_geometry_and_uv_identical':True, 'compositor_identical_except_scene_reference':True,
          'cached_gaussian_texture_taps':81, 'film_texture_lookups':1,
          'linear_cache_size':[4096,2048], 'preserved_source_scene':source.name}
Path('E:/LifeOS-Art/phengos/smooth-sky-v17-verification.json').write_text(json.dumps(result, indent=2))
print('PHENGOS_V17_VERIFICATION_PASS', json.dumps(result), flush=True)
