# Local Blender Art Workflow

## Installed connection

- Blender: `E:\Blender\blender.exe` (5.2.2 LTS).
- MIT upstream: https://github.com/ahujasid/mcp-for-blender.
- Isolated bridge: `E:\LifeOS-Tools\blender-mcp-venv`.
- Published package pinned to `mcp-for-blender==2.1.3`; dependencies validated with `pip check`.
- Source inspected at commit `60d2a31b4632a7bc178f3dd636f7e68dfb5c8ae4`.
- Add-on: `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\blender_mcp.py`.
- Codex configuration: project `.codex/config.toml`. Existing model/agent/global settings unchanged.
- Socket: `127.0.0.1:9876`, starts when Blender opens.

The bridge is stdio MCP; Codex starts it on demand. Do not run a standalone
long-lived stdio server without a client. Restart/reload Codex's MCP servers
to expose the configured tools in a new tool session. The smoke-test client
can exercise the actual MCP protocol before that restart.

## Security boundary

Telemetry consent is false and telemetry-disable environment flags are set.
Paid generators/external asset tools are not in the Codex tool allowlist.
Safe mode is enabled and a prohibited `os` import was tested and rejected.
No API key or paid service is required for local modeling.
The add-on's raw socket is NOT authenticated or a full security sandbox.
Local processes can access it; never bind it publicly or add a port-forward.
Safe mode guards scripts sent through the MCP server, not the whole PC.
Close Blender to stop the socket. Disable `[mcp_servers.blender]` to remove
Codex access without removing any artwork.

## Pilot

Editable scene: `E:\LifeOS-Art\fitness\fitness-art-study.blend`.
Rendered preview: `E:\LifeOS-Art\fitness\fitness-art-study.png0001.png`.
Repeatable source: `scripts/blender/fitness_art_study.py`.
Independent named plates, axis, planet, moons, orbit curves and materials.
The original startup scene is preserved; the pilot uses a separate scene.
This is an art-direction study, NOT a deployed replacement or a proven 60 FPS scene.
No backend or application runtime files changed.

```powershell
& '.\scripts\blender\launch.ps1'
& 'E:\LifeOS-Tools\blender-mcp-venv\Scripts\python.exe' '.\scripts\blender\mcp_client.py' inspect --prompt 'Inspect the Blender scene'
& 'E:\LifeOS-Tools\blender-mcp-venv\Scripts\python.exe' '.\scripts\blender\mcp_client.py' execute '.\scripts\blender\fitness_art_study.py' --prompt 'Create the Fitness art study'
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\fitness\fitness-art-study.blend' --scene LifeOS_Fitness_ArtStudy --render-frame 1
```

Creation deliberately makes a NEW scene on every invocation. Do not rerun it
to modify an existing study; use targeted MCP edits and save a revision.
The one-time refinement script records the first lighting/shaft correction.

## Full System Composition Study

Editable composition: `E:\LifeOS-Art\system\system-composition.blend`.
Current render: `E:\LifeOS-Art\system\system-cinematic-study0001.png`.
Scene: `LifeOS_System_Composition`. The Fitness pilot remains in its separate scene.
The full study includes all five domain roots, Self Core, distant stars and dust,
foreground fragments, and a shared camera/lighting rig. It is not the live hub.

Sources: `scripts/blender/art_primitives.py`, `system_composition.py`, and
`refine_system_composition.py`. Creation requires the pilot's `Fitness_Asset`
collection already loaded, and creates a new scene. Run the refinement against
the existing system scene; it does not regenerate the scene.

```powershell
& 'E:\LifeOS-Tools\blender-mcp-venv\Scripts\python.exe' '.\scripts\blender\mcp_client.py' execute '.\scripts\blender\system_composition.py' --library '.\scripts\blender\art_primitives.py' --prompt 'Create the complete system composition'
& 'E:\LifeOS-Tools\blender-mcp-venv\Scripts\python.exe' '.\scripts\blender\mcp_client.py' execute '.\scripts\blender\refine_system_composition.py' --library '.\scripts\blender\art_primitives.py' --prompt 'Refine the cinematic lighting study'
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\system\system-composition.blend' --scene LifeOS_System_Composition --render-frame 1
```

