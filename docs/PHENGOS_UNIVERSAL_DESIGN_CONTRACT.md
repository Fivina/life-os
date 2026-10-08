<!-- Durable project contract. Source: user-provided PHÉNGOS UI LANGUAGE v0.1, 2026-10-03. -->
# LIFE OS universal design contract

This file preserves the full user-provided v0.1 contract below. Treat the sections as product direction and the live repository as implementation truth. Update this file when the user changes the design; add a dated entry to the change log rather than silently replacing a decision. Keep `docs/PHENGOS_VISUAL_LANGUAGE.md` and shared CSS tokens aligned with accepted revisions. The reference images are in `D:/Life OS/New Design/Design/`.

## 2026-10-04 visual correction — current priority

- The sidebar capsule and **all cards across routed domains** share one smoked, near-black translucent material. Keep the introduction scene fully present in the open canvas; tint it locally only where a card or the sidebar sits. The scene should remain perceptible through those surfaces while the contour, text, and restrained inner reflection keep content legible. Do not add a page-wide dark wash behind the interface.
- The sidebar in `New Design/Design/2.png` and isolated `3.png` is a **narrow floating object**, not a full-height slab. The LIFE OS identifier and orb sit above a separate rounded navigation capsule. Leave visible scene space at its left and bottom edges. Its structure is dark blue-black; the active row and a short contour segment carry the current domain accent.
- The workspace has **no continuous top or bottom bar**. Page content occupies the sky. Required navigation and session actions may remain as individual unobtrusive controls; the reference's assistant input is a floating instrument, not a footer strip.
- Cards and widgets use **smoked black glass**: the scene reads through the interior without competing with text. Use a restrained inner reflection, depth shadow and brighter contour. Ordinary data cards, calendar events, calendar cells, and repeated utility rows keep their fill dark; domain color belongs at the edge, icon and selected state. Notifications and PHÉNGOS suggestions may tint the glass with their semantic red, amber, green or blue, but remain translucent windows rather than matte color blocks. Avoid stacking opaque inner layers on a glass card.
- Apply this geometry and material consistently to the Home surface and routed workspaces. This correction supersedes earlier implementation notes describing a full-height rail.
- Glass uses a two-level hierarchy: **dark blue glass** for a major workspace frame, and **deeper near-black glass** for its ordinary information cards and repeated items. Both need a visible thin specular reflection at the upper edge, a controlled illuminated contour, and enough transparency for the sky to register. An alpha value alone does not make a matte fill look like glass. Apply the treatment to the entire Calendar and Kitchen pages, including lower legacy utilities and forms; do not stop at their new overview panels.
- In Calendar, scheduled items, Today, Week Allocation and Commitment Calendar are ordinary dark glass. Needs Attention is translucent red glass; PHÉNGOS Suggestion is translucent blue glass. Their semantic colors do not justify opaque blocks.

## 2026-10-03 implementation amendment

- The current work covers the shared desktop sidebar, main menu, navigation, Calendar and Kitchen. Do not redesign PHÉNGOS's circle or implement voice states in this step.
- The shell's contour is a visible but elegant structural rail. Increase its weight and depth from the current thin blue edge. Let selected contour segments and the active navigation row transition to the current domain accent. The universal blue foundation remains visible under that accent.
- On a mixed Overview or Calendar surface, a card or event keeps the **origin object's** accent. Use the accent in contour segments, icon, small edge, selected state or restrained illumination. Avoid full neon fills and uniform colored boxes. Attention red is reserved for actual conflicts or intervention.
- Do not generate food images from the Kitchen catalog. Use real approved media only when a backend utility supplies it. Until then, make the meal utility credible through typography, content and states; do not substitute an arbitrary stock photograph.
- Preserve all existing routed controls, API contracts, data states, browser history and deep links. The catalog shows a target composition, not permission to invent schedule, nutrition, recommendation or assistant data.
- References: `1.png` is the Calendar view and object-to-card interaction atlas; `2.png` is the full desktop Calendar shell and strongest current page reference; `3.png` (109×719) isolates the sidebar; `4.png` (20×115) isolates a contour fragment, so inspect it with `2.png`; `5.png` is the Kitchen composition; `download.png` is the widget-origin and contour system sheet. The food photos in `5.png` are composition references, not assets to recreate now.

