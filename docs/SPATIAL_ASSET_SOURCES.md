# Spatial Artwork Asset Sources

## Life Globe

- Source: NASA Earth Observatory, Blue Marble: Next Generation, July base map.
- Source page: https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/
- Original JPEG: https://assets.science.nasa.gov/content/dam/science/esd/eo/images/bmng/bmng-base/july/world.200407.3x5400x2700.jpg
- Local source: `E:\LifeOS-Art\textures\nasa-blue-marble-july.jpg`.
- Usage guidance checked: https://www.nasa.gov/nasa-brand-center/images-and-media/
- This is a globe texture used in a private interface, not an assertion of NASA
  endorsement, scientific accuracy of the rendered scene, or exclusive ownership.
  No NASA insignia, persons or promotional endorsement is included.

Life's separate procedural cloud shell is a stylized art layer, not observed
weather or another NASA dataset.

## Fitness Mineral Surface

- Credit: NASA's Scientific Visualization Studio, CGI Moon Kit (LROC/LOLA).
- Verified source page: https://svs.gsfc.nasa.gov/4720/
- Color: https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_2k.jpg
- Height preview: https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_3_8bit.jpg
- Local sources: `E:/LifeOS-Art/textures/nasa-lroc-color-2k.jpg` and
  `E:/LifeOS-Art/textures/nasa-lola-height-1k.jpg`.
- These are albedo/elevation inputs, not lighting baked from a photograph of a
  sphere. The blue-tinted Fitness world is fictional art direction, not a claim
  to depict the Moon scientifically. The 8-bit preview supplies bounded shader
  relief; it is not treated as a precise scientific displacement product.
- Usage follows the NASA guidance above; no NASA branding/endorsement is implied.

## Generated Backdrop

Built-in image-generation asset, generated and inspected 2026-10-01:
`apps/web/public/art/system/deep-space-v1.png` (1672 x 941).
Original retained under the current Codex generated-images directory.
This is distant scenery only, not a rasterized interface or planetary system.

Generation prompt: production-quality cinematic deep-space environment backplate;
wide 16:9 landscape, near-black central negative space, fine blue interstellar
dust crossing diagonally, one small subtle distant spiral galaxy upper right,
varied sparse stars and photographic depth. Avoid text, labels, UI, planets,
orbit lines, lens flares, bright neon nebula, bokeh blobs and geometric grids.
Generated through the built-in image tool, not a user API key or CLI fallback.

## Authored Geometry

## Phengos Opening v2 Surface Assets

- Night lighting: NASA Earth Observatory, Black Marble 2016, 3600x1800 global map.
  Source: https://science.nasa.gov/earth/earth-observatory/earth-at-night/maps/
  Image: https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/144000/144898/BlackMarble_2016_01deg.jpg
  Local: `E:/LifeOS-Art/textures/nasa-black-marble-2016.jpg`.
  NASA usage guidance above applies. Warm emission and rim lighting are artistic,
  not a scientifically accurate day/night or illumination model.
- Neptune, Jupiter, and Earth cloud maps: Solar System Scope / INOVE.
  Source: https://ftp.solarsystemscope.com/textures/
  Downloads: `/textures/download/2k_neptune.jpg`, `2k_jupiter.jpg`,
  `2k_earth_clouds.jpg` on that domain.
  License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ .
  Credit: Solar System Scope / INOVE, NASA-derived planetary textures.
  Local: `E:/LifeOS-Art/textures/sss-neptune.jpg`, `sss-jupiter.jpg`,
  `sss-earth-clouds.jpg`. Adaptations: blue key light, atmospheric edge shader,
  artistic orientation and Earth cloud blending. These are surface maps on
  geometry, not sky wallpaper. Verified/downloaded 2026-10-01.

## Editable Scenes

## Phengos Warm Preview v4

- Earth night and cloud maps: Solar System Scope / INOVE, NASA-derived imagery.
  Source: https://ftp.solarsystemscope.com/textures/
  Night: https://ftp.solarsystemscope.com/textures/download/8k_earth_nightmap.jpg
  Clouds: https://ftp.solarsystemscope.com/textures/download/8k_earth_clouds.jpg
  License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ .
  Local: `E:/LifeOS-Art/textures/sss-earth-night-8k.jpg` and
  `E:/LifeOS-Art/textures/sss-earth-clouds-8k.jpg`.
  Adaptations: warm city-emission tint, cloud attenuation, European orientation,
  and an artistic whitish horizon. Downloaded 2026-10-02. This is not a physical
  simulation or a claim to depict Los Angeles specifically.
- The two distant worlds use original procedural matte red/orange geology.
  Jupiter and Neptune photographs are NOT used by their v4 materials. Existing
  archived scenes may retain the separately credited v2 maps.
- Camera/planet placement begins with the user's live Blender setup. Distance
  and physical size were scaled together to preserve opening angular framing.

## Phengos Sunrise Study v5

