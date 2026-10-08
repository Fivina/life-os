# Spatial Visual Review

Reviewed 2026-10-01. Scope: independent comparison of supplied local images and
`SPATIAL_ART_DIRECTION_PLAN.md`; no implementation or browser access.

**BROWSER GATE: UNVERIFIED.** Browser screenshots are unavailable and browser
attachment is explicitly blocked. No browser tools or workaround were used.
Nothing here establishes browser parity, exported material fidelity, mobile
framing, runtime behavior, or performance. A valid render or GLB export does not
demonstrate visual fidelity.

## Evidence Inspected

All images below were actually opened with `view_image`:

- Main reference: `E:/Downloads/ChatGPT Image Sep 30, 2026, 05_35_03 AM-1.png`.
- Current whole frame: `E:/LifeOS-Art/system/system-art-v20001.png`.
- Fitness: `D:/Life OS/3D Objects/Fitness/fitness_orbit_barbell_catalog (1).png`
  and `depth_2_reference.png` in the same directory.
- Learning: `D:/Life OS/3D Objects/Neural Bloom/learning_neural_bloom_catalog (1).png`
  and `depth_2_reference.png` in the same directory.
- Home: `D:/Life OS/3D Objects/Home/home_supply_core_catalog (1).png`
  and `depth_2_reference.png` in the same directory.
- Additional Self Core evidence:
  `D:/Life OS/3D Objects/Self Core/self_core_star_catalog.png`.
- Newly available renders: `E:/LifeOS-Art/system/selfcore-closeup.png`,
  `learning-closeup.png`, `home-closeup.png`, and `fitness-closeup.png`
  (same directory).

Evidence caveat: the inspected Neural Bloom and Home depth-2 images both depict
the Fitness system, with Training/Nutrition/Recovery/Body labels. They are not
independent close-up evidence for Learning or Home. Their catalogs and the main
reference support those comparisons instead. Catalog state captions are visual
reference content, not authorization to introduce product state semantics.

Fitness's closeup arrived before completion and was inspected. The four closeups
supplement the whole-frame evidence; hidden geometry and actual shader settings
remain unresolved. The remaining render queue was not awaited.
The user reports reduced bump textures, revised Earth orientation, and smoother
Home faces in the source and identifies this full frame as the revised render.
The whole frame was reopened after that update. Recommendations concern what is
visible in it; they do not request restoration of the earlier bump settings.

## Judgment

The current image is a legible system study with distinct object silhouettes,
a useful galaxy background, and an already recognizable equatorial Fitness
assembly. It has not yet reached the reference's cinematic finish. The reference
combines selective bright edges, textured shadowed surfaces, localized luminous
atmosphere, and foreground occlusion. The current frame separates objects cleanly
but often presents them as isolated models arranged over a starfield.

Do preserve the progress visible here: Home is now a polygon-panel shell rather
than the plan's earlier cube-patch description; Life has recognizable geography;
Fitness's shaft crosses the planet rather than sitting below it. Repeating those
old diagnoses would misdescribe this image. The remaining material problem is
how surfaces respond to light and how much authored structure survives at this
scale, not simply whether a texture or mesh exists.

## Five Ordered Changes

### 1. Establish a shared light hierarchy and three depth layers

**Visual evidence:** In the main reference, the central star has a luminous blue
envelope that links it to nearby space; Home has a warm, textured lit hemisphere;
Calendar and Fitness retain dark faces with bright selective rims. The large
lower-left asteroid belt and lower-right cropped body overlap the scene and
establish a foreground. In the current frame, Learning's pale top cap and Home's
broad silver/gold highlights compete with the small central emitter. Broad blue
orbit ellipses enclose a large empty area, while the rocks occupy only the bottom
edge. The diagonal galaxy provides atmosphere but does not by itself establish
the objects' relative depth. Planet sizes suggest depth; occlusion supports it
only weakly.

**Likely causes, inferred:** Light/exposure balance favors broad surface
highlights over the core's surrounding light; orbit curves are more diagrammatic
than spatial; foreground placement provides little overlap. Camera-space
placement and local effects may be insufficiently coordinated. The render alone
does not establish the actual rig or world-space distances.