## Design change log

| Date | Decision | Owner and affected implementation |
| --- | --- | --- |
| 2026-10-03 | Freeze v0.1 as a shared language; use Calendar as the strongest current reference. Make shell contours denser and context-sensitive while object accents remain restrained. Defer circle redesign and food image creation. | User direction; shared shell, Calendar, Kitchen, future domains |
| 2026-10-04 | The floating sidebar uses the same near-black translucent glass as every card. The scene must remain faintly visible through both. | User correction; shared glass tokens and all routed cards |
| 2026-10-04 | The background is the primary visual surface. Remove the page-wide dark overlay and let only cards and the sidebar tint the scene locally. Use a small blur so stars and horizon still read through the smoked glass. | User clarification; Home and routed workspace material correction |
| 2026-10-04 | Apply smoked glass to every card and widget. Keep ordinary Calendar events and utility rows dark with colored contours; reserve translucent color fills for notifications and suggestions. Remove opaque inner meal layers in Kitchen. | User clarification; Kitchen, Calendar, and shared routed utilities |
| 2026-10-04 | Distinguish structural blue glass from darker information glass with upper-edge reflection and scene visibility. Carry the treatment through all lower Calendar and Kitchen tools and forms. Keep Calendar attention red and suggestion blue. | User screenshot correction; full Calendar and Kitchen routes |

---

Yes. I would now freeze this as the **shared LIFE OS visual-language contract** before we design more individual pages.

# LIFE OS — PHÉNGOS UI LANGUAGE v0.1

## 1. What we are actually building

LIFE OS is **not a collection of separate apps sitting behind a sidebar**.

Home, Kitchen, Fitness, Learning, Calendar, Life, Shopping, etc. share:

- one shell,
- one visual language,
- one persistent assistant,
- one card/object language,
- one motion grammar.

The individual domains provide their own **identity**, primarily through accent color, iconography and the data they display.

The core concept is:

> **PHÉNGOS is persistent.  
> The interface around PHÉNGOS changes according to context.**

The old hyper-realistic solar-system interface is no longer the operating UI. We keep only the parts that gave LIFE OS character:

- dark space,
- sparse stars,
- cinematic depth,
- light,
- atmospheric blue,
- subtle cosmic feeling.

Functionality now comes first.

---

# 2. PHÉNGOS

PHÉNGOS is the luminous circle.

It should never feel like a normal chatbot avatar.

It is:

- assistant identity,
- navigation continuity,
- status indicator,
- agent-role carrier,
- origin of contextual cards,
- conversational entry point.

### Circle structure

The core should remain **filled**.

That is important.

The new idea from the latest design is to give the circle **internal life** rather than making it an empty glowing ring.

Inside PHÉNGOS:

- slow cloud / steam / plasma-like movement,
- soft volumetric turbulence,
- barely perceptible internal circulation,
- no obvious waveform,
- no cliché voice visualizer.

Think more:

> **small luminous atmosphere**

than:

> voice assistant orb.

### Intensity communicates state

PHÉNGOS does not need to continuously move around.

Its internal energy gives it personality.

| State | Behavior |
|---|---|
| Idle | very slow internal cloud, weak halo |
| Available | normal glow, subtle internal motion |
| Listening | slightly brighter rim, internal cloud becomes more responsive |
| Thinking | increased internal activity, concentrated luminosity |
| Speaking | soft rhythmic luminosity, not an audio waveform |
| Focused/working | tighter, brighter core |
| Attention | red contamination/pulse only when action is genuinely required |

The circle itself remains identifiable through every state.

---

# 3. Domain identity

The domains have different colors, but **they are still part of one dark LIFE OS world**.

The color is an accent, not the entire page.

## Frozen primary palette

