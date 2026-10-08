"""Bake portable materials and export only the authored Life OS V2 artwork.

E:/Blender/blender.exe --background E:/LifeOS-Art/system/system-art-v2.blend \
  --python scripts/blender/export_system_art.py -- --output artwork.glb \
  --textures E:/LifeOS-Art/system/baked

All edits are in a disposable background process. This script never saves a blend.
Linked procedural channels use Cycles; original UV image maps stay image maps.
View-dependent emission is stripped and described in material extras for runtime.
"""

import argparse
import hashlib
import json
import math
import re
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_art_glb import inspect_glb


ROOTS = ("SelfCore", "Calendar", "Learning", "Home", "Fitness", "Life", "Scenery")
SOURCE_UV = "ArtSourceUV"
BAKE_UV = "ArtBakeUV"
VIEW_NODES = {"FRESNEL", "LAYER_WEIGHT", "LIGHT_PATH", "CAMERA", "SHADERINFO"}
CHANNELS = ("Base Color", "Metallic", "Roughness", "Alpha", "Normal", "Emission Color")


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def log(message):
    print("[LifeOS export] " + message, flush=True)


def plain(value):
    if isinstance(value, (str, bool, int, float)):
        return value
    try:
        return list(value)
    except TypeError:
        return str(value)


def upstream(socket, seen=None):
    seen = set() if seen is None else seen
    for link in socket.links:
        node = link.from_node
        if node.as_pointer() in seen:
            continue
        seen.add(node.as_pointer())
        yield node, link.from_socket
        for inp in node.inputs:
            yield from upstream(inp, seen)
        if node.type == "GROUP" and node.node_tree:
            # Groups can hide view dependence; conservatively inspect their contents.
            for inner in node.node_tree.nodes:
                yield inner, None


def view_dependent(socket):
    return any(node.type in VIEW_NODES or
               (node.type == "TEX_COORD" and out and out.name in ("Camera", "Reflection")) or
               (node.type == "NEW_GEOMETRY" and out and out.name in ("Incoming", "Backfacing"))
               for node, out in upstream(socket))


def graph_extra(socket):
    nodes = []
    for node, _ in upstream(socket):
        nodes.append({"name": node.name, "type": node.bl_idname,
                      "operation": getattr(node, "operation", ""),
                      "inputs": {inp.name: plain(inp.default_value) for inp in node.inputs
                                 if hasattr(inp, "default_value") and not inp.is_linked},
                      "links": [{"input": link.to_socket.name, "node": link.from_node.name,
                                 "output": link.from_socket.name} for inp in node.inputs for link in inp.links]})
    return {"socket": socket.name, "default": plain(getattr(socket, "default_value", 0)), "nodes": nodes}


def origin(socket):
    if not socket.is_linked:
        return None
    result = socket.links[0].from_socket
    while result.node.type == "REROUTE":
        check(result.node.inputs[0].is_linked, "Disconnected shader reroute")
        result = result.node.inputs[0].links[0].from_socket
    return result


def constant(socket):
    out = origin(socket)
    if out is None:
        return plain(socket.default_value)
    if out.node.type in ("RGB", "VALUE"):
        return plain(out.default_value)
    return None


def scalar_range(socket, seen=None):
    """Conservative bounds for the scalar nodes used by procedural emission."""
    value = constant(socket)
    if isinstance(value, (int, float)):
        return value, value
    out = origin(socket)
    if out is None:
        return None
    seen = set() if seen is None else seen
    if out.as_pointer() in seen:
        return None
    seen = seen | {out.as_pointer()}
    node = out.node
    if node.type == "TEX_NOISE" and out.name == "Fac":
        return 0, 1
    if node.type == "VALTORGB":
        values = [component for element in node.color_ramp.elements for component in element.color[:3]]
        return min(values), max(values)
    if node.type == "MAP_RANGE" and node.clamp and node.data_type == "FLOAT":
        low = constant(node.inputs["To Min"])
        high = constant(node.inputs["To Max"])
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            return min(low, high), max(low, high)
    if node.type == "MATH":
        a = scalar_range(node.inputs[0], seen)
        b = scalar_range(node.inputs[1], seen)
        if a is None or b is None:
            return None
        if node.operation == "MULTIPLY":
            values = [x * y for x in a for y in b]
            bounds = min(values), max(values)
        elif node.operation == "ADD":
            bounds = a[0] + b[0], a[1] + b[1]
        elif node.operation == "SUBTRACT":
            bounds = a[0] - b[1], a[1] - b[0]
        elif node.operation == "MAXIMUM":
            bounds = max(a[0], b[0]), max(a[1], b[1])
        elif node.operation == "MINIMUM":
            bounds = min(a[0], b[0]), min(a[1], b[1])
        elif node.operation == "POWER" and a[0] >= 0 and b[0] == b[1] and b[0] > 0:
            bounds = a[0] ** b[0], a[1] ** b[1]
        else:
            return None
        return (max(0, min(1, bounds[0])), max(0, min(1, bounds[1]))) if node.use_clamp else bounds
    return None


