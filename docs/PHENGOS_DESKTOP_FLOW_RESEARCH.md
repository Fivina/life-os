# Phengos desktop flow: research and implementation decision

Snapshot: 2026-10-03. The ten sheets in `New Design` are visual/interaction references, not a source of domain data or instructions to add unsupported actions. The desktop focus is sheet 3's workspace and sheet 6's contextual card lifecycle.

## Working flow

1. The Blender film ends on the lone circle. Clicking it opens the desktop workspace.
2. Existing domain data is projected into ranked, asymmetric cards: today's plan and commitments, training, shopping, selected meal, near-term fixture, and pending assistant action.
3. A card shows its canonical source and an appropriate action. A proposal shows its arguments before allowing approval; long/complex arguments require review in its saved conversation.
4. Confirm/cancel calls the existing assistant proposal service. A successful mutation invalidates the affected Query caches; the card leaves the active set. Shopping and workout actions use their existing domain endpoints.
5. Pinning changes presentation order locally. Dismissal hides a card for this view and never changes domain data. All 21 existing destinations remain accessible.

## Focused comparison with maintained upstream approaches

| Approach | What it offers | Fit and decision |
| --- | --- | --- |
| [Motion for React layout animation](https://motion.dev/docs/react-layout-animations) | Transform-based position animation and `AnimatePresence` for exits. Already installed, MIT-licensed. | Use `layout="position"` for card reorder/arrival and a short spring. Keep the Blender scene as a video, so normal home has no WebGL render loop. A literal one-circle-to-many-cards shared `layoutId` is unsuitable because one source cannot represent several simultaneous cards. |
| [TanStack Query mutation invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations) | Targeted refetch after a confirmed mutation. Already installed. | Use it to update home and chat after proposal, shopping and training actions. This retains backend services as the source of truth. |
| [Adaptive Cards JS](https://github.com/microsoft/AdaptiveCards) | A maintained MIT JavaScript renderer, JSON card schema and submit actions. | The card host still has to map submits to Life OS permissions and canonical domain services. Its generic schema/styles would make the catalog-specific asymmetry and motion harder and add a second UI model. Use its structured-action idea, not its renderer, for this milestone. |
| [React Grid Layout](https://github.com/react-grid-layout/react-grid-layout/blob/master/README.md) | Maintained MIT responsive, draggable and resizable widgets. | No drag/resize requirement exists. CSS Grid spans already produce the asymmetric layout with less code and no saved layout state. Revisit only if user arrangement becomes a product requirement. |
| [AG-UI](https://github.com/ag-ui-protocol/ag-ui) and [CopilotKit human-in-the-loop](https://github.com/CopilotKit/OpenGenerativeUI/blob/main/docs/human-in-the-loop.md) | Typed streaming agent events and approval components. | Strong model for later voice and live generated cards. Life OS already has streaming work logs, persisted proposals, explicit confirmation and a domain tool registry. Replacing transport now would duplicate those contracts and require adapter work. Borrow the visible pending/approved/cancelled card lifecycle; assess AG-UI when voice transport is implemented. |
| [Radix Dialog](https://www.radix-ui.com/primitives/docs/components/dialog) | Maintained unstyled modal focus management. | A good candidate if the workspace dialog needs more complex nested controls. The current menu has a bounded focus trap and no nested dialog. Do not add a dependency during the data-flow milestone solely for visual work. |

Apple's [widget guidance](https://developer.apple.com/design/human-interface-guidelines/widgets) supports glanceable content with deeper detail on demand. Its [motion guidance](https://developer.apple.com/design/human-interface-guidelines/motion) supports brief feedback tied to real state changes and reduced-motion alternatives. The cards therefore avoid fabricated "thinking" animations and keep route links visible.

## Current gaps and limits

- Voice transport and agent-authored arbitrary card schemas are not in the current product. The existing proposal contract can be reused by a later voice interface; voice is not claimed implemented.
- Recipe records have no image field, so selected-meal cards show real recipe names and timing without fake food photos.
- A team logo appears only when the configured fixture provider supplies a safe HTTP(S) logo URL during synchronization. Fixture cards do not invent matches.
- Pin order is stored in this browser only. Domain state remains server-owned.
- The film is encoded at 60 fps. Browser playback timing and dropped-frame instrumentation are device dependent; an encoded rate is not a measured UI frame rate.