| Domain | Role | Primary |
|---|---|---|
| **Overview / Self** | system-wide context | `#60A5FA` |
| **Home** | Home + Kitchen + Shopping + Household | `#3B82F6` |
| **Fitness** | Fitness + Training + Nutrition | `#06B6D4` |
| **Life** | Life / social / personal | `#22C55E` |
| **Learning** | learning / university | `#A855F7` |
| **Calendar** | time / commitments / planning | `#F59E0B` |
| **Attention** | required action / conflict / urgent | `#EF4444` |

### Important rule

**Red is never a normal domain color.**

`#EF4444`

means:

> Something requires attention.

No decorative red.

No generic negative numbers in red.

No red buttons simply because they look dramatic.

---

# 4. Core dark palette

The dark surfaces are what make those colors look expensive rather than childish.

| Token | Code | Purpose |
|---|---|---|
| `space-black` | `#01060D` | deepest background |
| `space-deep` | `#020A14` | primary application background |
| `surface-0` | `#06111F` | large workspace surfaces |
| `surface-1` | `#091727` | normal cards |
| `surface-2` | `#0C1D30` | elevated/hover cards |
| `surface-3` | `#10243A` | selected/high-information surfaces |
| `line-dark` | `#132A42` | normal separators |
| `line-blue` | `#174D78` | structural contour |
| `contour-blue` | `#0E6BA8` | brighter futuristic contour |
| `text-main` | `#F1F7FF` | primary text |
| `text-secondary` | `#A9B8CB` | secondary |
| `text-muted` | `#6F849C` | tertiary |
| `phengos-white` | `#F4FCFF` | circle core |
| `phengos-blue` | `#4FC3FF` | external glow |

The background should **never become pure flat black everywhere**.

There should be slight blue depth.

---

# 5. The contour-line language

This should become one of the most recognizable visual elements of LIFE OS.

You pointed out exactly the right element in the Calendar design.

The sidebar is one object.

But **sharp glowing lines exist independently around it**.

Those lines:

- turn corners,
- terminate intentionally,
- occasionally leave gaps,
- frame important spatial regions,
- imply a larger invisible system,
- do not simply trace every rectangle.

They should feel like:

> **technical rails / electronic architecture / futuristic instrument geometry**

rather than decorative borders.

### Base contour

```text
#174D78
```

### Highlight contour

```text
#0E6BA8
```

### Very active system contour

```text
#38A8E8
```

Low opacity most of the time.

Typical opacity:

```text
18–35%
```

Highlight:

```text
45–70%
```

Never create bright blue outlines around every component.

That would turn the interface into neon cyberpunk.

---

# 6. Contours inherit domain context

The **form remains universal**.

Only selected pieces of the contour can inherit the domain color.

Example:

### Calendar

Base rail:

```text
#174D78
```

Calendar accent:

```text
#F59E0B
```

### Kitchen

Base rail stays:

```text
#174D78
```

Selected accent becomes Home blue:

```text
#3B82F6
```

### Learning

```text
#A855F7
```

This creates a very useful effect:

The user always feels:

> “I am still inside LIFE OS.”

while also immediately understanding:

> “I am currently inside Learning.”

---

# 7. Sidebar

The latest Calendar sidebar is now the reference.

We should keep it globally.

Do not redesign it independently for Kitchen, Calendar, Fitness, etc.

## Structure

At top:

**LIFE OS**

then PHÉNGOS.

Then major domains.

Current direction:

```text
Home
Calendar
Focus / Learning depending final IA
Learning
Fitness
Life
Kitchen / Home context where necessary
```

Later this can expand as LIFE OS grows.

Bottom remains:

```text
Search
Settings
```

### Selected domain

The selected row receives:

- domain-color icon,
- faint colored background,
- domain-color left rail / contour,
- very restrained glow.

Example Calendar:

```text
background:
rgba(245,158,11,0.08)

border/glow:
#F59E0B
```

Kitchen/Home:

```text
rgba(59,130,246,0.08)
#3B82F6
```

---

# 8. Card language

This is extremely important.

We are **not designing independent card styles for every page**.

We create one family of LIFE OS cards.

The differences come from:

- source domain,
- importance,
- type,
- state.

---

# 9. Standard card

Base:

```text
background: #091727
border: #17304A
```

Hover:

```text
background: #0C1D30
border: #27577E
```

Default radius:

```text
12–16px
```

Main surfaces can use:

```text
16–20px
```

Not everything should be extremely rounded.

---

# 10. Domain card accents

Every widget retains the identity of its **origin domain** even when shown somewhere else.

This is one of the central rules.

## Home widget

```text
primary: #3B82F6
soft fill: rgba(59,130,246,0.08)
border: rgba(59,130,246,0.55)
glow: rgba(59,130,246,0.18)
```

## Fitness

```text
primary: #06B6D4
soft fill: rgba(6,182,212,0.08)
border: rgba(6,182,212,0.55)
glow: rgba(6,182,212,0.18)
```

## Life

```text
primary: #22C55E
soft fill: rgba(34,197,94,0.08)
border: rgba(34,197,94,0.50)
glow: rgba(34,197,94,0.16)
```

## Learning

```text
primary: #A855F7
soft fill: rgba(168,85,247,0.08)
border: rgba(168,85,247,0.55)
glow: rgba(168,85,247,0.18)
```

## Calendar

```text
primary: #F59E0B
soft fill: rgba(245,158,11,0.08)
border: rgba(245,158,11,0.55)
glow: rgba(245,158,11,0.18)
```

## Overview / Self

```text
primary: #60A5FA
soft fill: rgba(96,165,250,0.07)
border: rgba(96,165,250,0.45)
glow: rgba(96,165,250,0.14)
```

## Attention

```text
primary: #EF4444
soft fill: rgba(239,68,68,0.09)
border: rgba(239,68,68,0.65)
glow: rgba(239,68,68,0.22)
```

---

# 11. Widget origin identity

This becomes particularly important on **Overview**.

Imagine the general overview contains:

```text
Training today
Dinner tonight
Football match
Exam preparation
Shopping
Calendar conflict
```

They should not all become generic Overview-blue cards.

Instead:

### Training

Cyan.

```text
#06B6D4
```

### Dinner / Kitchen

Blue.

```text
#3B82F6
```

### Learning

Violet.

```text
#A855F7
```

### Social / Life

Green.

```text
#22C55E
```

### Calendar

Amber.

```text
#F59E0B
```

### Required attention

Red.

```text
#EF4444
```

The Overview page itself remains deep blue.

Therefore Overview becomes a **composition of your life**, rather than a page with one arbitrary color.

---

# 12. Dynamic Overview

The overview should not have a permanently fixed grid of ten dashboard statistics.

Instead, it has a **stable spatial skeleton with dynamic contents**.

Example morning:

```text
Today's schedule
Training
University
Breakfast / nutrition
Upcoming football match
```

Example evening:

```text
Dinner
Tomorrow
Shopping
Recovery
Football match
```

Example shopping day:

```text
Shopping list
Fridge state
Today's schedule
Payment
Training
```

The system decides what deserves exposure.

But we should not randomly move everything every five minutes.

There should be stable zones.

---

# 13. Widget priorities

Widgets can exist in approximately three priority states.

### Ambient

Useful but not urgent.

Smaller.

Low glow.

### Relevant

Contextually useful right now.

Normal card.

Domain accent visible.

### Attention

User genuinely needs to do something.

Red.

Can rise visually.

This means a shopping widget could normally be blue.

When shopping becomes relevant today:

Blue remains its identity.

Maybe brighter.

But it **does not become red** simply because shopping is today.

It becomes red only if something is wrong or requires intervention.

---

# 14. Contextual examples

## Dinner approaching

Kitchen card appears:

```text
Dinner
19:00

Garlic Chicken Bowl
20 min
All ingredients available
```

Blue Home/Kitchen accent.

---

## Training today

Fitness card:

```text
Training
18:00

Upper Body
65 min
```

Cyan.

---

## Football match

Life card:

```text
Beşiktaş      vs      Opponent
20:00

Match in 2h 15m
```

Team logos can appear.

The card uses its **Life-domain green identity** or a very restrained event treatment.

Team colors can appear inside the content.

They should not rewrite LIFE OS chrome.

---

## Shopping

```text
Shopping
7 items

3 planned meals
4 household
```

Home blue.

---

## Exam / study