def image_socket(socket):
    out = origin(socket)
    if out is None or out.node.type != "TEX_IMAGE":
        return None
    node = out.node
    vector = origin(node.inputs["Vector"])
    uv_input = vector is None or vector.node.type == "UVMAP" or (vector.node.type == "TEX_COORD" and vector.name == "UV")
    if node.projection != "FLAT" or not uv_input:
        return None
    image = node.image
    check(image is not None, "Missing image on " + node.name)
    check(image.source in ("FILE", "GENERATED"), "Unsupported image source: " + image.name)
    check(image.size[0] > 0 and image.size[1] > 0, "Missing image pixels: " + image.name)
    if image.source == "FILE" and not image.packed_file:
        check(Path(bpy.path.abspath(image.filepath, library=image.library)).is_file(), "Missing image file: " + image.filepath)
    uv = vector.node.uv_map if vector and vector.node.type == "UVMAP" else SOURCE_UV
    return {"image": image, "output": out.name, "uv": uv or SOURCE_UV,
            "extension": node.extension, "interpolation": node.interpolation}


def shader_info(mat):
    check(mat.use_nodes and mat.node_tree, "Material requires nodes: " + mat.name)
    outputs = [n for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output]
    check(len(outputs) == 1, "Ambiguous active material output: " + mat.name)
    output = outputs[0]
    check(not output.inputs["Displacement"].is_linked and not output.inputs["Volume"].is_linked,
          "Apply displacement to geometry / remove volume before export: " + mat.name)
    surface = origin(output.inputs["Surface"])
    check(surface is not None, "Disconnected surface: " + mat.name)
    node = surface.node
    extras = {}
    if node.type in ("MIX_SHADER", "ADD_SHADER"):
        branches = [origin(inp) for inp in node.inputs if inp.type == "SHADER"]
        principled = [out.node for out in branches if out and out.node.type == "BSDF_PRINCIPLED"]
        emission = [out.node for out in branches if out and out.node.type == "EMISSION"]
        check(len(principled) == 1 and len(emission) == 1 and view_dependent(output.inputs["Surface"]),
              "Unsupported surface mix (cannot flatten safely): " + mat.name)
        extras["lifeos_runtime_atmosphere"] = graph_extra(output.inputs["Surface"])
        node = principled[0]
    check(node.type in ("BSDF_PRINCIPLED", "EMISSION"), "Unsupported surface shader: " + mat.name + ": " + node.type)
    if node.type == "EMISSION":
        sockets = {"Emission Color": node.inputs["Color"]}
        strength_socket = node.inputs["Strength"]
    else:
        sockets = {name: node.inputs[name] for name in CHANNELS}
        strength_socket = node.inputs["Emission Strength"]
        for inp in node.inputs:
            check(not inp.is_linked or inp.name in CHANNELS or inp.name == "Emission Strength",
                  "Unsupported linked Principled channel: " + mat.name + ": " + inp.name)
    procedural_strength = False
    if view_dependent(strength_socket) or view_dependent(sockets["Emission Color"]):
        extras["lifeos_runtime_emission"] = {"color": graph_extra(sockets["Emission Color"]),
                                             "strength": graph_extra(strength_socket), "exported_strength": 0}
        strength = 0
    else:
        strength = constant(strength_socket)
        if strength is None:
            bounds = scalar_range(strength_socket)
            scale = mat.get("lifeos_emission_scale")
            check(bounds is not None or isinstance(scale, (int, float)),
                  "Cannot bound procedural emission strength; set material lifeos_emission_scale to its peak: " + mat.name)
            check(bounds is None or bounds[0] >= 0, "Negative procedural emission strength: " + mat.name)
            strength = float(scale) if scale is not None else bounds[1]
            check(strength > 0 and (bounds is None or strength >= bounds[1]), "Emission scale below procedural peak: " + mat.name)
            procedural_strength = True
            extras["lifeos_baked_emission_modulation"] = {"strength_graph": graph_extra(strength_socket),
                                                          "normalization_strength": strength}
        check(isinstance(strength, (int, float)) and math.isfinite(strength) and strength >= 0,
              "Invalid emission strength: " + mat.name)
    plans = {}
    for name, socket in sockets.items():
        if name == "Emission Color" and strength == 0:
            continue
        check(not view_dependent(socket), "View-dependent PBR channel cannot be baked: " + mat.name + ": " + name)
        if name == "Normal":
            if not socket.is_linked:
                continue
            out = origin(socket)
            normal = out.node
            texture = image_socket(normal.inputs["Color"]) if normal.type == "NORMAL_MAP" else None
            scale = constant(normal.inputs["Strength"]) if normal.type == "NORMAL_MAP" else None
            if texture and normal.space == "TANGENT" and scale is not None:
                texture["uv"] = normal.uv_map or texture["uv"]
                plans[name] = {"kind": "normal_image", "texture": texture, "scale": scale}
            else:
                plans[name] = {"kind": "bake"}
        elif name == "Emission Color" and procedural_strength:
            plans[name] = {"kind": "bake"}
        else:
            value = constant(socket)
            texture = image_socket(socket) if value is None else None
            plans[name] = ({"kind": "constant", "value": value} if value is not None else
                           {"kind": "image", "texture": texture} if texture else {"kind": "bake"})
    return {"node": node, "output": output, "sockets": sockets, "strength": strength,
            "strength_socket": strength_socket, "procedural_strength": procedural_strength,
            "extras": extras, "plans": plans}