- Natural rock height and roughness: Poly Haven, **Aerial Rocks 02**, Rob Tuytel.
  Source: https://polyhaven.com/a/aerial_rocks_02
  License: CC0, https://polyhaven.com/license . Commercial use and redistribution
  are allowed; credit retained for provenance despite not being required.
- Files: `E:/LifeOS-Art/phengos/textures/aerial_rocks_02_disp_4k.exr` and
  `E:/LifeOS-Art/phengos/textures/aerial_rocks_02_rough_2k.jpg`.
  Downloaded from URLs returned by `https://api.polyhaven.com/files/aerial_rocks_02`,
  verified against the API's MD5 checksums on 2026-10-02. Both packed into v5.
- Adaptation: triplanar height/bump and matte roughness on the existing fictional
  worlds. No moss-colored diffuse map, no imported real Solar System planet,
  no new add-on. Their red/orange palettes and authored geometry remain original.
- Atmosphere is a bounded volume with exponential density, Rayleigh scattering
  and weak forward aerosol scattering. Earth surface emits city lights only.
  A finite-distance white sun supplies the lighting; this is an artistic scene,
  not a scientifically scaled astronomical simulation.

## Scene Sources

## Phengos Natural Horizon Study v10

- High-detail settlement radiance: NASA Earth Observatory, Black Marble 2016
  grayscale maps, Suomi NPP VIIRS. Source page:
  https://science.nasa.gov/earth/earth-observatory/earth-at-night/maps/ .
- NASA Earth Observatory imagery by Joshua Stevens, using VIIRS data from Miguel
  Roman, NASA GSFC. NASA imagery usage guidance above applies; no endorsement.
- C1 northern 0..90E/0..90N tile (21600x21600, nominal 500 m source):
  https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/144000/144897/BlackMarble_2016_C1_gray.jpg
  Local: `E:/LifeOS-Art/phengos/textures/nasa-black-marble-C1-500m-gray.jpg`.
  SHA256: `95c448f32e5c42bd4017d1c0394a56a93b77abb449cc1666573495df00f89a58`.
- Deterministic geographic extraction: 2..40E, 35..62N, reduced from 9120x6480
  to 8192x5821. This retains much finer local city detail than an 8K full-world
  map without loading the full 21K tile into this 8 GB RAM PC's Blender process.
  It is not upscaled or AI-invented satellite imagery.
- Derived map: `E:/LifeOS-Art/phengos/textures/nasa-black-marble-regional-8k.png`.
  SHA256: `3787838723fb23ab5fadfa734564ebf1e2b9c44328c5ecdaf12a4fda4b8f3ed5`.
  Preparation: `scripts/blender/prepare_phengos_night_tile.py`.
  The shader maps the crop by geographic UV bounds, uses cubic sampling, applies
  a warm artistic tint and cloud attenuation, and retains the previously credited
  Solar System Scope global night map only outside the crop.
- NASA 13500x6750 grayscale global map also downloaded as a research alternative:
  https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/144000/144897/BlackMarble_2016_3km_gray.jpg .
  Local `nasa-black-marble-global-3km-gray.jpg` in the same E: texture directory.
  This alternative is NOT linked in the v10 material.
- Existing NASA day albedo, INOVE cloud maps and fictional planet textures remain
  as previously credited. No third-party full Earth model, new plugin, false NASA
  branding or new runtime dependency is introduced.

## Phengos Silver Horizon Study v11

- Fictional planet terrain: NASA Scientific Visualization Studio **CGI Moon Kit**,
  Ernie Wright, LRO/LROC and LOLA teams, https://svs.gsfc.nasa.gov/4720/ .
  These are terrain maps on Life OS-authored spheres, not imported Moon models.
  Recolored dark orange/red, with different UV regions and bounded shader bump.
  NASA imagery usage guidance applies; no endorsement implied.
- LROC 2019 color map, 4096x2048:
  https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_4k.tif .
  Local: `E:/LifeOS-Art/phengos/textures/nasa-lroc-color-4k.tif`.
  SHA256: `918649a7f8ed2f1329b2cd95bb0d25483befdcb60ae1a66db681a637cc21344f`.
- LOLA unsigned 16-bit elevation, 5760x2880:
  https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_16_uint.tif .
  Local: `E:/LifeOS-Art/phengos/textures/nasa-lola-height-16ppd.tif`.
  SHA256: `45a2b32d56e81ed30db07fead8abc842b249b6511219d9ca2c53f81bc2dc5d62`.
  Downloaded 2026-10-02; packed into v11. Elevation uses Non-Color sampling.
- Earth city/day/cloud assets remain as credited above. The silver/blue limb
  uses original, view-dependent native Blender shaders without a texture or
  volumetric noise. It is a camera-only optical art layer, not physical atmospheric
  scattering or a new light source. The previous volume remains in the scene,
  disabled in the selected silver mode for comparison and later refinement.

Life OS art scripts under `scripts/blender` author the editable scene and meshes.
Supplied concept references under `3D Objects` and `E:\Downloads` remain reference
material; they are not mislabeled as finished exported 3D assets.