```text
Macroeconomics
Exam in 9 days

Today's session
14:00–16:00
```

Learning violet.

---

# 15. Cards are objects, not screenshots

This is another fundamental LIFE OS rule.

A card should be able to change representation depending on context.

Example:

A Study block exists.

### Calendar

```text
Study Macro
14:00–16:00
```

### Daily List

```text
14:00
Study Macro
2h
```

### Overview

```text
Next
Study Macro
14:00
```

### PHÉNGOS conversation

```text
Study Macro

Current
14:00–16:00

Suggested
Saturday 11:00–13:00
```

Same underlying object.

Different density.

---

# 16. Card transformation levels

I would formalize three.

### Compact

Used in:

- calendar,
- lists,
- small overview widgets.

### Standard

Used in:

- overview,
- domain dashboard.

### Expanded

Used in:

- PHÉNGOS conversation,
- detail inspection,
- proposal/approval.

This is how the UI remains coherent.

---

# 17. PHÉNGOS suggestion card

This is its own recognizable card type.

We should preserve the design from Calendar.

### Color

PHÉNGOS/system blue:

```text
#60A5FA
```

Border:

```text
rgba(96,165,250,0.65)
```

Strong highlight:

```text
#38BDF8
```

Interior:

```text
#08172A
```

Example:

```text
PHÉNGOS SUGGESTION

Saturday is overloaded by 75 min.
2 suggestions available.
```

It should always visually connect back to PHÉNGOS.

---

# 18. Attention card

Only used when the user must notice something.

Example:

```text
NEEDS ATTENTION

Study Macro conflicts with Social
10:00–13:00

Review
```

Colors:

```text
background: #160C12
border: #EF4444
glow: rgba(239,68,68,0.20)
```

Red should be striking because we rarely use it elsewhere.

---

# 19. Statistic cards

Examples:

- Week Capacity
- Nutrition
- Body goal
- Commitment calendar
- Learning trajectory
- Cooking competency

These should not just display giant numbers.

Where useful, they become visualizations.

Examples:

### Nutrition

rings.

### Capacity

vertical bars.

### Commitment consistency

daily cells.

### Body goal

eventually a human-body progression visualization.

### Learning

trajectory / completion / confidence.

The design philosophy:

> **show state spatially before forcing the user to read numbers.**

---

# 20. Calendar visual language

The latest Calendar design is now an important reference.

Calendar accent:

```text
#F59E0B
```

But events retain their source colors.

This is why the Calendar looks good.

The Calendar **container belongs to Calendar**.

The events belong to their own domains.

Example:

```text
University → Learning purple
Training → Fitness cyan
Dinner → Home blue
Social → Life green
Meeting / pure calendar commitment → Calendar amber
Conflict → Attention red
```

This means the Calendar becomes another place where LIFE OS identity naturally combines.

---

# 21. Kitchen visual language

Kitchen belongs to Home.

Therefore its base domain color is:

```text
#3B82F6
```

Do not invent a new unrelated color for Kitchen.

Kitchen gets its own **icon and contextual PHÉNGOS role**, not another full color universe.

Main Kitchen screen contains:

### PHÉNGOS Suggestion

one.

### Tonight / relevant meal

hero utility.

### Fridge

real inventory state.

### Nutrition target

compact.

### Quick Actions

- Log external meal
- Add ingredient
- Scan recipe

### Week meal strip

small meal-plan representation.

### Shopping connection

only compact status.

The full Shopping system remains under Shopping.

---

# 22. Fridge card

This deserves a distinct internal language.

Normal item:

```text
#3B82F6
```

Fresh indicator could use green minimally:

```text
#22C55E
```

Use-soon warning:

```text
#F59E0B
```

Critical expiry:

```text
#EF4444
```

Again:

Red only when actual intervention is necessary.

The Fridge card itself remains Home blue.

Ingredient status colors exist **inside** the card.

---

# 23. Calendar workspace

Calendar should have:

- Day
- Week
- Month
- Today controls
- quick add
- actual grid,
- Today widget,
- Week Capacity,
- Commitment Calendar,
- PHÉNGOS suggestion,
- Needs Attention when necessary.