Motion timing is proposed in `docs/SPATIAL_MOTION_STORYBOARD.md`, not implemented.
Browser materials, baked textures, camera framing, accessibility and performance
still require verification; a Blender render does not prove browser fidelity or 60 FPS.

## Browser Quality Gate

Review the visual direction with the user. Bake procedural surface channels
to textures before GLB export; Blender node shaders and compositor glow do
not automatically translate into web materials. Keep distinct attention accents,
orbit motion and atmosphere as runtime layers. Integrate only an isolated
browser preview first, measure desktop/mobile framing and frame cost, then
replace a production object after visual approval.

## Authored V2 And Portable Export

V2 is a separate generated scene: `LifeOS_System_Composition_V2`, source
`E:\LifeOS-Art\system\system-art-v2.blend`. Named roots: SelfCore, Calendar,
Learning, Home, Life, Fitness, Scenery. Stage lights and the bitmap backplate are
not export geometry. Rebuilding this generated V2 overwrites its generated source;
keep hand-authored variants separately. Original V1/pilot files are preserved.

```powershell
& 'E:\Blender\blender.exe' --background --factory-startup --python '.\scripts\blender\system_art_v2.py'
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\system\system-art-v2.blend' --scene LifeOS_System_Composition_V2 --threads 4 --render-frame 1
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\system\system-art-v2.blend' --threads 4 --python-exit-code 1 --python '.\scripts\blender\render_art_view.py' -- --target all
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\system\system-art-v34.blend' --threads 4 --python-exit-code 1 --python '.\scripts\blender\export_system_art.py' -- --output 'D:\Life OS\apps\web\public\art\system\life-os-system-v34.glb' --textures 'E:\LifeOS-Art\system\baked-v34' --size 1024 --threads 4
```

The export script evaluates/converts geometry in a disposable scene, checks UVs,
bakes linked procedural PBR channels, batches compatible objects within their
named root, retains explicit runtime atmosphere extras, exports the camera,
validates the GLB and atomically replaces the output. It does not save the blend.
Report is beside the GLB. Close-up rendering also never saves over the source.

Oversized source maps are copied/capped at 2048px in the disposable export scene;
the original image files and saved blend are untouched. The report records source
and portable dimensions. Physical transmission/IOR/specular and transparency are
validated as well as texture presence. Do not rebuild the source while an export
is running: the source-hash guard will reject a changed scene rather than publish
an ambiguous asset.

Separate portrait poses/scales are authored in `art_composition.py` and stored in
root extras in glTF Y-up coordinates. The preview applies these only to tall system
views and restores desktop transforms on resize. Repeatable diagnostics:

```powershell
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\system\system-art-v2.blend' --python-exit-code 1 --python '.\scripts\blender\render_art_composition.py' -- --composition portrait --output 'E:\LifeOS-Art\system\portrait.png'
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\system\system-art-v2.blend' --python-exit-code 1 --python '.\scripts\blender\render_art_composition.py' -- --look untextured --output 'E:\LifeOS-Art\system\untextured.png'
& 'E:\Blender\blender.exe' --background 'E:\LifeOS-Art\system\system-art-v2.blend' --python-exit-code 1 --python '.\scripts\blender\render_art_composition.py' -- --look clay --output 'E:\LifeOS-Art\system\clay.png'
```

Untextured proof preserves source emission/material identity and actual filament
geometry while removing maps, backplate, cloud/scattering sheets, camera optics and
bloom. Label-bounds exclusion is not diagnostic visibility. V33 corrects that
conflation; older controls hid the outer strands. Neutral clay evaluates body placement;
it must not be substituted for the authored emission hierarchy proof.

`render_art_view.py` also supports disposable Learning diagnostics:
`--hide-light-sources transmission`, `--hide-light-sources all`, and
`--learning-material-probe`. These distinguish light-source reflections from
material/refraction problems. They never save the source. A diagnostic with lights
hidden is not the accepted lighting rig or proof of browser rendering behavior.
V30 independently stages the near frame, receding belt and orbit tracks as direct
boolean-tagged children of Scenery. Export consolidation retains those parents;
the preview applies their exported portrait poses and restores baseline transforms
without accumulation. Older untagged assets retain their whole-root staging.
Blender proof rendering replays each saved source's metadata, not today's constants.
Repeatable transform/reset and legacy behavior are covered by focused tests.

