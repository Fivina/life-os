"""v17: densely filter the existing cloud plate without changing shot staging.

Run against phengos-intro-v16-reference.blend. This changes only the
camera-visible dome's material; v16 and all body/motion/light data stay intact.
"""
import bpy
import json
import math

OUT = 'E:/LifeOS-Art/phengos'
source = bpy.data.scenes['Phengos_Reference_v16']
assert 'Phengos_Smooth_Sky_v17' not in bpy.data.scenes
scene = source.copy()
scene.name = 'Phengos_Smooth_Sky_v17'
scene.use_fake_user = True
bpy.context.window.scene = scene
scene.compositing_node_group = source.compositing_node_group.copy()
for node in scene.compositing_node_group.nodes:
    if node.type == 'R_LAYERS':
        node.scene = scene

original = next(o for o in scene.objects if o.get('art_role') == 'surrounding sky')
sky = original.copy()
sky.data = original.data.copy()
scene.collection.objects.link(sky)
scene.collection.objects.unlink(original)
sky.name = 'Phengos_v17_Continuous_Cloud_Dome'
sky.data.materials.clear()
material = bpy.data.materials.new('Phengos_v17_Dense_Gaussian_Clouds')
material.use_nodes = True
material.cycles.emission_sampling = 'NONE'
sky.data.materials.append(material)
tree = material.node_tree
tree.nodes.clear()
image = next(n.image for n in original.data.materials[-1].node_tree.nodes
             if n.type == 'TEX_IMAGE')
width, height = image.size
coords = tree.nodes.new('ShaderNodeTexCoord')
emission = tree.nodes.new('ShaderNodeEmission')
emission.label = 'Same independent celestial radiance as v16'
emission.inputs['Strength'].default_value = 0.5
output = tree.nodes.new('ShaderNodeOutputMaterial')
tree.links.new(emission.outputs[0], output.inputs['Surface'])

# v16 used 9 separated taps with gaps between them. A normalized dense Gaussian
# suppresses the source's angular high-frequency pattern before projection.
# These pixel units are measured against the source, not output dimensions.
sigma, spacing, radius = 8.0, 4.0, 4
weights = [(dx, dy, math.exp(-((dx*spacing)**2+(dy*spacing)**2)/(2*sigma*sigma)))
           for dy in range(-radius, radius+1) for dx in range(-radius, radius+1)]
total = sum(w for _, _, w in weights)
average = None
for dx, dy, weight in weights:
    offset = tree.nodes.new('ShaderNodeVectorMath')
    offset.operation = 'ADD'
    offset.inputs[1].default_value = (dx*spacing/width, dy*spacing/height, 0)
    tree.links.new(coords.outputs['UV'], offset.inputs[0])
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    texture.interpolation = 'Cubic'
    texture.extension = 'EXTEND'
    tree.links.new(offset.outputs[0], texture.inputs['Vector'])
    scale = tree.nodes.new('ShaderNodeVectorMath')
    scale.operation = 'SCALE'
    scale.inputs['Scale'].default_value = weight/total
    tree.links.new(texture.outputs['Color'], scale.inputs[0])
    if average is None:
        average = scale.outputs[0]
    else:
        add = tree.nodes.new('ShaderNodeVectorMath')
        add.operation = 'ADD'
        tree.links.new(average, add.inputs[0])
        tree.links.new(scale.outputs[0], add.inputs[1])
        average = add.outputs[0]
tree.links.new(average, emission.inputs['Color'])
sky['cloud_filter'] = '81 cubic Gaussian taps; source sigma 8px; 4px spacing; normalized weights'
scene['source_scene'] = source.name
scene['sky_refinement_contract'] = 'Only cloud material; dome UV/mesh, stars, camera, bodies, typography, motion and lighting preserved'
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=OUT+'/phengos-intro-v17-smooth-sky.blend')
print('PHENGOS_V17_SKY_AUTHORED', json.dumps({'scene':scene.name,
    'image_size':list(image.size), 'taps':len(weights), 'sigma_source_px':sigma}), flush=True)
