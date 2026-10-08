"""NASA lunar albedo/elevation as art-directed mineral terrain, not cloudy noise."""
import bpy

from art_primitives import art_material


def build_fitness_surface():
    mat = art_material("V11_Fitness_Lunar_Mineral", (0.02, 0.06, 0.1), roughness=0.82, metallic=0.03)
    mat["art_role"] = "mineral_geology"
    mat["art_source"] = "NASA Scientific Visualization Studio CGI Moon Kit; blue art-direction tint"
    tree = mat.node_tree
    shader = tree.nodes["Principled BSDF"]
    shader.inputs["Specular IOR Level"].default_value = 0.15
    albedo = tree.nodes.new("ShaderNodeTexImage")
    albedo.image = bpy.data.images.load("E:/LifeOS-Art/textures/nasa-lroc-color-2k.jpg", check_existing=True)
    tint = tree.nodes.new("ShaderNodeMixRGB")
    tint.blend_type = "MULTIPLY"
    tint.inputs[0].default_value = 1
    tint.inputs[2].default_value = (0.055, 0.17, 0.31, 1)
    tree.links.new(albedo.outputs["Color"], tint.inputs[1])
    tree.links.new(tint.outputs[0], shader.inputs["Base Color"])
    height = tree.nodes.new("ShaderNodeTexImage")
    height.image = bpy.data.images.load("E:/LifeOS-Art/textures/nasa-lola-height-1k.jpg", check_existing=True)
    height.image.colorspace_settings.name = "Non-Color"
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.028
    bump.inputs["Strength"].default_value = 0.4
    tree.links.new(height.outputs["Color"], bump.inputs["Height"])
    roughness = tree.nodes.new("ShaderNodeMapRange")
    roughness.inputs["To Min"].default_value = 0.68
    roughness.inputs["To Max"].default_value = 0.92
    tree.links.new(height.outputs["Color"], roughness.inputs["Value"])
    tree.links.new(roughness.outputs["Result"], shader.inputs["Roughness"])
    fine = tree.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 180
    fine.inputs["Detail"].default_value = 3
    grains = tree.nodes.new("ShaderNodeBump")
    grains.inputs["Distance"].default_value = 0.0015
    grains.inputs["Strength"].default_value = 0.14
    tree.links.new(fine.outputs["Fac"], grains.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], grains.inputs["Normal"])
    tree.links.new(grains.outputs["Normal"], shader.inputs["Normal"])
    return mat
