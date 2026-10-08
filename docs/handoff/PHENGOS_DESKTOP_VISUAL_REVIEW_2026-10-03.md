# PHÉNGOS desktop visual review — 2026-10-03

Superseded for sidebar and glass treatment by `PHENGOS_FLOATING_RAIL_REVIEW_2026-10-04.md` after user review.

## Authority and reference order

User direction in this session takes priority. The six current visual files are `New Design/Design/{1,2,3,4,5,download}.png`; older images elsewhere in `New Design` are historical. `docs/PHENGOS_UNIVERSAL_DESIGN_CONTRACT.md` holds the lasting palette and object-origin rules. Existing routes and API data remain the implementation truth.

## Completed visual comparisons

| Reference | Mismatch found in live desktop app | Applied correction |
| --- | --- | --- |
| `2.png`, `3.png`, `4.png` | Sidebar was thin and strongly blue, with System in the main domain stack | Dark full-height rail, luminous identifier, subdued structural contour, active domain-colored contour and row, Kitchen direct entry, Search and Settings at the bottom. Home launcher rail follows the same treatment. |
| `2.png`, `5.png` | Intro background did not show behind routed components | Fixed the CSS cascade that replaced the image; routed pages now share a cropped still derived from the v17 intro environment. One composited background layer supplies stars and horizon. |
| `2.png`, `5.png`, `download.png` | Cards had blue-heavy interiors and weak edge contrast | Near-black card interiors, brighter thin contours, restrained source-colored edge glow; Nutrition is cyan, Calendar amber, Kitchen blue, attention red. |
| `2.png` | Calendar suggestion absent despite a real overloaded plan; empty selection card displaced the capacity and mini calendar | Real shortfall drives a compact suggestion above the attention card; selection details appear only after selecting an event. |
| `2.png` | Seven-day calendar overflowed horizontally on laptop width and lower input covered the right rail | Narrower minimum day width fits the full week at 1280px; fixed input aligns with the main calendar column. |
| `5.png` | Kitchen lower row touched the fixed input on shorter desktop displays | Height-aware card layout keeps the row clear at 1280×800 and 1440×900. |
| `5.png` | Kitchen headline exposed raw recipe ranking scores | The suggestion now uses the saved recipe name, actual ingredient availability and preparation time. Technical score text is suppressed in the primary meal description. |
| `download.png` | Home launcher lacked the current rail utility pattern | Added direct Kitchen, Search across the canonical feature list, and Settings at the bottom. All existing domain features remain accessible. |
| `download.png` | A raw partial-refresh sentence interrupted the Home card composition | Moved the status into a quiet, accessible source-status badge beside the date. |

## Verification and limits

- Live browser compared at 1440×900 and 1280×800, with real API data. Current stills: `PHENGOS_DESKTOP_2026-10-03.png`, `PHENGOS_CALENDAR_DESKTOP_2026-10-03.png`, and `PHENGOS_KITCHEN_DESKTOP_2026-10-03.png` in this directory.
- Focused Home, navigation, Calendar and Kitchen tests passed (80 tests before the final Home rail pass; 60 Home/navigation tests after it). TypeScript and the final production build passed. Vite still reports the pre-existing large main bundle warning.
- Real data currently fills mostly Saturday's Calendar column, contains a developer-like recipe title, and has no planned meals. The UI does not invent other events, a polished meal name, or food photography to match the example data in the catalog.
- The circle's own appearance and voice states remain outside this step by user direction. Browser frame cadence has not been measured, so the 60 FPS target is unverified.
