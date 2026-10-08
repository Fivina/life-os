# Phengos Milestone 1 Artwork

Foreground: `apps/web/public/art/phengos/horizon-v1.png`.
Generated with the built-in image_gen tool on 2026-10-01, then copied into the
repository. Actual output: 1672 x 941 RGBA, 1,398,959 bytes. This is not a 4K asset.
No image-generation API key or extra user plugin was required.

Starfield: existing `apps/web/public/art/system/deep-space-v1.png`, reused unchanged.
Foreground alpha reveals this separate layer. The camera-follow illusion moves
the foreground down by 115% and the oversized starfield down by 12%; foreground
opacity is never animated. No GLB is needed by the normal Phengos home.

## Generation Prompt

Use case: stylized-concept. Asset type: production foreground layer for a cinematic
personal-assistant app called Life OS. Generate a very wide landscape 16:9
high-resolution transparent PNG, ideally 3840x2160. Entire backdrop MUST be
genuinely transparent, including all space above the Earth. Main subject: a
photorealistic curved Earth NIGHT hemisphere rising from the bottom edge, with an
exquisite thin electric ice-blue atmospheric rim, detailed dark continents and
restrained warm amber city lights. The horizon apex is at 60 percent image height;
the globe fills the lower 40 percent and continues beyond the bottom and side
edges, NOT a complete floating globe. A subtle concentrated sunrise glint appears
at the center of the horizon, NOT a giant starburst. Two separate dark blue rim-lit
planets appear in the upper peripheral corners: a small planet clipped slightly at
far left at 23 percent image height, a larger planet partially clipped at far right
at 32 percent image height. Center upper half remains completely empty transparent
negative space for a live animated circle and title. Premium film-opening
astrophotography, realistic cloud detail, near-black hemispheres, crisp atmospheric
edges, no plastic surfaces. Constraints: transparent alpha outside Earth and the
two planets; NO starfield, NO nebula, NO black rectangle, NO text, NO lettering,
NO logos, NO UI, NO frames, NO diagram, NO watermark. This will be composited over
a separate deep-space star field. Keep the glow restrained and alpha feathered
naturally.

## Technique

### Blender Intro v1 (Superseded)

The normal home now uses `public/art/phengos/intro-v1.mp4` and matching
`opening-plate-v1.webp`, `horizon-plate-v1.webp`, `idle-plate-v1.webp`.
These were rendered with Blender 5.2.2 LTS / Eevee / AgX from the authored scene
`E:/LifeOS-Art/phengos/phengos-intro-v1.blend`. 1920x1080, 255 frames at 30 fps.
The MP4 is 842,661 bytes. WebP plates total 118,182 bytes at quality 95. Circle/text are in the opening film; poster plates exclude
them, allowing an interactive live actor after the film. No audio or provider calls.

The star depths and low-frequency cobalt space shader are authored in Blender,
not a NASA wallpaper. Existing Earth/Moon NASA-derived surface textures from
`E:/LifeOS-Art/textures` are used on actual sphere geometry, not as backgrounds.
Their earlier provenance remains in the spatial-art documentation. This is a visual
composition, not a scientific visualization or astronomical simulation.

Generated `deep-space-v2/v3/v4.png` are unused exploratory variants, not runtime
dependencies. v3 was rejected as too textured. v4 prompt (built-in image generation):
"Wide landscape 16:9 cinematic deep-space environment plate for Life OS Phengos.
Extremely restrained, low-texture composition. Approximately 80 percent uninterrupted
near-black ink navy negative space. Very sparse tiny cool-blue stars, most dim, no
large bright stars or lens flares. Only a whisper of smooth soft deep-cobalt
interstellar haze behind center-right, barely visible, diffuse not granular, not
cloudy clumps, no veins, no sharp dust detail. The feeling is vast quiet space,
clean photographic film contrast, not a busy space wallpaper. No nebula band,
no galaxies, no dense star fields, no gritty texture, no planets, no Earth,
no horizon, no text, no glowing orb, no UI, no bright center. A pure-white circle
will be added by code and must dominate. Maintain cool blue-black palette, no
purple, no neutral gray clouds, no teal. Seamless space across all edges."

