"""Complete system composition; prepend art_primitives.py via the MCP client."""
random.seed(916)
scene = bpy.data.scenes.new("LifeOS_System_Composition")
bpy.context.window.scene = scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.filepath = "E:/LifeOS-Art/system/system-composition"
scene.view_settings.view_transform = "AgX"
assets = bpy.data.collections.new("System_Artwork")
scene.collection.children.link(assets)
staging = bpy.data.collections.new("System_Stage")
scene.collection.children.link(staging)
world = bpy.data.worlds.new("System_Void")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.001, 0.003, 0.008, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.1
scene.world = world

cyan = art_material("System_Cyan", (0.025, 0.48, 0.8), 3)
violet = art_material("System_Violet", (0.4, 0.16, 0.8), 2.6)
gold = art_material("System_Amber", (0.65, 0.33, 0.10), 1.5)
green = art_material("System_Green", (0.07, 0.5, 0.32), 1.7)
core_light = art_material("Self_Stellar_White", (0.24, 0.7, 1), 8)
track_mat = art_material("System_Quiet_Tracks", (0.024, 0.065, 0.10), 0.55)

# Camera-space composition: deliberately asymmetric scale and several depth planes.
core = art_root("SelfCore", (0, 0, 0.15))
art_sphere("Self_Inner_Star", 0.29, core_light, core)
for index in range(9):
    points = []
    for step in range(144):
        angle = step / 144 * math.tau
        radius = 0.55 + index * 0.033
        p = Vector((radius * math.cos(angle), radius * 0.48 * math.sin(angle), 0))
        axis = Vector((math.cos(index * 0.73), math.sin(index * 0.73), 0))
        from mathutils import Quaternion
        p = Quaternion(axis, index * 0.61) @ p
        points.append(tuple(p))
    art_path("Self_Magnetic_Orbit_" + str(index), points, 0.006, cyan, core, True)

calendar = art_root("Calendar", (-5.15, 0.45, 0.18))
calendar_surface = art_surface("Calendar_Mineral", (0.003, 0.005, 0.014), (0.06, 0.035, 0.17))
art_sphere("Chrono_Planet", 0.83, calendar_surface, calendar)
for tick in range(48):
    angle = math.tau * tick / 48
    points = [(1.21 * math.cos(angle + step * 0.009), 1.21 * math.sin(angle + step * 0.009),
               0.11 * math.sin(angle + step * 0.009)) for step in range(5)]
    art_path("Chrono_Segment_" + str(tick), points, 0.017, violet, calendar)
art_orbit("Chrono_Inner_Track", 1.13, violet, calendar, 1, 0.11, 0.004)
art_sphere("Chrono_Now_Marker", 0.072, core_light, calendar, (0.49, -1.11, -0.05), 16)
art_sphere("Chrono_Satellite", 0.11, calendar_surface, calendar, (-0.8, -1.65, -0.05), 24)

learning = art_root("Learning", (-0.3, 4.35, 0.9))
learning_surface = art_surface("Learning_Mineral", (0.008, 0.002, 0.018), (0.075, 0.025, 0.14))
art_sphere("Learning_Dark_Shell", 0.78, learning_surface, learning)
# Luminous, curved branching network follows the camera-facing hemisphere.
for branch in range(11):
    direction = math.tau * branch / 11 + 0.15
    start = Vector((0, -0.7, 0.2))
    endpoint = Vector((math.cos(direction) * 0.62, -0.62, 0.2 + math.sin(direction) * 0.50))
    points = []
    for step in range(24):
        t = step / 23
        p = start.lerp(endpoint, t)
        p.x += math.sin(t * math.pi) * math.cos(branch * 1.3) * 0.13
        p.z += math.sin(t * math.pi) * math.sin(branch * 1.3) * 0.08
        points.append(tuple(p))
    art_path("Neural_Branch_" + str(branch), points, 0.008, violet, learning)
    art_sphere("Neural_Terminal_" + str(branch), 0.021, violet, learning, tuple(endpoint), 12)
    twig_start = Vector(points[13])
    twig_end = twig_start + Vector((math.cos(direction + 0.65) * 0.15, -0.04,
                                  math.sin(direction + 0.65) * 0.15))
    art_path("Neural_Twig_" + str(branch), [tuple(twig_start.lerp(twig_end, i / 11)) for i in range(12)],
             0.004, violet, learning)
art_orbit("Learning_Moon_Orbit", 1.22, violet, learning, 0.78, 0.3, 0.005)
art_sphere("Learning_Moon", 0.09, learning_surface, learning, (-1.05, -0.6, 0.0), 24)

home = art_root("Home", (5.25, 1.85, 0.4))
home_core = art_material("Home_Seam_Light", (0.28, 0.11, 0.02), 0.6, 0.6, 0.4)
plate_mat = art_surface("Home_Bronze_Ceramic", (0.035, 0.019, 0.009), (0.26, 0.15, 0.07))
plate_mat.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.5
art_sphere("Home_Inner_Core", 0.88, home_core, home)
for face in range(6):
    for row in range(2):
        for col in range(2):
            verts = []
            faces = []
            for y in range(7):
                for x in range(7):
                    u = -1 + col + 0.04 + x / 6 * 0.92
                    v = -1 + row + 0.04 + y / 6 * 0.92
                    normal = [(1, u, v), (-1, u, v), (u, 1, v), (u, -1, v), (u, v, 1), (u, v, -1)][face]
                    verts.append(tuple(Vector(normal).normalized() * 0.94))
            for y in range(6):
                for x in range(6):
                    a = y * 7 + x
                    quad = (a, a + 1, a + 8, a + 7)
                    faces.append(tuple(reversed(quad)) if face in (1, 2, 5) else quad)
            mesh = bpy.data.meshes.new("Home_Panel_Surface")
            mesh.from_pydata(verts, [], faces)
            mesh.update()
            obj = bpy.data.objects.new("Home_Plate_" + str(face * 4 + row * 2 + col), mesh)
            assets.objects.link(obj)
            obj.parent = home
            mesh.materials.append(plate_mat)
            for poly in mesh.polygons:
                poly.use_smooth = True
            shell = obj.modifiers.new("Ceramic_Thickness", "SOLIDIFY")
            shell.thickness = 0.025
