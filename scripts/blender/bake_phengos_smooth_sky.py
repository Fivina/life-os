"""Cache v17's exact cloud filter once in scene-linear EXR for cheap film rays.

This is a Blender shader render, not an upscale claiming new celestial detail.
The untouched 1774x887 original remains packed in the preserved v16 scene.
"""
import bpy
from mathutils import Vector

OUT = 'E:/LifeOS-Art/phengos'
scene = bpy.data.scenes['Phengos_Smooth_Sky_v17']
sky = next(o for o in scene.objects if o.get('art_role') == 'surrounding sky')
filtered = sky.data.materials[0]
bake = bpy.data.scenes.new('Temporary_v17_Cloud_Filter_Bake')
bpy.context.window.scene = bake
bake.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'OPTIX'
bake.cycles.device = 'GPU'
bake.cycles.samples = 1
bake.cycles.use_adaptive_sampling = False
bake.cycles.use_denoising = False
bake.render.resolution_x = 4096
bake.render.resolution_y = 2048
bake.render.resolution_percentage = 100
bake.render.use_compositing = False
bake.render.image_settings.file_format = 'OPEN_EXR'
bake.render.image_settings.color_mode = 'RGB'
bake.render.image_settings.color_depth = '32'
bake.render.image_settings.exr_codec = 'ZIP'
bake.render.filepath = OUT+'/cloud-filter-v17-linear-4096.exr'
mesh = bpy.data.meshes.new('Temporary_v17_Filter_Plane')
mesh.from_pydata([(-2,-1,0),(2,-1,0),(2,1,0),(-2,1,0)], [], [(0,1,2,3)])
uv = mesh.uv_layers.new()
for i,co in enumerate(((0,0),(1,0),(1,1),(0,1))):
    uv.data[i].uv = co
obj = bpy.data.objects.new(mesh.name, mesh)
bake.collection.objects.link(obj)
mat = filtered.copy()
next(n for n in mat.node_tree.nodes if n.type == 'EMISSION').inputs['Strength'].default_value = 1
mesh.materials.append(mat)
camera_data = bpy.data.cameras.new('Temporary_v17_Filter_Camera')
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 4
camera = bpy.data.objects.new(camera_data.name, camera_data)
bake.collection.objects.link(camera)
camera.location = (0,0,3)
bake.camera = camera
bpy.ops.render.render(write_still=True, scene=bake.name)

image = bpy.data.images.load(bake.render.filepath, check_existing=False)
image.colorspace_settings.name = 'Non-Color'
material = bpy.data.materials.new('Phengos_v17_Cached_Gaussian_Clouds')
material.use_nodes = True
material.cycles.emission_sampling = 'NONE'
tree = material.node_tree
tree.nodes.clear()
coords = tree.nodes.new('ShaderNodeTexCoord')
texture = tree.nodes.new('ShaderNodeTexImage')
texture.image = image
texture.interpolation = 'Cubic'
texture.extension = 'EXTEND'
tree.links.new(coords.outputs['UV'], texture.inputs['Vector'])
emission = tree.nodes.new('ShaderNodeEmission')
emission.inputs['Strength'].default_value = 0.5
tree.links.new(texture.outputs['Color'], emission.inputs['Color'])
output = tree.nodes.new('ShaderNodeOutputMaterial')
tree.links.new(emission.outputs[0], output.inputs['Surface'])
sky.data.materials.clear()
sky.data.materials.append(material)
sky['cloud_filter_cache'] = '4096x2048 float32 scene-linear EXR; exact v17 81-tap shader bake; single cubic film lookup'
bpy.context.window.scene = scene
bpy.data.scenes.remove(bake)
scene.frame_set(1)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/phengos-intro-v17-smooth-sky.blend')
print('PHENGOS_V17_CLOUD_FILTER_CACHED', list(image.size), flush=True)