### Runtime Motion

Motion for React supports spring and shared-layout animation. Core is MIT licensed.
Verified upstream: https://github.com/motiondivision/motion and
https://motion.dev/docs/react-layout-animations . Installed runtime: motion 13.4.6.
Existing React/Router/Query/domain service patterns remain unchanged.
Later card-to-circle transitions belong to the navigation/functionality milestones.

### Continuous Opening v2 (Superseded)

The current home uses `environment-v2.mp4` (1,127,760 bytes) with matching `opening-plate-v2.webp`,
`horizon-plate-v2.webp` and `idle-plate-v2.webp`. The rendered environment contains
no circle or lettering: React owns one continuously visible, clickable Phengos.
Its perspective uses the same 38mm lens, 36mm sensor, 0.43 world-unit radius,
5-second approach and 3.5-second rise as Blender. Quintic easing has zero endpoint
velocity and acceleration. Circle and camera share the exact same vertical track;
there is no relative bob or ascent-specific squash. The environment is rendered at 1920x1080, 60fps,
511 frames; this is not a measured runtime FPS claim.

In this archived version, `requestVideoFrameCallback` synchronizes CSS transforms with decoded media frames;
older browsers use an animation-frame playback clock. No React rerender per frame.
Natural completion holds the last decoded environment frame, instead of swapping
video/circle actors. Clicking Phengos cancels playback and enters the live view.
Opening is once per browser session (existing session key retained), with explicit
replay. Reduced-motion mode omits video. Missing/stalled media cannot block menus.

Authoring scene: `E:/LifeOS-Art/phengos/phengos-intro-v2.blend`.
Actual rendered snapshot: `E:/LifeOS-Art/phengos/phengos-intro-v2-user-framing.blend`.
The latter preserves the user's live Blender planet placement/sizes as inspected:
cobalt planet at (-17.82201767, -0.0265938, -15), diameter 5.2; banded planet at
(18.10551071, 5.93720388, -15), diameter 8.2. Camera remained at its normal start
(0,0,25), zero rotation, 38mm lens. Source script retains those placements.
Earth/cloud/city-light and planet texture credits: `SPATIAL_ASSET_SOURCES.md`.
All source images are packed in the saved .blend. Smooth space is an authored
shader with sparse star geometry, not a photographic wallpaper.

Idle return still uses the matching horizon plate and live Motion transforms;
it is not yet a reverse-rendered Blender camera track. Portrait wordmark spacing
is bounded independently of cover-cropped landscape scenery. Browser-based visual
and frame-rate verification remains pending after the earlier tool-policy block.

### Smooth Sky Opening v17 (Current)

The landing page uses the user-reviewed Blender v16 composition with the blue
clouds smoothed in a separate v17 scene at
`E:/LifeOS-Art/phengos/phengos-intro-v17-smooth-sky.blend`. The v16 cloud plate
was projected across a wide dome with too little filtering, causing visible
coarse blue patches. v17 applies a Gaussian filter to that cloud material, then
bakes the result into a 4096×2048 scene-linear texture for one lookup per ray.
Stars, the atmospheric horizon, title, planets, character path, and compositor
glow remain separately authored. The original v16 scene is preserved.

The web scene is the native `<video>` element playing
`public/art/phengos/environment-v17-60.mp4`. Its matching first-frame poster,
last-frame circle-free idle plate, and circle-free horizon rest plate live beside
it. The film owns the title and circle during the 8.5-second introduction; the
live clickable CSS/Motion circle takes over at its final centered frame. Returning
to the horizon moves that live circle toward the O position over the matching
rest plate. The page uses no runtime WebGL, whole-object GPU rendering, canvas
loop, or per-frame React state updates. Browser playback and compositing remain
subject to the device's actual capacity.

The final export is 1280×720, 60 fps, 511 frames, silent H.264. This describes
the encoded asset, not a universal 60 FPS playback guarantee. More detailed
scene, fidelity, and decoded-frame checks are in
`E:/LifeOS-Art/phengos/smooth-sky-v17-notes.md` and its QA JSON files.