**Next pass:** Author one dominant key direction with a restrained fill and
selective local accents. Reduce the pale Learning cap, preserve dark hemispheres,
and make Self Core's immediate surroundings the main luminous region. Vary orbit
visibility with depth and brightness rather than drawing equally legible complete
ellipses. Bring a limited foreground rock group into deliberate silhouette overlap
and keep the distant galaxy subordinate. Judge a fixed-camera thumbnail and a
surface-only version: the core should lead attention and three spatial layers
should remain legible before bloom. Do not brighten every planet to achieve this.

### 2. Give Self Core stellar structure and an intentional energy envelope

**Visual evidence:** The current center is a pale, finely mottled ball surrounded
by thin cyan loops, with a dense knot of crossings to its right and several faint
loops extending down. Some surface texture is visible, so calling it a completely
featureless clipped disk would overstate the evidence. Nevertheless, its tonal
range is compressed and the loops read as wire curves. The main reference and
Self Core catalog retain blue interior structure, a bright irregular photosphere,
localized flares, and filaments with varied brightness and thickness.
The Self Core closeup confirms cloudy blue-white mottling and some differences
in loop brightness, but no convincing bright limb/corona separation. Thin loops
remain individually traceable curves rather than a luminous energy envelope.

**Likely causes, inferred:** Relatively uniform emissive color and curve profiles,
insufficient separation between photosphere and corona, and a projected curve
arrangement whose crossings dominate one side.

**Next pass:** Retain the blue-white stellar identity and orbit language, but
introduce darker blue channels in the photosphere, limited brilliant hotspots,
and an irregular bright limb. Compose fewer dominant flowing filaments with
fine secondary strands; vary width, intensity, and foreground/background
occlusion. Add a source-bound halo that falls away quickly. Check that stellar
surface structure survives the final exposure and that the halo draws the eye
before the loop knot does. A modest redesign is appropriate; a larger white ball
with stronger blanket bloom is not sufficient.

### 3. Finish Fitness as the material and craftsmanship anchor

**Visual evidence:** In the lower-right of the current image, the shaft crosses
the sphere near its middle and connects the plate assemblies. That basic
relationship already works. Compared with the catalog and Fitness depth-2 image,
the plate faces are very dark, narrow cyan edges carry much of their readability,
and the sphere's upper blue/brown mottling has less apparent relief than the
reference's craggy, sharply lit surface. The large outer cyan ellipse reads more
strongly than the plate-face machining. Perspective can explain different apparent
plate widths; this image does not prove an asymmetrical model.
The closeup confirms plate-stack thickness and bright edge bands. The left
plate's visible face is a broad, largely featureless dark disk; the right stack
is almost black apart from its rims. Outer shaft ends and a right collar-like
transition are visible. The sphere already has relief, including a broad uneven
upper silhouette and softly ridged blue/brown surfaces. It lacks the reference's
more varied mineral scales and distinct material response; it does not simply
lack bump. The bright enclosing ellipse remains visually louder than face detail.

**Likely causes, inferred:** Insufficient reflected/key light on metal faces,
weak roughness contrast between shaft/collars/plates, terrain detail that appears
mostly tonal at system scale, and an overly prominent orbit relative to hardware.
The near plate could have overly simple face geometry or lighting that conceals
its detailing; the image establishes the visual absence, not which cause applies.

**Next pass:** Preserve the equatorial assembly. Use a grazing highlight to reveal
plate thickness, face recesses, collar transitions, and bevels; distinguish polished
shaft metal from satin plate faces and rough mineral terrain. Keep cyan channels
narrow and selective. Make the planetary relief respond to the same light rather
than relying on color mottling; use layered mineral scales and roughness variation
instead of indiscriminately raising bump strength. Give the near plate a readable
hub/recess and machined face transitions where the present face is visually blank.
Reduce the enclosing orbit's prominence if it
outlines the object more strongly than its own form. Compare the closeup and the
unchanged system camera: machining must be credible nearby and the barbell must
remain recognizable at small size without emission doing all the work.