def excluded(obj, names):
    return obj.name in names or "NONEXPORT" in obj.name.upper().replace("_", "") or bool(
        obj.get("nonexport", False) or obj.get("non_export", False) or obj.get("lifeos_nonexport", False)
        or obj.get("export_exclude", False)) or any(obj.get(key, True) == False
                                                 for key in ("export", "gltf_export", "art_export"))


def activate(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def clone_scene(args):
    source = bpy.data.scenes.get(args.scene)
    check(source is not None, "Exact scene not found: " + args.scene)
    bpy.context.window.scene = source
    assets = bpy.data.collections.get(args.collection)
    check(assets is not None, "Exact asset collection not found: " + args.collection)

    def collection_objects(collection):
        if collection.hide_render:
            return set()
        result = set(collection.objects)
        for child in collection.children:
            result.update(collection_objects(child))
        return result

    def has_collection(collection):
        return collection == assets or any(has_collection(c) for c in collection.children)

    check(has_collection(source.collection), "Asset collection is not in requested scene")
    candidates = collection_objects(assets)
    roots = {name: source.objects.get(name) for name in ROOTS}
    for name, obj in roots.items():
        check(obj is not None and obj in candidates and obj.type == "EMPTY", "Missing asset parent: " + name)
        check(not excluded(obj, args.exclude), "Required parent marked nonexport: " + name)
    camera = source.objects.get(args.camera)
    check(camera is not None and camera.type == "CAMERA", "Exact camera not found: " + args.camera)
    selected = set(roots.values()) | {camera}
    skipped = []
    for obj in candidates:
        ancestor = obj
        blocked = False
        while ancestor:
            blocked |= excluded(ancestor, args.exclude) or ancestor.hide_render
            ancestor = ancestor.parent
        if blocked or obj.type == "LIGHT" or (obj.type == "CAMERA" and obj != camera):
            skipped.append(obj.name)
            continue
        check(obj.type in ("EMPTY", "MESH", "CURVE", "SURFACE", "FONT", "CAMERA"), "Unsupported object: " + obj.name)
        check(obj.instance_type == "NONE", "Realize instances before export: " + obj.name)
        selected.add(obj)
    for obj in list(selected):
        parent = obj.parent
        while parent:
            check(parent in candidates and parent.type == "EMPTY", "Parent outside artwork / non-empty parent: " + obj.name)
            selected.add(parent)
            parent = parent.parent
    depsgraph = bpy.context.evaluated_depsgraph_get()
    snapshots = {}
    for obj in selected:
        evaluated = obj.evaluated_get(depsgraph)
        data = obj.data.copy() if obj.type == "CAMERA" else None
        if obj.type in ("MESH", "CURVE", "SURFACE", "FONT"):
            check(not obj.animation_data and not (obj.type == "MESH" and obj.data.shape_keys),
                  "Animated geometry requires a separate export contract: " + obj.name)
            data = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
            check(data and len(data.polygons) > 0, "Empty evaluated geometry: " + obj.name)
        snapshots[obj] = (obj.name, data, evaluated.matrix_world.copy(), obj.parent)
    temporary = bpy.data.scenes.new("LifeOS_Art_Export_Temporary")
    temporary.render.engine = "CYCLES"
    temporary.cycles.device = args.device
    temporary.cycles.samples = args.samples
    temporary.render.threads_mode = "FIXED"
    temporary.render.threads = args.threads
    temporary.render.bake.margin = args.margin
    temporary.render.bake.use_selected_to_active = False
    temporary.world = source.world
    temporary.render.resolution_x = source.render.resolution_x
    temporary.render.resolution_y = source.render.resolution_y
    temporary.render.resolution_percentage = source.render.resolution_percentage
    temporary.render.pixel_aspect_x = source.render.pixel_aspect_x
    temporary.render.pixel_aspect_y = source.render.pixel_aspect_y
    temporary["lifeos_source_scene"] = args.scene
    temporary["lifeos_external_background"] = "/art/system/deep-space-v1.png"
    clones = {}
    for obj, (name, data, world, _) in snapshots.items():
        obj.name = "Source::" + name
        clone = bpy.data.objects.new(name, data)
        for key in obj.keys():
            if key != "_RNA_UI":
                clone[key] = obj[key]
        temporary.collection.objects.link(clone)
        clone.matrix_world = world
        clones[obj] = clone
    for obj, (_, _, world, parent) in snapshots.items():
        clone = clones[obj]
        if parent:
            clone.parent = clones[parent]
        elif clone.type == "MESH" and obj not in roots.values():
            clone.parent = clones[roots["Scenery"]]
        clone.matrix_world = world
    bpy.context.window.scene = temporary
    temporary.camera = clones[camera]
    bpy.context.view_layer.update()
    log("Isolated {} objects; excluded {}".format(len(clones), len(skipped)))
    return temporary, skipped


def root_of(obj):
    current = obj
    while current:
        if current.name in ROOTS:
            return current.name
        current = current.parent
    raise RuntimeError("Geometry has no named art root: " + obj.name)


def ensure_uv(obj):
    mesh = obj.data
    uv = mesh.uv_layers.active
    valid = uv is not None
    if valid:
        for poly in mesh.polygons:
            points = [uv.data[i].uv for i in poly.loop_indices]
            area = abs(sum(a.x * b.y - a.y * b.x for a, b in zip(points, points[1:] + points[:1])))
            if area < 1e-12 and poly.area > 1e-12:
                valid = False
                break
    if not valid:
        if uv is None:
            uv = mesh.uv_layers.new(name="UVMap")
        activate([obj])
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.025)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
        log("Smart-projected " + obj.name)
    check(SOURCE_UV not in mesh.uv_layers and BAKE_UV not in mesh.uv_layers, "Reserved export UV name on " + obj.name)
    copy = mesh.uv_layers.new(name=SOURCE_UV)
    for source, target in zip(uv.data, copy.data):
        check(all(math.isfinite(v) for v in source.uv), "Non-finite UV: " + obj.name)
        target.uv = source.uv
    mesh.uv_layers.active = copy
    copy.active_render = True


