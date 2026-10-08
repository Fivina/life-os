# Product Constitution

Life OS exists to help one private user make sustainable progress while reducing cognitive load, overwhelm, anxiety-producing backlog, and planning effort.

The product is not a maximum-productivity system. It should let the user manage intentions, goals, commitments, and state while the system gradually takes on scheduling complexity.

## Non-Negotiable Boundaries

- PostgreSQL is the canonical source of truth.
- Browser clients display and interact with canonical state; they are not the source of truth.
- Calendars are outputs of the planning system.
- AI never directly controls the calendar.
- AI never receives unrestricted SQL or database access.
- Domains do not directly schedule calendar or plan blocks.
- The central Planner decides what is scheduled, when it is scheduled, and what moves; specialist domains never write `PlanBlock` directly.
- Planner V2 and bounded Personal Learning may improve scheduling decisions, but learned evidence remains advisory and deterministic code retains authority.
- The app is single-user for the foreseeable future.

## Operating Principle

Domains generate possibilities. Core code makes decisions. AI understands, generates, and communicates. Learning improves future decisions. The database stores canonical reality. Clients display and interact with that reality.