### 4. Turn Learning's front-facing branch fan into a volume

**Visual evidence:** The current upper-center object shows a pale trunk splitting
into many almost straight, similar-width diagonals, all readily visible on the
front of the sphere. The bright top cap dominates the branching. In the main
reference the curved trunk has roots and branching levels; the Neural Bloom
catalog develops sweeping branches, varied twig scales, luminous endpoint nodes,
and strands that wrap around or extend beyond the body's edge. The current image
does not show convincing near/far overlap within that body.
The Learning closeup confirms that small pale node beads already exist and the
branches have some curvature. They still form a narrow fan of largely uniform
strokes over an opaque-looking rocky sphere; the broad white upper highlight
washes across branch tips. The issue is branch hierarchy and projected volume,
not the complete absence of nodes or surface texture.

**Likely causes, inferred:** A shallow projected branch layout, limited taper
and curvature, insufficient depth occlusion, and shell lighting that washes out
the upper canopy. Actual branch geometry could be three-dimensional while still
producing this flat result from the reviewed camera.

**Next pass:** Compose a curved trunk and a few unequal primary branches, then
taper into fine twigs and sparse endpoint nodes. Place readable branch groups at
different depths; hide portions behind the trunk and shell, attenuate distant
branches, and let a few wrap toward the silhouette. Keep the luminous organic
identity without copying every catalog strand. Verify overlap and depth from
the established view and a nearby oblique closeup; merely adding more front-facing
lines or glow will intensify the emblem effect.

### 5. Replace Home's uniform panel pattern with fitted, materially distinct modules

**Visual evidence:** The current upper-right Home is a clean shell of similarly
sized polygon faces, narrow regular seams, and broad smooth gold/silver highlights.
It reads as a faceted manufactured ball. The main reference uses irregular
interlocking plates with broken edges, substantial dark recesses, and uneven
surface relief. The Home catalog offers another valid interpretation: thick,
rounded fitted modules, recessed hardware, restrained wear, and varied ceramic/
metal finishes. Those references differ in shape, but both give the shell a
crafted construction that the regular current tiling lacks.
The Home closeup confirms actual raised plate thickness, sharp beveled edges,
recessed gaps, and fine surface grain. These are present, not missing. The fairly
uniform large polygon faces and repeated edge construction still make it read
as a regular faceted shell rather than an assembly of individually fitted modules.

**Likely causes, inferred:** Repeated panel topology and depth, uniform edge
treatment, limited visible understructure, and insufficiently differentiated
module construction. The closeup does show varying reflections and surface grain;
adding generic noise is unlikely to solve the larger pattern problem.

**Next pass:** Keep Home's warm modular identity while varying a limited family
of plate shapes and sizes. Establish visible thickness, recessed dark joints,
occasional exposed understructure, and purposeful bevels. Separate warm metal
frames from a few ceramic module faces with distinct specular widths; add small
fasteners or restrained wear only where they survive the intended scale. Do not
copy all catalog icons or invent new states. At system scale, joints and plate
depth should remain readable beneath a selective warm highlight; in closeup,
modules should look fitted rather than like flat colored facets.

## Constraints And Acceptance

Palette remains creative. Blue-white, violet, warm metal, living greens, and cyan
already distinguish identities; exact hue matching is unnecessary. Attention red
is an optional fallback, not a required fix. Any later state treatment must also
use luminance, contrast, shape, and labels, and preserve existing product semantics.
Slight identity-preserving object redesign is allowed.

The next useful evidence is a fixed-camera whole-frame comparison and matching
closeups after the recommended pass. Self Core, Learning, Home, and Fitness
closeups are now inspected. Surface detail, silhouette, shadow shape, and depth
must survive restrained effects.
Labels/UI are absent from the reviewed render, so their legibility and safe regions
are not evaluated. No numeric fidelity score is warranted. The static artwork
gate remains unmet on this evidence; the browser gate remains **UNVERIFIED** even
if the next authored render improves or its GLB exports successfully.
