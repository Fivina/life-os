"""Extract the visible geographic region, keeping real satellite data within RAM limits."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path('E:/LifeOS-Art/phengos/textures')
source = ROOT / 'nasa-black-marble-C1-500m-gray.jpg'
target = ROOT / 'nasa-black-marble-regional-8k.png'
# NASA's C1 tile covers longitude 0..90E and latitude 0..90N.
WEST, EAST, SOUTH, NORTH = 2.0, 40.0, 35.0, 62.0
Image.MAX_IMAGE_PIXELS = 500_000_000
with Image.open(source) as image:
    assert image.size == (21600, 21600)
    width, height = image.size
    bounds = (round(WEST / 90 * width), round((90 - NORTH) / 90 * height),
              round(EAST / 90 * width), round((90 - SOUTH) / 90 * height))
    region = image.crop(bounds).convert('L')
    region.thumbnail((8192, 8192), Image.Resampling.LANCZOS)
    region.save(target)
    print(json.dumps({'path': str(target), 'size': region.size,
                      'bounds_degrees': [WEST, EAST, SOUTH, NORTH],
                      'source': str(source), 'processing': 'Geographic crop and bounded downsample only'}))
