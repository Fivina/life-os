"""Dependency-free GLB structural validation and geometry/texture accounting.

Run with ordinary Python: inspect_art_glb.py artwork.glb [--json report.json].
This checks portability and structure, not rendered appearance.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def image_size(data, mime):
    if mime == "image/png":
        require(data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24, "Invalid PNG")
        return struct.unpack_from(">II", data, 16)
    if mime == "image/jpeg":
        require(data[:2] == b"\xff\xd8", "Invalid JPEG")
        offset = 2
        while offset < len(data):
            require(data[offset] == 255, "Invalid JPEG marker")
            while offset < len(data) and data[offset] == 255:
                offset += 1
            require(offset < len(data), "Truncated JPEG marker")
            marker = data[offset]
            offset += 1
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            require(offset + 2 <= len(data), "Truncated JPEG segment")
            length = struct.unpack_from(">H", data, offset)[0]
            require(length >= 2 and offset + length <= len(data), "Invalid JPEG segment")
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack_from(">HH", data, offset + 3)
                return width, height
            offset += length
    raise ValueError("Unsupported or malformed embedded image: " + str(mime))


def inspect_glb(path, required_roots=(), camera_name=None):
    path = Path(path)
    raw = path.read_bytes()
    require(len(raw) >= 20, "Truncated GLB header")
    magic, version, length = struct.unpack_from("<4sII", raw)
    require(magic == b"glTF" and version == 2 and length == len(raw), "Invalid GLB header")
    chunks = []
    offset = 12
    while offset < length:
        require(offset + 8 <= length, "Truncated chunk header")
        size, kind = struct.unpack_from("<II", raw, offset)
        offset += 8
        require(size % 4 == 0 and offset + size <= length, "Invalid chunk length")
        chunks.append((kind, raw[offset:offset + size]))
        offset += size
    require([kind for kind, _ in chunks] == [0x4E4F534A, 0x004E4942], "Expected JSON then BIN chunks")
    doc = json.loads(chunks[0][1].decode("utf-8"))
    binary = chunks[1][1]
    require(doc.get("asset", {}).get("version") == "2.0", "Expected glTF 2.0")
    buffers = doc.get("buffers", [])
    require(len(buffers) == 1 and "uri" not in buffers[0], "GLB must have one embedded buffer")
    binary_length = buffers[0]["byteLength"]
    require(0 <= len(binary) - binary_length <= 3, "BIN/buffer length mismatch")
    views = doc.get("bufferViews", [])
    for view in views:
        require(view.get("buffer", 0) == 0, "External buffer reference")
        require(view.get("byteOffset", 0) >= 0 and view["byteLength"] >= 0, "Negative buffer range")
        require(view.get("byteOffset", 0) + view["byteLength"] <= binary_length, "Buffer view out of bounds")
    accessors = doc.get("accessors", [])
    components = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    arities = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    for accessor in accessors:
        require("sparse" not in accessor, "Sparse accessors are outside this art export contract")
        require(accessor.get("count", -1) >= 0, "Invalid accessor count")
        require(accessor.get("componentType") in components and accessor.get("type") in arities,
                "Unsupported accessor type")
        view_index = accessor.get("bufferView", -1)
        require(0 <= view_index < len(views), "Missing accessor buffer view")
        view = views[view_index]
        item_size = components[accessor["componentType"]] * arities[accessor["type"]]
        stride = view.get("byteStride", item_size)
        start = accessor.get("byteOffset", 0)
        end = start + max(0, accessor["count"] - 1) * stride + (item_size if accessor["count"] else 0)
        require(start >= 0 and stride >= item_size and end <= view["byteLength"], "Accessor out of bounds")
    scenes = doc.get("scenes", [])
    require(len(scenes) == 1 and doc.get("scene", 0) == 0, "Expected exactly one exported scene")
    nodes = doc.get("nodes", [])
    reachable, visiting = set(), set()

    def visit(index):
        require(0 <= index < len(nodes), "Invalid node reference")
        require(index not in visiting, "Cyclic node hierarchy")
        require(index not in reachable, "Node has more than one parent")
        reachable.add(index)
        visiting.add(index)
        for child in nodes[index].get("children", []):
            visit(child)
        visiting.remove(index)

    for index in scenes[0].get("nodes", []):
        visit(index)
    require(len(reachable) == len(nodes), "Unreachable exported nodes")
    names = [node.get("name") for node in nodes]
    for root in required_roots:
        require(names.count(root) == 1, "Missing or duplicate named root: " + root)
        require("mesh" not in nodes[names.index(root)], "Root must remain a parent: " + root)
    if camera_name:
        require(names.count(camera_name) == 1, "Missing named camera: " + camera_name)
        require("camera" in nodes[names.index(camera_name)] and len(doc.get("cameras", [])) == 1,
                "Expected exactly one camera")
    require("KHR_lights_punctual" not in doc.get("extensions", {}), "Unexpected staging lights")
    require(not any("KHR_lights_punctual" in n.get("extensions", {}) for n in nodes), "Unexpected light nodes")
    textures = doc.get("textures", [])
    images = doc.get("images", [])
    for texture in textures:
        require(0 <= texture.get("source", -1) < len(images), "Missing texture image")
    texture_report = []
    for index, img in enumerate(images):
        require("uri" not in img and 0 <= img.get("bufferView", -1) < len(views), "Image is not embedded")
        view = views[img["bufferView"]]
        start = view.get("byteOffset", 0)
        width, height = image_size(binary[start:start + view["byteLength"]], img.get("mimeType"))
        require(width > 0 and height > 0, "Empty image")
        texture_report.append({"index": index, "name": img.get("name"), "width": width, "height": height,
                               "encoded_bytes": view["byteLength"], "rgba8_bytes": width * height * 4,
                               "sha256": hashlib.sha256(binary[start:start + view["byteLength"]]).hexdigest()})
    materials = doc.get("materials", [])
    material_report = []
    material_uvs = []
    for mat in materials:
        pbr = mat.get("pbrMetallicRoughness", {})
        slots = {k: v for k, v in mat.items() if k.endswith("Texture")}
        slots.update({k: v for k, v in pbr.items() if k.endswith("Texture")})
        uv_sets = set()
        for slot in slots.values():
            require(0 <= slot.get("index", -1) < len(textures), "Invalid material texture")
            uv_sets.add(slot.get("extensions", {}).get("KHR_texture_transform", {}).get("texCoord", slot.get("texCoord", 0)))
        material_uvs.append(uv_sets)
        material_report.append({"name": mat.get("name"), "textures": slots, "base_color": pbr.get("baseColorFactor", [1, 1, 1, 1]),
                                "metallic": pbr.get("metallicFactor", 1), "roughness": pbr.get("roughnessFactor", 1),
                                "alpha_mode": mat.get("alphaMode", "OPAQUE"),
                                "emissive_factor": mat.get("emissiveFactor", [0, 0, 0]),
                                "extensions": mat.get("extensions", {}), "extras": mat.get("extras", {})})
    meshes = doc.get("meshes", [])
    mesh_counts = []
    for mesh in meshes:
        vertices = triangles = 0
        for primitive in mesh.get("primitives", []):
            attrs = primitive.get("attributes", {})
            require("POSITION" in attrs and "NORMAL" in attrs, "Missing mesh position/normal")
            require("TEXCOORD_0" in attrs, "Missing mesh UVs")
            for value in attrs.values():
                require(0 <= value < len(accessors), "Invalid attribute accessor")
            mat_index = primitive.get("material", -1)
            require(0 <= mat_index < len(materials), "Missing primitive material")
            for uv in material_uvs[mat_index]:
                require("TEXCOORD_" + str(uv) in attrs, "Missing texture UV set")
            if "normalTexture" in materials[mat_index]:
                require("TANGENT" in attrs, "Normal-mapped primitive has no tangents")
            count = accessors[attrs["POSITION"]]["count"]
            require(all(accessors[value]["count"] == count for value in attrs.values()), "Attribute count mismatch")
            vertices += count
            if "indices" in primitive:
                index = primitive["indices"]
                require(0 <= index < len(accessors), "Invalid index accessor")
                count = accessors[index]["count"]
            require(primitive.get("mode", 4) == 4 and count % 3 == 0, "Expected triangle primitives")
            triangles += count // 3
        mesh_counts.append({"name": mesh.get("name"), "vertices": vertices, "triangles": triangles,
                            "primitives": len(mesh.get("primitives", []))})
    draw_calls = instance_triangles = 0
    for node in nodes:
        if "mesh" in node:
            require(0 <= node["mesh"] < len(meshes), "Invalid node mesh")
            counts = mesh_counts[node["mesh"]]
            draw_calls += counts["primitives"]
            instance_triangles += counts["triangles"]
        if "camera" in node:
            require(0 <= node["camera"] < len(doc.get("cameras", [])), "Invalid camera reference")
    report = {"path": str(path.resolve()), "file_bytes": len(raw), "nodes": len(nodes),
              "node_names": names, "meshes": mesh_counts, "materials": material_report, "images": texture_report,
              "vertices": sum(m["vertices"] for m in mesh_counts), "triangles": instance_triangles,
              "draw_calls": draw_calls, "encoded_texture_bytes": sum(i["encoded_bytes"] for i in texture_report),
              "estimated_rgba8_bytes": sum(i["rgba8_bytes"] for i in texture_report),
              "estimated_rgba8_with_mips_bytes": sum(i["rgba8_bytes"] for i in texture_report) * 4 // 3,
              "extensions_used": doc.get("extensionsUsed", []), "structural_validation": "passed"}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--require-root", action="append", default=[])
    parser.add_argument("--camera")
    args = parser.parse_args()
    result = inspect_glb(args.glb, args.require_root, args.camera)
    output = json.dumps(result, indent=2)
    if args.json:
        args.json.write_text(output + "\n", encoding="utf-8")
    print(output)