def triangulate(obj):
    # Tangent calculation cannot handle authored n-gons, including metal end caps.
    import bmesh
    mesh = bmesh.new()
    try:
        mesh.from_mesh(obj.data)
        bmesh.ops.triangulate(mesh, faces=list(mesh.faces), quad_method="BEAUTY", ngon_method="BEAUTY")
        mesh.to_mesh(obj.data)
    finally:
        mesh.free()
    obj.data.update()


def stabilize_uv(mat):
    tree = mat.node_tree
    uv = tree.nodes.new("ShaderNodeUVMap")
    uv.uv_map = SOURCE_UV
    for node in list(tree.nodes):
        if node.type == "TEX_IMAGE" and not node.inputs["Vector"].is_linked:
            tree.links.new(uv.outputs["UV"], node.inputs["Vector"])
        if node.type == "TEX_COORD":
            for link in list(node.outputs["UV"].links):
                tree.links.new(uv.outputs["UV"], link.to_socket)


def make_atlases(objects, bake_objects, margin, size):
    groups = defaultdict(list)
    for obj in objects:
        if obj in bake_objects:
            groups[root_of(obj)].append(obj)
    for root, members in groups.items():
        members.sort(key=lambda o: o.name)
        cells = math.ceil(math.sqrt(len(members)))
        padding = (margin + 2) / size
        check(padding * 2 < 1 / cells, "Atlas too small for " + root + "; increase --size or reduce --margin")
        for index, obj in enumerate(members):
            original = obj.data.uv_layers[SOURCE_UV]
            uv = obj.data.uv_layers.new(name=BAKE_UV)
            coords = [entry.uv for entry in original.data]
            low = (min(v.x for v in coords), min(v.y for v in coords))
            high = (max(v.x for v in coords), max(v.y for v in coords))
            extent = max(high[0] - low[0], high[1] - low[1], 1e-8)
            scale = (1 / cells - 2 * padding) / extent
            x, y = index % cells / cells + padding, index // cells / cells + padding
            for source, target in zip(original.data, uv.data):
                target.uv = ((source.uv.x - low[0]) * scale + x, (source.uv.y - low[1]) * scale + y)
            obj.data.uv_layers.active = uv
            uv.active_render = True