Calendar occupies most of the screen.

PHÉNGOS accompanies it.

PHÉNGOS does not dominate it.

---

# 24. Commitment calendar

This is intentionally **not another traditional calendar**.

It is a small behavioral/statistical strip.

Example:

```text
October

1 2 3 4 5 6 7 8 ...
■ ▓ ░ □ █ ▓ ...
```

High-performance day:

dark/strong filled cell.

Weak:

light.

Nothing:

near-empty.

It can remain primarily monochrome with Calendar accent.

Do not use a red/green habit tracker aesthetic.

---

# 25. Assistant input bar

The latest Calendar bar should become a shared LIFE OS component.

This is important.

Structure:

```text
●  Add an event, or tell PHÉNGOS...
                              contextual tools
                         [ primary action ]
```

The left PHÉNGOS object remains alive.

### In Calendar

Placeholder:

> Add an event, or tell PHÉNGOS…

Primary action:

> Add Event

Calendar amber.

---

### In Kitchen

Placeholder:

> Add a meal, check my fridge, or ask PHÉNGOS…

Possible contextual quick functions:

- recipe
- meal
- ingredient

Primary color:

Home blue.

---

### In Learning

> Add study work, or ask PHÉNGOS…

Violet.

---

The **bar architecture stays identical**.

Only context and domain accent change.

---

# 26. Chat behavior

This is **not a chatbot page**.

PHÉNGOS conversation emerges from the current workspace.

On desktop:

The workspace can compress to roughly 50–60%.

Conversation materializes beside it.

So when you're in Calendar:

```text
CALENDAR | PHÉNGOS
```

not:

```text
leave Calendar → open ChatGPT clone
```

If PHÉNGOS talks about a calendar event, the original event component can expand into conversation.

Same for recipe.

Same for shopping item.

Same for workout.

---

# 27. Conversation storage philosophy

We also discussed that specialist agents should not create independent chat universes.

There is one conversational history with context metadata.

A session could be displayed as:

```text
Dinner planning
Kitchen · Chef

Tomorrow's schedule
Calendar · Learning

Training adjustment
Fitness · Training
```

Not:

```text
ChefBot Chat
FitnessBot Chat
CalendarBot Chat
```

The activity defines the session.

PHÉNGOS remains the identity.

---

# 28. Specialist agents

Agents are expressed through:

- PHÉNGOS context,
- domain color,
- domain glyph,
- available tools,
- relevant data.

Not separate avatars.

Kitchen Chef:

white PHÉNGOS + blue role accent.

Training:

white PHÉNGOS + cyan.

Learning:

white PHÉNGOS + violet.

Life:

white PHÉNGOS + green.

Calendar:

white PHÉNGOS + amber.

---

# 29. Motion philosophy

We are deliberately not implementing final motion yet.

But all designs should support it.

Later:

### Card appears

not simple fade.

PHÉNGOS may emit a line/node and the card materializes.

### Calendar block discussion

block lifts → expands → PHÉNGOS attaches.

### Approve

card contracts → object settles into new state.

### Navigation

PHÉNGOS persists.

Interface changes around it.

### Idle

after ~10–15 minutes:

PHÉNGOS returns to its waiting/idle state.

---

# 30. Typography

I agree with you: the typography in the latest Calendar generation works extremely well.

The general direction should be:

> **modern neo-grotesk / geometric sans**

Not futuristic gamer typography.

Something close to:

- Inter
- Geist
- Manrope

with careful spacing.

### Suggested typography hierarchy

Main title:

```text
32–36 px
500–600
```

Section header:

```text
18–20 px
600
```

Card title:

```text
15–17 px
600
```

Body:

```text
14–15 px
400
```

Caption:

```text
11–12 px
400–500
```

Metadata labels can use generous tracking.

---

# 31. Glow rules

Glow is important.

But it needs discipline.

### Structural glow

Blue.

Low.

### Domain glow

Only selected/important components.

### PHÉNGOS glow

always present.

### Attention glow

rare red.

The rule should be:

> **Glow communicates energy, focus or identity—not decoration.**

---

# 32. What the Overview eventually becomes

