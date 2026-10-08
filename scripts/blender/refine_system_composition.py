"""Lighting/composition revision; prepend art_primitives.py via the MCP client."""
scene = bpy.data.scenes["LifeOS_System_Composition"]
bpy.context.window.scene = scene
assets = bpy.data.collections["System_Artwork"]
staging = bpy.data.collections["System_Stage"]
random.seed(916)
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.filepath = "E:/LifeOS-Art/system/system-cinematic-study"
scene.camera.location = (0, -19.5, 12.5)
scene.camera.data.lens = 43
art_aim(scene.camera, (0, 0.1, 0))
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.035
scene.objects["System_Key"].data.energy = 480
scene.objects["System_Key"].location = (-8, -2, 7)
art_aim(scene.objects["System_Key"], (0, 0, 0))
scene.objects["System_Blue_Rim"].data.energy = 3300
scene.objects["System_Blue_Rim"].location = (2, 5, 4)
scene.objects["Home_Warm_Reflection"].data.energy = 340
scene.objects["Self_Core_Illumination"].data.energy = 180
bpy.data.materials["Self_Stellar_White"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 35

# Repair older panel winding once; new scene creation already uses outward faces.
for obj in assets.objects:
    if not obj.name.startswith("Home_Plate_"):
        continue
    center = sum((v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
    if obj.data.polygons[0].normal.dot(center) < 0:
        obj.data.flip_normals()
        obj.data.update()

for name, color in [
    ("Calendar_Mineral", (0.23, 0.13, 0.8)),
    ("Learning_Mineral", (0.4, 0.16, 0.9)),
    ("Life_Living_Continents", (0.045, 0.38, 0.65)),
]:
    mat = bpy.data.materials[name]
    tree = mat.node_tree
    shader = tree.nodes["Principled BSDF"]
    fresnel = tree.nodes.get("Art_Atmosphere_Fresnel") or tree.nodes.new("ShaderNodeFresnel")
    fresnel.name = "Art_Atmosphere_Fresnel"
    fresnel.inputs["IOR"].default_value = 1.12
    power = tree.nodes.get("Art_Atmosphere_Falloff") or tree.nodes.new("ShaderNodeMath")
    power.name = "Art_Atmosphere_Falloff"
    power.operation = "POWER"
    power.inputs[1].default_value = 1.8
    strength = tree.nodes.get("Art_Atmosphere_Strength") or tree.nodes.new("ShaderNodeMath")
    strength.name = "Art_Atmosphere_Strength"
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = 4
    tree.links.new(fresnel.outputs["Fac"], power.inputs[0])
    tree.links.new(power.outputs[0], strength.inputs[0])
    tree.links.new(strength.outputs[0], shader.inputs["Emission Strength"])
    shader.inputs["Emission Color"].default_value = (*color, 1)

# Project every neural branch onto the visible shell instead of burying it.
front = Vector((0, -19.5 - 4.35, 12.5 - 0.9)).normalized()
right = Vector((1, 0, 0))
up = front.cross(right).normalized()
for obj in list(assets.objects):
    if obj.name.startswith(("Neural_Branch_", "Neural_Twig_", "Neural_Terminal_")):
        bpy.data.objects.remove(obj, do_unlink=True)
learning = scene.objects["Learning"]
violet = bpy.data.materials["System_Violet"]
def shell_point(x, y):
    return right * x + up * y + front * math.sqrt(max(0.025, 0.8 ** 2 - x * x - y * y))
for branch in range(9):
    side = -1 if branch % 2 else 1
    end_y = -0.06 + branch / 8 * 0.63
    end_x = side * (0.45 - branch / 8 * 0.17)
    points = []
    for step in range(25):
        t = step / 24
        points.append(tuple(shell_point(end_x * t * t, -0.53 + (end_y + 0.53) * t)))
    art_path("Neural_Branch_" + str(branch), points, 0.007, violet, learning)
    art_sphere("Neural_Terminal_" + str(branch), 0.018, violet, learning, points[-1], 12)
    for twig in range(2):
        t = 0.58 + twig * 0.2
        x = end_x * t * t
        y = -0.53 + (end_y + 0.53) * t
        art_path("Neural_Twig_" + str(branch) + "_" + str(twig),
                 [tuple(shell_point(x + side * s * 0.1, y + s * 0.14))
                  for s in [i / 11 for i in range(12)]], 0.003, violet, learning)

# Scale hierarchy and a subtle roll keep the barbell from looking detached.
scene.objects["Fitness"].rotation_euler.y = -0.16
scene.objects["Learning"].scale = (1.17, 1.17, 1.17)
scene.objects["Calendar"].scale = (1.08, 1.08, 1.08)
scene.objects["Home"].scale = (1.06, 1.06, 1.06)
scene.objects["System_Orbit_1"].hide_render = True
scene.objects["System_Orbit_3"].hide_render = True
for obj in assets.objects:
    if obj.name.startswith("Self_Magnetic_Orbit_"):
        obj.data.bevel_depth = 0.0035
    if obj.name.startswith("Foreground_Fragment_"):
        index = int(obj.name.rsplit("_", 1)[1])
        angle = 3.5 + index / 27 * 1.03
        obj.location = (math.cos(angle) * 10, math.sin(angle) * 8 - 0.8, 0.2)
        obj.scale = (2.3, 1.3, 1.8)

# A distant dust sheet is an art backplate, not volumetric runtime simulation.
old = scene.objects.get("Distant_Galactic_Dust")
if old:
    bpy.data.objects.remove(old, do_unlink=True)
camera = scene.camera
rotation = camera.rotation_euler.to_quaternion()
forward = rotation @ Vector((0, 0, -1))
bpy.ops.mesh.primitive_plane_add(size=2, location=camera.location + forward * 65)
dust = art_place(bpy.context.object, "Distant_Galactic_Dust")
dust.rotation_euler = camera.rotation_euler
dust.scale = (36, 22, 1)
mat = bpy.data.materials.new("Distant_Dust_Art_Backplate")
mat.use_nodes = True
tree = mat.node_tree
tree.nodes.clear()
output = tree.nodes.new("ShaderNodeOutputMaterial")
emission = tree.nodes.new("ShaderNodeEmission")
coord = tree.nodes.new("ShaderNodeTexCoord")
noise = tree.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 6
noise.inputs["Detail"].default_value = 6
noise.inputs["Roughness"].default_value = 0.76
noise.inputs["Distortion"].default_value = 1.9
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.42
ramp.color_ramp.elements[0].color = (0.0001, 0.0002, 0.0005, 1)
ramp.color_ramp.elements[1].position = 0.76
ramp.color_ramp.elements[1].color = (0.003, 0.008, 0.018, 1)
separate = tree.nodes.new("ShaderNodeSeparateXYZ")
tree.links.new(coord.outputs["UV"], separate.inputs["Vector"])
slant = tree.nodes.new("ShaderNodeMath")
slant.operation = "MULTIPLY"
slant.inputs[1].default_value = 0.4
tree.links.new(separate.outputs["X"], slant.inputs[0])
offset = tree.nodes.new("ShaderNodeMath")
offset.operation = "SUBTRACT"
tree.links.new(separate.outputs["Y"], offset.inputs[0])
tree.links.new(slant.outputs[0], offset.inputs[1])
center = tree.nodes.new("ShaderNodeMath")
center.operation = "SUBTRACT"
center.inputs[1].default_value = 0.34
tree.links.new(offset.outputs[0], center.inputs[0])
distance = tree.nodes.new("ShaderNodeMath")
distance.operation = "ABSOLUTE"
tree.links.new(center.outputs[0], distance.inputs[0])
band = tree.nodes.new("ShaderNodeMapRange")
band.clamp = True
band.inputs["From Min"].default_value = 0.015
band.inputs["From Max"].default_value = 0.18
band.inputs["To Min"].default_value = 0.8
band.inputs["To Max"].default_value = 0
tree.links.new(distance.outputs[0], band.inputs["Value"])
tree.links.new(band.outputs["Result"], emission.inputs["Strength"])
tree.links.new(coord.outputs["UV"], noise.inputs["Vector"])
tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], emission.inputs["Color"])
tree.links.new(emission.outputs[0], output.inputs["Surface"])
dust.data.materials.append(mat)

for node in scene.compositing_node_group.nodes:
    if node.bl_idname == "CompositorNodeGlare":
        node.inputs["Threshold"].default_value = 1.2
        node.inputs["Strength"].default_value = 0.75
bpy.ops.wm.save_as_mainfile(filepath="E:/LifeOS-Art/system/system-composition.blend")
print("Cinematic lighting study saved; browser export and final motion remain separate quality gates")