def texture_node(tree, target, texture):
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = texture["image"]
    node.extension = texture.get("extension", "EXTEND")
    node.interpolation = texture.get("interpolation", "Linear")
    uv = tree.nodes.new("ShaderNodeUVMap")
    uv.uv_map = texture["uv"]
    tree.links.new(uv.outputs["UV"], node.inputs["Vector"])
    tree.links.new(node.outputs[texture.get("output", "Color")], target)


def new_portable(source, root, info):
    mat = bpy.data.materials.new("Art_" + root + "_" + source.name)
    mat.use_nodes = True
    mat.diffuse_color = source.diffuse_color
    mat.use_backface_culling = source.use_backface_culling
    mat.surface_render_method = source.surface_render_method
    for key in source.keys():
        if key != "_RNA_UI":
            mat[key] = source[key]
    shader = mat.node_tree.nodes.get("Principled BSDF")
    if info["node"].type == "BSDF_PRINCIPLED":
        for inp in info["node"].inputs:
            if inp.name in shader.inputs and hasattr(inp, "default_value") and not inp.is_linked:
                shader.inputs[inp.name].default_value = inp.default_value
    else:
        shader.inputs["Base Color"].default_value = (0, 0, 0, 1)
        shader.inputs["Roughness"].default_value = 1
        shader.inputs["Specular IOR Level"].default_value = 0
        mat["lifeos_unlit_emission"] = True
    shader.inputs["Emission Strength"].default_value = info["strength"]
    mat["lifeos_source_material"] = source.name
    mat["lifeos_emissive_strength"] = info["strength"]
    for key, value in info["extras"].items():
        mat[key] = value
    for channel, plan in info["plans"].items():
        if plan["kind"] == "constant":
            shader.inputs[channel].default_value = plan["value"]
        elif plan["kind"] == "image":
            texture_node(mat.node_tree, shader.inputs[channel], plan["texture"])
        elif plan["kind"] == "normal_image":
            normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
            normal.uv_map = plan["texture"]["uv"]
            normal.inputs["Strength"].default_value = plan["scale"]
            texture_node(mat.node_tree, normal.inputs["Color"], plan["texture"])
            mat.node_tree.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    return mat


def bake_channel(scene, members, source, info, channel, image, scratch):
    activate(members)
    mats = {slot.material for obj in members for slot in obj.material_slots if slot.material}
    targets = []
    for mat in mats:
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image if mat == source else scratch
        mat.node_tree.nodes.active = node
        targets.append((mat, node))
    tree = source.node_tree
    surface = info["output"].inputs["Surface"]
    old = origin(surface)
    emitter = None
    modulation = []
    try:
        if channel == "Normal":
            tree.links.new(info["node"].outputs[0], surface)
            bake_type = "NORMAL"
        else:
            # EMIT captures raw channel values without lighting or color management.
            emitter = tree.nodes.new("ShaderNodeEmission")
            socket = info["sockets"][channel]
            if socket.is_linked:
                tree.links.new(socket.links[0].from_socket, emitter.inputs["Color"])
            else:
                value = socket.default_value
                emitter.inputs["Color"].default_value = value if socket.type == "RGBA" else (value, value, value, 1)
            emitter.inputs["Strength"].default_value = 1
            if channel == "Emission Color" and info["procedural_strength"]:
                multiplier = tree.nodes.new("ShaderNodeMath")
                multiplier.operation = "DIVIDE"
                multiplier.inputs[1].default_value = info["strength"]
                tree.links.new(info["strength_socket"].links[0].from_socket, multiplier.inputs[0])
                tree.links.new(multiplier.outputs[0], emitter.inputs["Strength"])
                modulation.append(multiplier)
            tree.links.new(emitter.outputs[0], surface)
            bake_type = "EMIT"
        log("Bake {} / {}: {} objects at {}px".format(source.name, channel, len(members), image.size[0]))
        result = bpy.ops.object.bake(type=bake_type, use_clear=False, margin=scene.render.bake.margin,
                                     normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z",
                                     use_selected_to_active=False, target="IMAGE_TEXTURES", uv_layer=BAKE_UV)
        check("FINISHED" in result, "Cycles bake did not finish: " + source.name + ": " + channel)
    finally:
        if old:
            tree.links.new(old, surface)
        if emitter:
            tree.nodes.remove(emitter)
        for node in modulation:
            tree.nodes.remove(node)
        for mat, node in targets:
            mat.node_tree.nodes.remove(node)