Overview should become arguably the most intelligent page in LIFE OS.

It should answer:

> **What matters in my life right now?**

Not:

> Here are my 12 apps.

Therefore a particular day could show:

```text
08:30 University

18:00 Training
Upper body

20:00 Beşiktaş
Match in 3h

Dinner
Chicken bowl
Ready in 20 min

Shopping
7 items for Friday

Learning
Exam in 9 days
```

Each keeps its domain identity.

PHÉNGOS can decide which ones deserve exposure.

---

# 33. The deepest principle

This is probably the most important visual-system decision we've reached:

> **The page does not own the visual identity of a widget.  
> The object owns its identity.**

Therefore:

A Fitness widget shown on Home is cyan.

A Learning event shown on Calendar is violet.

A Dinner card shown on Overview is Home blue.

An urgent Learning item becomes red **only because it requires attention**, but still carries enough Learning identity internally to remain recognizable.

This makes the entire OS feel like one connected system.

---

# 34. What we should NOT do

No:

- emoji UI,
- rainbow cards,
- full neon borders everywhere,
- independent design style for each domain,
- giant page introductions,
- dashboard made exclusively from statistics,
- multiple PHÉNGOS suggestion boxes,
- permanent giant forms,
- chatbot pages for every agent,
- red as decoration,
- excessive space backgrounds inside every card,
- glassmorphism everywhere,
- animation simply because animation is possible.

---

# 35. Where the design stands now

We now effectively have four foundational components:

**1. Universal shell**  
Dark space + contour language + sidebar.

**2. PHÉNGOS**  
Persistent intelligent circle with internal atmosphere and state intensity.

**3. Object/card system**  
Compact → standard → expanded, maintaining domain identity everywhere.

**4. Contextual workspace**  
Calendar, Kitchen, Home, Learning etc. use the same system but emphasize different kinds of information.

And the new **Calendar design is the strongest current reference for the overall UI language**.

The goal now should be to make Kitchen, Home, Fitness, Learning and Life feel as sharp as Calendar **without cloning Calendar's layout**.

They should clearly belong to the same operating system.

That is the visual language I would freeze before we continue designing the next major pages.

---

# Implementation amendment — 2026-10-03 desktop comparison

The six files in `New Design/Design` are the current visual references. The older images in `New Design` are historical context and must not override them. In this set, `2.png` is the primary complete Calendar view, `5.png` is the primary Kitchen view, `3.png` and `4.png` isolate the sidebar and contour, `1.png` shows Calendar view transitions and object-to-card motion, and `download.png` explains the common language and source identity.

- The routed desktop shell and the general surface fill the viewport. They sit over a still derived from the v17 Blender intro environment, with the title letters removed. The horizon and stars remain visible around the cards. The background is one composited image layer, not per-card scene rendering.
- Card interiors are near black. Brighter, thin contours and small edge glows create the contrast shown in `2.png` and `5.png`. A domain accent belongs to the object: blue for Kitchen and Shopping, cyan for Nutrition and Fitness, violet for Learning blocks on Calendar, amber for time and planning, green for Life, red only for attention. Do not turn whole cards into saturated colored fills.
- The desktop rail is one dark object. Its structural outline is subdued blue. The current page accent appears on its selected item and upper contour, and the rail keeps Search and Settings at the bottom. Kitchen has a direct rail destination, while all canonical feature routes remain available through the existing groups and Search.
- The common lower input bar is text first. Calendar and Kitchen use relevant existing shortcuts; typed input opens the existing Assistant route. Voice behavior remains future work. It must not cover a card at the initial desktop viewport.
- Calendar's PHÉNGOS suggestion may summarize a real overloaded plan even when there is no pending proposal. The separate attention card holds the actual shortfall and review path. No invented schedule, meal, fixture, or completed action may appear as live data.
- Kitchen suggestion copy is derived from the saved recipe, available or missing ingredients, and real preparation time. Raw scores and backend diagnostic explanations stay out of the primary view. Food photos are deferred to the separate backend media utility.

Review this amendment against the images and update it when the approved visual direction changes; keep the frozen palette and object-origin rule intact unless the user explicitly revises them.
