# PHÉNGOS floating rail review — 2026-10-04

## Reference and correction

The current desktop baseline is `New Design/Design/2.png`, with `3.png` isolating the sidebar, `4.png` isolating its contour, `5.png` for Kitchen glass cards, and `download.png` for domain color identity. The user rejected the former full-height 112px strip and continuous top/bottom chrome.

| Element | Previous live state | Current implementation |
| --- | --- | --- |
| Sidebar shape | Continuous strip attached to the viewport | 80px floating navigation capsule at desktop sizes, 12px from the left and 24px above the bottom; LIFE OS identifier and orb sit separately above it. A separate angular contour runs just to its right, following the bend in `Design/4.png`. |
| Domain state | Thin generic blue side line | Subdued blue-black capsule frame, a short upper contour in the current domain accent, and an accent-colored selected row. The detached line blends the domain accent into the structural blue. |
| Home duplication | Full Overview tile above Home | Overview remains reachable through the orb; Home remains the domain entry. |
| Top and bottom chrome | Full-width Home bars and routed header fill | Home chrome is reduced to a floating close control. Replay, horizon and idle controls occupy the open upper-right area; no control covers the card row. The decorative full-width footer panel was removed, while assistant entry remains in the prompt, contextual card and navigation. Routed header has no painted bar; Back, history and account controls remain available. |
| Card material | Flat navy panels | High-opacity almost-black glass, faint inner reflection, stronger lit contour and depth shadow. Applied to Home cards, Calendar panels, Kitchen panels and preserved routed content bands. |
| Date/status readout | Calendar used plain text in open sky | Calendar and Kitchen now use a small, independent dark-glass date card above their contextual panels, matching the catalog's hierarchy without recreating a top bar. |

## Verification

- Inspected live Home, Calendar and Kitchen at laptop and 1440×900 desktop viewports. The floating capsule and dark glass render with real data. Captures: `PHENGOS_HOME_NO_BARS_2026-10-04.png`, `PHENGOS_CALENDAR_FLOATING_RAIL_2026-10-04.png`, and `PHENGOS_KITCHEN_FLOATING_RAIL_2026-10-04.png`.
- Rechecked the refined contour in the local browser at 1280×720 on Home and Calendar. Captures: `PHENGOS_HOME_CONTOUR_2026-10-04.jpg` and `PHENGOS_CALENDAR_CONTOUR_2026-10-04.jpg`. The capsule remains 80px wide, starts 103px from the top, ends 24px above the viewport bottom, and the detached line appears without horizontal overflow. The earlier 1440×900 captures precede this contour refinement; the height-responsive Home card rule still needs a live 1440×900 visual pass.
- Checked the Calendar and Kitchen date cards at 1280×720; both remain separate glass objects and the routed pages have no horizontal overflow. Kitchen capture: `PHENGOS_KITCHEN_DATE_GLASS_2026-10-04.jpg`.
- TypeScript and the production build passed. A second production build after the contour refinement also passed (2279 modules, 35.13s). The final Home test pass has 14/14 passing tests; an earlier combined Home/navigation run had a single transient near-term commitment timeout, and that test passed in isolation. The existing large main-chunk warning remains.
- The circle's appearance, food photography, voice mode and existing domain data were not redesigned. Visual acceptance and measured frame cadence remain open.

## Shared glass correction after user feedback

The sidebar is now made from the same near-black translucent material as the cards. The shared tokens in `apps/web/src/features/phengos/phengosTheme.css` give the scene a faint read-through (roughly 80% opaque at the top and 88% at the bottom), with a soft blur and restrained inner highlight. The darker underlying color keeps text legible; the current domain accent stays at the contour and selected row. The detached angular line remains separate from the capsule.

Applied the material to Home foundation/context/utility cards; Calendar panels, event blocks and date card; Kitchen panels, date card and smaller meal/action tiles; routed `content-band` and nested stat/utility cards across Fitness, Assistant, Settings and other existing feature pages. Repeated rows use translucent fill without individual blur to keep scrolling lighter. Red attention borders remain data driven. No feature component or route was removed.

Live desktop checks at 1280×720 verified computed transparency/blur and no horizontal overflow on Home, Calendar, Kitchen, Fitness, Assistant and Settings. A current Home capture is `PHENGOS_SHARED_GLASS_HOME_2026-10-04.jpg`. The production Vite build passed after the material changes (2279 modules); it retains the existing large chunk warning. Wide-screen visual acceptance and measured 60 FPS remain open.