def prepare_source_images(scene, args):
    replacements, report = {}, []
    materials = {slot.material for obj in scene.objects if obj.type == "MESH"
                 for slot in obj.material_slots if slot.material}
    for mat in materials:
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type != "TEX_IMAGE" or not node.image:
                continue
            image = node.image
            width, height = image.size
            if max(width, height) <= args.max_source_size:
                continue
            if image not in replacements:
                check(width > 0 and height > 0 and image.source == "FILE", "Unsupported oversized source image: " + image.name)
                factor = args.max_source_size / max(width, height)
                copy = image.copy()
                copy.name = "Portable_" + image.name
                copy.scale(max(1, round(width * factor)), max(1, round(height * factor)))
                slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(image.name).stem)
                copy.file_format = "PNG"
                copy.filepath_raw = str(args.textures / (slug + "_portable_" + str(args.max_source_size) + ".png"))
                copy.save()
                copy.pack()
                copy["lifeos_original_image_path"] = bpy.path.abspath(image.filepath, library=image.library)
                replacements[image] = copy
                report.append({"original": image.name, "original_path": copy["lifeos_original_image_path"],
                               "original_dimensions": [width, height], "portable_dimensions": list(copy.size),
                               "portable_path": copy.filepath_raw})
            node.image = replacements[image]
    return report


def prepare_materials(scene, args):
    objects = sorted((o for o in scene.objects if o.type == "MESH"), key=lambda o: o.name)
    original_materials = {}
    groups = defaultdict(set)
    for obj in objects:
        ensure_uv(obj)
        check(len(obj.data.materials) and all(slot.material for slot in obj.material_slots), "Missing material: " + obj.name)
        used = sorted({poly.material_index for poly in obj.data.polygons})
        check(used[-1] < len(obj.data.materials), "Invalid polygon material: " + obj.name)
        if len(used) != len(obj.data.materials):
            materials = [obj.data.materials[index] for index in used]
            remap = {old: new for new, old in enumerate(used)}
            indices = [remap[poly.material_index] for poly in obj.data.polygons]
            obj.data.materials.clear()
            for mat in materials:
                obj.data.materials.append(mat)
            for poly, index in zip(obj.data.polygons, indices):
                poly.material_index = index
        triangulate(obj)
        original_materials[obj] = list(obj.data.materials)
        for mat in obj.data.materials:
            groups[(root_of(obj), mat)].add(obj)
    infos = {mat: shader_info(mat) for _, mat in groups}
    bake_objects = set().union(*(members for (_, mat), members in groups.items()
                               if any(p["kind"] == "bake" for p in infos[mat]["plans"].values())))
    make_atlases(objects, bake_objects, args.margin, args.size)
    work, portable = {}, {}
    for root, mat in groups:
        copy = mat.copy()
        copy.name = "Bake_" + root + "_" + mat.name
        stabilize_uv(copy)
        work[(root, mat)] = copy
        portable[(root, mat)] = new_portable(mat, root, infos[mat])
    for obj, materials in original_materials.items():
        for index, mat in enumerate(materials):
            obj.data.materials[index] = work[(root_of(obj), mat)]
    scratch = bpy.data.images.new("Art_Discard_Bake", width=4, height=4)
    scratch.colorspace_settings.name = "Non-Color"
    report = []
    for (root, mat), members in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1].name)):
        bake_mat = work[(root, mat)]
        info = shader_info(bake_mat)
        output = portable[(root, mat)]
        shader = output.node_tree.nodes.get("Principled BSDF")
        baked = {}
        preserved = {}
        for channel, plan in info["plans"].items():
            if plan["kind"] in ("image", "normal_image"):
                preserved[channel] = {"name": plan["texture"]["image"].name,
                                      "filepath": bpy.path.abspath(plan["texture"]["image"].filepath),
                                      "original_filepath": plan["texture"]["image"].get("lifeos_original_image_path")}
            if plan["kind"] != "bake":
                continue
            slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", output.name + "_" + channel)
            image = bpy.data.images.new(slug, width=args.size, height=args.size, alpha=False, float_buffer=False)
            image.colorspace_settings.name = "sRGB" if channel in ("Base Color", "Emission Color") else "Non-Color"
            image.generated_color = (0.5, 0.5, 1, 1) if channel == "Normal" else (0, 0, 0, 1)
            bake_channel(scene, sorted(members, key=lambda o: o.name), bake_mat, info, channel, image, scratch)
            image.filepath_raw = str(args.textures / (slug + ".png"))
            image.file_format = "PNG"
            image.save()
            image.pack()
            target = shader.inputs[channel]
            if channel == "Normal":
                normal = output.node_tree.nodes.new("ShaderNodeNormalMap")
                normal.uv_map = BAKE_UV
                output.node_tree.links.new(normal.outputs["Normal"], target)
                target = normal.inputs["Color"]
            texture_node(output.node_tree, target, {"image": image, "uv": BAKE_UV})
            baked[channel] = image.filepath_raw
        physical = {}
        if info["node"].type == "BSDF_PRINCIPLED":
            physical = {"transmission": float(info["node"].inputs["Transmission Weight"].default_value),
                        "ior": float(info["node"].inputs["IOR"].default_value),
                        "specular": min(1.0, float(info["node"].inputs["Specular IOR Level"].default_value) * 2)}
        report.append({"material": output.name, "source_material": mat.name, "root": root,
                       "objects": sorted(o.name for o in members), "baked": baked, "preserved_images": preserved,
                       "emissive_strength": info["strength"], "runtime_extras": info["extras"],
                       "physical_contract": physical,
                       "art_rim_contract": {key: plain(mat[key]) for key in
                           ("art_rim_color", "art_rim_strength", "art_rim_direction", "art_rim_floor") if key in mat}})
    for obj, materials in original_materials.items():
        for index, mat in enumerate(materials):
            obj.data.materials[index] = portable[(root_of(obj), mat)]
        # UV0 remains a conventional source UV even when an atlas is also present.
        obj.data.uv_layers.active = obj.data.uv_layers[SOURCE_UV]
        obj.data.uv_layers[SOURCE_UV].active_render = True
    return report