V22 source-power compensation is authored in `art_composition.py`, exported as
`art_portrait_source_power_scale` on SelfCore and applied only to portrait system
staging. Directional material limbs export Y-up `art_rim_direction` plus bounded
`art_rim_floor`; the runtime transforms that direction into view space. Export
validation checks these extras against the authored values rather than assuming
the shader graph survives glTF. Preview lights use explicit linear RGB matching
Blender, but power conversion remains approximate until browser comparison is
available. Passing injection/unit tests does not prove WebGL shader execution.

Asset provenance: `docs/SPATIAL_ASSET_SOURCES.md`. NASA geography is not generated
terrain; the generated distant environment is not a substitute for 3D objects.
Development-only preview: `http://127.0.0.1:5173/_dev/system-art?depth=system`.
Current browser gate is UNVERIFIED: browser tool security policy blocked access.
No runtime/performance evidence should be inferred from successful export/build.

## Depth 1 Scenery And Optics

`scenery_art_geometry.py` authors actual perspective positions against the fixed
desktop camera: a near framing band and a receding middle/far belt. Root metadata
documents depth staging; the bitmap is a non-geometry distant layer. Rocks reuse
shape/detail meshes and consolidate by material on export. Per-rock annotations
must not defeat batching. Current V34 has four Scenery batches (19 near meshes,
226 receding rocks/chips, 90 dust flecks, 8 paths). Its 168 chips share the existing
belt material, adding no draws/maps but increasing per-object bake time. The extra
belt material originally introduced in V29 increases the
decoded texture estimate from 144 to 160 MiB including mipmaps; not measured GPU use.

The source camera focuses on Core with a shallow aperture. The distant image is
composited after camera optics using render-size crop, matching the preview's
separate bitmap placement conceptually. Closeup, clay and untextured diagnostics
disable optics; untextured also removes background and bloom. Foreground optics
must not be used to claim materials/depth work without those controls.

Camera extras `art_camera_optics_version=1`, `art_depth_focus_range` and
`art_depth_bokeh_scale` form a bounded renderer-specific contract. The DEV preview
uses the installed postprocessing DepthOfField focused on the current Core bounds,
half-resolution effects and reduced portrait bokeh. Invalid/missing metadata means
no depth effect. Blender aperture/runtime bokeh are not numerical equivalents;
actual browser appearance/performance remains unverified.

V33 corrects shadowing by the visible source proxy: the analytic Core light is inside
its photosphere, so that luminous mesh and the scattering sheet do not cast shadows
in Blender. The preview currently enables no mesh shadows; this does not prove
shadow/refraction parity. Core exports version-1 `art_source_power_scale` (2.5 for
6,250 W relative to 2,500 W); the preview applies it to its existing approximate
conversion, plus independent portrait compensation. Invalid/missing values retain
baseline power. The bounded helper accepts finite 0.1..4 only; nine focused tests
cover this and legacy behavior. No photometric calibration claim.

V35 introduces version-1 `art_source_color_linear` metadata on SelfCore, copied
from the actual Blender light color. V37 retains RGB (0.56, 0.76, 1), while power
remains 6,250 W. The preview's `artSourceColor.ts` accepts exactly three finite
0..1 components with at least one positive component, returns a fresh tuple and
passes it to Three's `setRGB` with `LinearSRGBColorSpace`. Missing/invalid metadata
preserves the older linear color (0.22, 0.62, 1); do not double-decode it as sRGB.
Sixteen focused tests passed, including malformed, sparse, nonfinite and legacy
inputs. This proves the bounded contract, not actual browser rendering/parity.
The V35/V36 near-end belt distributions were not published: their clump remained.
V37 applies staggered depth and a dominant/minor size hierarchy across both entry
clusters, retaining 58 rocks, 168 chips, 90 dust flecks and the accepted near layer.

`render_art_composition.py --width 400` renders a real small landscape proof;
`--composition portrait --width 300` preserves its authored tall aspect. These are
Blender renders, not browser screenshots or resized evidence of runtime quality.

Publish new revisions to a versioned GLB/report pair, validate, then switch the DEV
preview URL. V28 used this path after Windows denied replacing the older live file;
the V23 file remained intact. Do not change ACLs or interrupt the user's server to
overwrite an in-use asset. Freeze the exact source before export and compare its
hash with the report. See `SPATIAL_ART_CHECKPOINT.md` for actual current results.
