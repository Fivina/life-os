import bpy
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.region_3d.view_perspective = "CAMERA"
        area.spaces.active.shading.type = "MATERIAL"
        area.spaces.active.shading.use_scene_world = True
        area.spaces.active.shading.use_scene_lights = True
        area.spaces.active.overlay.show_overlays = False
bpy.ops.wm.save_as_mainfile(filepath="E:/LifeOS-Art/fitness/fitness-art-study.blend")
print("Editor uses the scene lighting; study saved")