art_orbit("Home_Resource_Orbit", 1.45, gold, home, 0.78, 0.18, 0.005)
art_sphere("Home_Resource_Node", 0.063, gold, home, (1.4, 0.1, 0.12), 16)

life = art_root("Life", (-2.9, -4.15, -0.35))
life_surface = art_surface("Life_Living_Continents", (0.002, 0.023, 0.05), (0.07, 0.18, 0.08), (0.018, 0.08, 0.036))
art_sphere("Life_Living_Planet", 0.88, life_surface, life, detail=64)
art_orbit("Life_Habitat_Orbit", 1.37, green, life, 0.7, 0.05, 0.005)
art_sphere("Life_Moon", 0.1, life_surface, life, (1.29, 0.27, 0.10), 24)

fitness = art_root("Fitness", (4.8, -3.9, -0.55))
fitness.scale = (0.57, 0.57, 0.57)
source = bpy.data.collections.get("Fitness_Asset")
for original in source.objects:
    if original.name.endswith("_Moon") or original.name in ["SecondaryOrbit", "SatelliteOrbit"]:
        continue
    obj = original.copy()
    assets.objects.link(obj)
    obj.name = "Fitness_" + original.name
    obj.parent = fitness

for index, radius in enumerate([4.0, 5.1, 6.3, 7.3]):
    art_orbit("System_Orbit_" + str(index), radius, track_mat, flatten=0.72,
              tilt=(-0.18 if index % 2 else 0.25), width=0.004)

# One batched mesh supplies distant stars; no hundreds of object draw calls.
star_mat = art_material("Star_Field_Moonlight", (0.21, 0.38, 0.55), 2)
vertices = []
triangles = []
for index in range(950):
    center = Vector((random.uniform(-25, 25), random.uniform(-7, 28), random.uniform(-14, -3)))
    radius = random.uniform(0.008, 0.028)
    start = len(vertices)
    vertices.extend([tuple(center + Vector((radius, 0, 0))), tuple(center + Vector((-radius, 0, 0))),
                     tuple(center + Vector((0, radius, radius)))])
    triangles.append((start, start + 1, start + 2))
mesh = bpy.data.meshes.new("Stars_Batched_Geometry")
mesh.from_pydata(vertices, [], triangles)
mesh.materials.append(star_mat)
stars = bpy.data.objects.new("Background_Stars", mesh)
assets.objects.link(stars)

# Foreground fragments are real geometry with parallax, not a flat decorative overlay.
rock_mat = art_surface("Foreground_Basalt", (0.002, 0.003, 0.004), (0.017, 0.022, 0.031))
for index in range(28):
    angle = 3.45 + index / 27 * 2.40
    center = (math.cos(angle) * 10.5, math.sin(angle) * 7.8 - 0.6, -0.9)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.13, 0.32), location=center)
    obj = art_place(bpy.context.object, "Foreground_Fragment_" + str(index))
    obj.scale = (1.4, 0.7, 0.9)
    obj.rotation_euler = (random.random(), random.random(), random.random())
    obj.data.materials.append(rock_mat)

art_light("System_Key", (-6, -6, 10), 1600, (0.56, 0.72, 1), 7)
art_light("System_Blue_Rim", (4, 5, 6), 2900, (0.20, 0.48, 1), 6)
art_light("Home_Warm_Reflection", (8, 0, 4), 480, (1, 0.62, 0.27), 4)
data = bpy.data.lights.new("Self_Core_Illumination", "POINT")
data.energy = 100
data.color = (0.2, 0.65, 1)
data.shadow_soft_size = 0.7
lamp = bpy.data.objects.new("Self_Core_Illumination", data)
staging.objects.link(lamp)
lamp.location = (0, -0.9, 1)

camera_data = bpy.data.cameras.new("System_Composition_Camera")
camera = bpy.data.objects.new("System_Composition_Camera", camera_data)
staging.objects.link(camera)
camera.location = (0, -17.8, 17)
camera_data.lens = 43
art_aim(camera, (0, 0.35, 0))
scene.camera = camera
compositor = bpy.data.node_groups.new("System_Light_Scattering", "CompositorNodeTree")
scene.compositing_node_group = compositor
compositor.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
layers = compositor.nodes.new("CompositorNodeRLayers")
layers.scene = scene
glow = compositor.nodes.new("CompositorNodeGlare")
glow.inputs["Type"].default_value = "Fog Glow"
glow.inputs["Threshold"].default_value = 1.7
glow.inputs["Strength"].default_value = 0.45
output = compositor.nodes.new("NodeGroupOutput")
compositor.links.new(layers.outputs["Image"], glow.inputs["Image"])
compositor.links.new(glow.outputs["Image"], output.inputs["Image"])
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.region_3d.view_perspective = "CAMERA"
        area.spaces.active.shading.type = "MATERIAL"
        area.spaces.active.shading.use_scene_world = True
        area.spaces.active.shading.use_scene_lights = True
        area.spaces.active.overlay.show_overlays = False
bpy.ops.wm.save_as_mainfile(filepath="E:/LifeOS-Art/system/system-composition.blend")
print("Complete composition saved: five domains, shared camera and lights, foreground depth, sparse stars")
