"""Fetch and convert Natural Earth's 1:50m land polygons to an equirectangular SVG mask."""

from __future__ import annotations

import io
import struct
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "apps/web/public/assets/core-earth-land.svg"
SOURCE = "https://naciscdn.org/naturalearth/50m/physical/ne_50m_land.zip"
WIDTH = 2048
HEIGHT = 1024


def polygons_from_shapefile(source: bytes):
    offset = 100  # Shapefile file header.
    while offset + 8 <= len(source):
        _, content_words = struct.unpack_from(">2i", source, offset)
        content_start = offset + 8
        content_end = content_start + content_words * 2
        content = source[content_start:content_end]
        shape_type = struct.unpack_from("<i", content, 0)[0]
        if shape_type in (5, 15, 25):  # Polygon, PolygonZ, PolygonM.
            part_count, point_count = struct.unpack_from("<2i", content, 36)
            parts_start = 44
            parts = struct.unpack_from(f"<{part_count}i", content, parts_start)
            points_start = parts_start + part_count * 4
            points = [
                struct.unpack_from("<2d", content, points_start + index * 16)
                for index in range(point_count)
            ]
            ends = (*parts[1:], point_count)
            yield [points[start:end] for start, end in zip(parts, ends)]
        offset = content_end


def to_svg_path(rings):
    commands = []
    for ring in rings:
        if len(ring) < 4:
            continue
        for index, (longitude, latitude) in enumerate(ring):
            x = (longitude + 180.0) * WIDTH / 360.0
            y = (90.0 - latitude) * HEIGHT / 180.0
            command = "M" if index == 0 else "L"
            commands.append(f"{command}{x:.2f},{y:.2f}")
        commands.append("Z")
    return " ".join(commands)


def main():
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "LifeOS CoreEarth asset generator"})
    with urllib.request.urlopen(request, timeout=30) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    shp_name = next(name for name in archive.namelist() if name.lower().endswith(".shp"))
    rings = [ring for polygon in polygons_from_shapefile(archive.read(shp_name)) for ring in polygon]
    path_data = to_svg_path(rings)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}">',
                "  <!-- Land polygons: Natural Earth 1:50m, version 4.0.0; public domain. -->",
                f'  <path fill="#fff" fill-rule="evenodd" d="{path_data}"/>',
                "</svg>",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} ({len(path_data):,} SVG path characters)")


if __name__ == "__main__":
    main()
