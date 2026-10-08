import bpy

scene = bpy.context.scene
for obj in scene.objects:
    if obj.name.startswith(("Left", "Right", "CentralAxis", "AxisLightTrace")):
        obj.location.y = -1.507 if obj.name == "AxisLightTrace" else -1.46
scene.objects["Key_Softbox"].data.energy = 350
scene.objects["Cyan_Rim"].data.energy = 1900
scene.camera.location = (3, -11.8, 3.7)
scene.camera.rotation_euler = (-scene.camera.location).to_track_quat("-Z", "Y").to_euler()

for material in bpy.data.materials:
    if not material.use_nodes or "Surface" not in material.name and material.name != "Planet_Ice_Continents":
        continue
    tree = material.node_tree
    shader = tree.nodes["Principled BSDF"]
    shader.inputs["Roughness"].default_value = 0.7
    bump = tree.nodes.get("Bump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.025
    ramp = tree.nodes.get("Color Ramp")
    if material.name == "Planet_Ice_Continents":
        ramp.color_ramp.elements[0].color = (0.001, 0.004, 0.009, 1)
        ramp.color_ramp.elements[1].color = (0.017, 0.049, 0.087, 1)
        ramp.color_ramp.elements[2].color = (0.045, 0.13, 0.23, 1)
    fresnel = tree.nodes.get("LifeOS_Rim_Fresnel") or tree.nodes.new("ShaderNodeFresnel")
    fresnel.name = "LifeOS_Rim_Fresnel"
    fresnel.inputs["IOR"].default_value = 1.15
    edge = tree.nodes.get("LifeOS_Rim_Falloff") or tree.nodes.new("ShaderNodeMath")
    edge.name = "LifeOS_Rim_Falloff"
    edge.operation = "POWER"
    edge.inputs[1].default_value = 2
    strength = tree.nodes.get("LifeOS_Rim_Strength") or tree.nodes.new("ShaderNodeMath")
    strength.name = "LifeOS_Rim_Strength"
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = 3
    tree.links.new(fresnel.outputs["Fac"], edge.inputs[0])
    tree.links.new(edge.outputs[0], strength.inputs[0])
    tree.links.new(strength.outputs[0], shader.inputs["Emission Strength"])
    shader.inputs["Emission Color"].default_value = ramp.color_ramp.elements[-1].color

bpy.ops.wm.save_as_mainfile(filepath="E:/LifeOS-Art/fitness/fitness-art-study.blend")
print("Adjusted shaft clearance, darker terrain, directional light and atmospheric edge")
