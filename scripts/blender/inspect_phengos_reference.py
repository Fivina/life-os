"""Read saved scene contracts and shader inputs before reference-match authoring."""
import bpy
import json

scene = bpy.data.scenes['Phengos_Cinematic_Hierarchy_v15']
bpy.context.window.scene = scene
scene.frame_set(1)
print('SCENE', bpy.app.version_string, scene.render.engine, scene.cycles.device,
      scene.view_settings.view_transform, scene.view_settings.look, scene.view_settings.exposure)
print('CAMERA', list(scene.camera.location), scene.camera.data.lens, scene.camera.data.angle,
      list(scene.camera.rotation_euler))
for obj in scene.objects:
    print('OBJ', obj.name, obj.type, list(obj.location), list(obj.scale),
          obj.hide_render, dict(obj.items()))
    if (obj.name.startswith(('Earth_Horizon', 'Phengos.')) or
            obj.get('optical_role') == 'earth_limb'):
        for mat in obj.data.materials:
            print('MAT', mat.name)
            for node in mat.node_tree.nodes:
                values = {}
                for socket in node.inputs:
                    if hasattr(socket, 'default_value'):
                        value = socket.default_value
                        values[socket.name] = list(value) if hasattr(value, '__len__') and not isinstance(value, str) else value
                print(node.type, node.name, node.label, json.dumps(values, default=str))
            print('LINKS', [(link.from_node.name, link.from_socket.name,
                            link.to_node.name, link.to_socket.name) for link in mat.node_tree.links])
print('PHENGOS_INSPECTION_COMPLETE')