def consolidate(scene):
    groups = defaultdict(list)
    for obj in scene.objects:
        parent = obj.parent
        batch_parent = parent and (parent.name in ROOTS or (
            parent.get("art_scenery_layer") is True and parent.parent and parent.parent.name == "Scenery"))
        if (obj.type == "MESH" and batch_parent and len(obj.data.materials) == 1
                and not obj.children and not obj.keys() and obj.matrix_world.determinant() > 0):
            groups[(obj.parent, obj.data.materials[0])].append(obj)
    merged = []
    for (parent, mat), members in groups.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda o: o.name)
        names = [o.name for o in members]
        activate(members)
        result = bpy.ops.object.join()
        check("FINISHED" in result, "Geometry consolidation failed: " + parent.name)
        obj = bpy.context.object
        obj.name = parent.name + "_Batch_" + mat.name
        merged.append({"object": obj.name, "source_objects": names})
    return merged


def validate_channels(report, baked_materials):
    materials = {m["name"]: m for m in report["materials"]}
    for contract in baked_materials:
        mat = materials.get(contract["material"])
        check(mat is not None, "Expected material absent from GLB: " + contract["material"])
        slots = mat["textures"]
        expected = set(contract["baked"]) | set(contract["preserved_images"])
        for channel in expected:
            slot = {"Base Color": "baseColorTexture", "Alpha": "baseColorTexture", "Normal": "normalTexture",
                    "Emission Color": "emissiveTexture", "Metallic": "metallicRoughnessTexture",
                    "Roughness": "metallicRoughnessTexture"}[channel]
            check(slot in slots, "Lost texture channel in GLB: " + contract["material"] + ": " + channel)
        if contract["emissive_strength"]:
            check(any(mat["emissive_factor"]), "Lost emission in GLB: " + contract["material"])
        if "Alpha" in expected:
            check(mat["alpha_mode"] in ("BLEND", "MASK"), "Lost transparency in GLB: " + contract["material"])
        physical = contract.get("physical_contract", {})
        extensions = mat["extensions"]
        for channel, extension, field, default in [
            ("transmission", "KHR_materials_transmission", "transmissionFactor", 0),
            ("ior", "KHR_materials_ior", "ior", 1.5),
            ("specular", "KHR_materials_specular", "specularFactor", 1),
        ]:
            if channel in physical:
                actual = extensions.get(extension, {}).get(field, default)
                check(abs(actual - physical[channel]) < 1e-6,
                      "Lost physical material channel in GLB: " + contract["material"] + ": " + channel)
        for key, expected in contract.get("art_rim_contract", {}).items():
            actual = mat["extras"].get(key)
            if isinstance(expected, list):
                valid = (isinstance(actual, list) and len(actual) == len(expected)
                         and all(abs(a - b) < 1e-6 for a, b in zip(actual, expected)))
            else:
                valid = isinstance(actual, (int, float)) and abs(actual - expected) < 1e-6
            check(valid, "Lost runtime limb contract in GLB: " + contract["material"] + ": " + key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--size", type=int, default=1024, help="Square atlas size per root/material/channel")
    parser.add_argument("--max-source-size", type=int, default=2048, help="Cap portable source maps; editable original images remain unchanged")
    parser.add_argument("--samples", type=int, default=1, help="Cycles bake samples (unlit channel and normal bakes)")
    parser.add_argument("--threads", type=int, default=4, help="CPU threads, shared with other background work")
    parser.add_argument("--margin", type=int, default=4)
    parser.add_argument("--device", choices=("CPU", "GPU"), default="CPU")
    parser.add_argument("--scene", default="LifeOS_System_Composition_V2")
    parser.add_argument("--collection", default="Art_V2_Assets")
    parser.add_argument("--camera", default="System_Composition_Camera")
    parser.add_argument("--exclude", action="append", default=[], help="Exact explicitly nonexport object name")
    parser.add_argument("--no-consolidate", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    check(bpy.app.background, "Run in a separate --background Blender process")
    check(32 <= args.size <= 8192 and 32 <= args.max_source_size <= 8192 and args.samples >= 1 and args.margin >= 0 and 1 <= args.threads <= 1024,
          "Invalid bake size/samples/margin/threads")
    args.output = args.output.resolve()
    args.textures = args.textures.resolve()
    check(args.output.suffix.lower() == ".glb", "--output must be a .glb path")
    source = Path(bpy.data.filepath).resolve()
    check(source.is_file() and source != args.output, "Load a source blend and use a different output path")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.textures.mkdir(parents=True, exist_ok=True)
    pending = args.output.with_name(args.output.stem + ".exporting.glb")
    start = time.monotonic()
    try:
        scene, skipped = clone_scene(args)
        source_images = prepare_source_images(scene, args)
        materials = prepare_materials(scene, args)
        merged = [] if args.no_consolidate else consolidate(scene)
        activate(list(scene.objects))
        properties = bpy.ops.export_scene.gltf.get_rna_type().properties
        settings = {"filepath": str(pending), "export_format": "GLB", "check_existing": False,
                    "use_active_scene": True, "use_selection": True, "export_cameras": True,
                    "export_lights": False, "export_extras": True, "export_animations": False,
                    "export_current_frame": True, "export_apply": False, "export_texcoords": True,
                    "export_normals": True, "export_tangents": True, "export_materials": "EXPORT",
                    "export_image_format": "AUTO", "export_keep_originals": False,
                    "export_vertex_color": "NONE", "export_skins": False, "export_morph": False,
                    "export_try_sparse_sk": False, "export_try_omit_sparse_sk": False,
                    "export_yup": True, "will_save_settings": False}
        check(all(key in properties for key in settings), "Installed glTF operator lacks required export options")
        log("Exporting via Blender " + bpy.app.version_string)
        check("FINISHED" in bpy.ops.export_scene.gltf(**settings), "glTF export failed")
        report = inspect_glb(pending, ROOTS, args.camera)
        validate_channels(report, materials)
        check(hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, "Source blend changed during export")
        report.update({"source_blend": str(source), "source_sha256": source_hash, "source_unchanged": True,
                       "source_scene": args.scene, "source_collection": args.collection,
                       "blender_version": bpy.app.version_string, "bake_size": args.size,
                       "max_source_texture_size": args.max_source_size, "source_texture_preparation": source_images,
                       "bake_samples": args.samples, "material_preparation": materials,
                       "consolidation": merged, "excluded_objects": sorted(skipped),
                       "elapsed_seconds": round(time.monotonic() - start, 2),
                       "external_background": "/art/system/deep-space-v1.png",
                       "path": str(args.output), "visual_fidelity": "not evaluated"})
        pending.replace(args.output)
        report_path = args.output.with_suffix(".report.json")
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        log("Validated: {} triangles, {} draw calls, {} embedded images, {:.2f} MiB GLB".format(
            report["triangles"], report["draw_calls"], len(report["images"]), report["file_bytes"] / 1048576))
        log("Report: " + str(report_path))
    finally:
        if pending.is_file():
            pending.unlink()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
