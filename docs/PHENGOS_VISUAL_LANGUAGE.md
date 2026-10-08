# Phengos visual language — PC implementation notes

Created 2026-10-03 for the desktop redesign. The authoritative, durable visual-language source is now `PHENGOS_UNIVERSAL_DESIGN_CONTRACT.md`, including its dated amendments. Read it alongside the latest images in `New Design/Design`, `PHENGOS_ROADMAP.md`, `PHENGOS_FEATURE_INVENTORY.md`, and `PHENGOS_PREMIUM_IMPLEMENTATION_TASKS.md`. This file records implementation notes; the catalog is visual reference and the live routes and services remain implementation truth.

## Experience

Phengos is a curious, energetic blue-white circle. It introduces, guides and acknowledges transitions. It settles into a small, calm presence while the user reads, edits or completes work. The PC experience is a sequence of spatial layers, not independent page themes:

`Blender introduction → idle circle → general surface/dashboard → domain → subcomponent → working view → return`.

At every depth, show where the user is, what matters now, what they can do next and how to go back. A card must have a reason to appear and a clear destination or action. The dashboard combines stable at-a-glance structure with contextual cards from real saved data. Layout is intentionally asymmetric: size, placement and imagery follow relevance and reading order, not a uniform widget grid.

## Foundations

The v17 Blender film supplies the introduction. A still derived from its space scene, without the title letters, supplies the routed workspace background at `apps/web/public/art/phengos/workspace-environment-v17.png`. The live interface uses HTML/CSS/Motion; no home-scene WebGL. The starfield and planetary horizon are the primary visual surface, visible in the open areas around cards without a page-wide dark overlay. Glow belongs mainly to Phengos, selected controls and meaningful card edges. Major workspace frames use dark blue glass; ordinary information cards and repeated items use deeper near-black glass. The sidebar belongs to the same dark material family. Every pane has a fine bright upper edge, controlled contour and enough transparency to reveal the scene. Ordinary event blocks and data widgets remain dark with color at their contour; Needs Attention uses translucent red glass and PHÉNGOS suggestions use translucent blue glass. A small blur belongs on the large panes; dense repeated rows remain unblurred to limit rendering cost. The same rules cover the full routed page, including older tools and forms below a new overview.

Shared color and motion tokens live in `apps/web/src/features/phengos/phengosTheme.css`. Frozen primary accents: Overview/Self `#60A5FA`, Home/Kitchen/Shopping/Household `#3B82F6`, Fitness/Training/Nutrition `#06B6D4`, Life `#22C55E`, Calendar `#F59E0B`, Learning `#A855F7`; red `#EF4444` is reserved for actual attention/error. The universal sidebar is a narrow floating capsule with a separate identifier and orb above it, open space at the left and bottom, and no full-height slab. Its quiet blue structural contour gives way to the active page accent on the selected segment. There is no continuous top or bottom chrome bar. A card or event retains its own source-domain accent even in a mixed workspace. Nutrition keeps cyan even though its existing route is under Kitchen. Use accent on edges, iconography and restrained highlights, not a neon fill. Do not create another domain color map or stylesheet of near-duplicate tokens.

Typography has three levels: quiet uppercase wayfinding, readable human headings, then compact labels/details. Avoid wide letter spacing in dense data. Controls have a visible 44 px target and a clear focus ring. Text and action labels state the user's goal, not internal service terms.

## Layer composition

| Layer | Composition | Circle | Primary interaction |
| --- | --- | --- | --- |
| Idle | Film endpoint/sky plate and circle only | Large, soft breath | Enter workspace |
| General surface | Full viewport, compact domain rail, greeting/prompt, stable overview and contextual cards | Above the content, expressive entry then still | Choose a card or domain |
| Domain | Same full viewport shell/rail, domain identity, component choices, relevant overview | Smaller, calm guide | Choose subcomponent/workspace |
| Subcomponent | Breadcrumb, back path, scoped cards/actions | Small, persistent | Inspect and choose action |
| Work view | Full existing controls and data; no feature loss | Smallest, quiet | Complete real task and return |

The initial film ends with only the circle. Entering the workspace transforms that moment into the interface. Do not show a greeting or dashboard over the film endpoint. On a direct routed page, preserve the same navigation language without replaying the film or discarding drafts.

## Cards

Card anatomy: source/context cue, meaningful title, concise detail, appropriate imagery or icon, action, state feedback. A near-term fixture can use two real crests; a planned meal can show food when an approved image exists; a shopping card prioritizes list items and a direct next step. Food images are deferred to the planned backend utility; the Kitchen page uses a restrained code-native plate motif until then. Do not add generic stock visuals merely to fill space. Use a compact, regular or wide footprint according to content and priority. Related cards align along a visual rhythm but do not become identical tiles.

Static overview and adaptive cards must coexist. Adaptive cards may enter or reorder when source data changes. Show honest loading, empty, stale and error states. A card claiming saved, done or approved must reflect the canonical response. Development scenarios are clearly labeled and cannot appear as production user data. Card backends are owned in a separate session; frontend view models and adapters connect existing canonical APIs.

## Motion and interaction

- Entrance: circle anticipates, the surface unfolds, then content settles. A selected domain changes depth and the chosen element leads the eye into the next layer. Use small translation, scale and opacity with spring-like easing; keep reading content still.
- Card changes: a card materializes from relevance, not from a perpetual animation. Reordering uses transform-based layout motion. Dismiss and completion visibly resolve and leave space for the remaining cards.
- Hover/press: short, tactile response. Never require hover to discover a primary action. Avoid multiple simultaneous pulses and exaggerated glow.
- Typical UI transitions should resolve in roughly 180–500 ms; the authored intro follows its own 8.5 second cinematic timing. These values are starting points to tune against actual desktop recordings, not performance claims.
- Respect reduced motion: skip ornamental travel and keep information/actions equivalent. Pause breathing when hidden or while focused work is active. No fake thinking indicator.

## Navigation, utility and preservation

`phengosFeatures.ts` is the canonical list of 21 destinations. `AppShell` owns routed navigation, Back, breadcrumbs, skip link, connection/push status and the persistent small circle. Extend these structures; do not create another router or menu source of truth. A domain card should link to an existing route/anchor until that feature's layered view is migrated. Keep current forms, tables, editing, history and settings controls reachable. Keep normal browser history, deep links and keyboard behavior.

The first domain migrations should be Kitchen/Shopping/Meal, Fitness/Training, Calendar/Daily List and Assistant/Review. Extract shared visual components after at least two real domains prove the pattern. Plan/strategy proposals and assistant action proposals have different backend mutation contracts; the UI must only show an Adjust action where a real edit path exists or provide a route to the native workflow/conversation.

## Review gate for every task

Show PC stills and a complete interaction recording: idle entry, dashboard, domain, subcomponent, routed work and return. Compare against the relevant catalog sheets at a representative wide and laptop viewport. Check legibility, keyboard/focus, reduced motion, truthful data, no lost draft or route, and no missing feature. Measure actual browser frame cadence before claiming 60 FPS. A passing build alone does not establish visual acceptance.
