---
name: web-layout
description: >-
  Use when building page structure, spacing, grids, dashboards, app shells,
  landing composition, responsive layout, scroll ownership, or visual hierarchy.
  Decides viewport-locked vs document-scroll frames and loads surface recipes
  for landing/dashboard/shell. Distilled from ui-craft, impeccable, taste-skill,
  shadcn-layouts, interface-design.
---
# Web Layout

Rules only. One skill: core below + surface recipes in `references/`.
**Before coding any non-trivial surface:** run §Frame, then §Plan, then load the matching recipe.

| Surface | Load |
|---------|------|
| Landing / marketing / portfolio | [references/landing.md](references/landing.md) |
| Dashboard / admin / analytics | [references/dashboard.md](references/dashboard.md) |
| App chrome / sidebar / scroll regions | [references/shell.md](references/shell.md) |
| Mixed | shell + the primary surface recipe |

## Frame (decide first, before any markup)

Two frames. Pick one **by name** and say which, in one line, before writing code.

| | `fixed` — viewport-locked | `document` — page scrolls |
|---|---|---|
| For | console, dashboard, editor, canvas, chat, IDE, tool | landing, marketing, docs, article, long form, auth |
| Root | `h-dvh overflow-hidden flex` | `min-h-dvh flex flex-col` |
| Scrolls | regions, each with its own scroller | the document |
| Chrome | permanently visible, `shrink-0` | `sticky top-0` header |

**Test:** must the sidebar / topbar stay visible while the user reads? → `fixed`.
Mixed page = `document` outside, a `fixed`-style panel with its own scroller inside.

**The one mistake that defines this skill:** a `fixed` frame written with
`min-height: 100dvh` instead of `height`. `min-height` grows with content, so the
shell becomes as tall as the *document*, not the *viewport* — the sidebar stretches
past the fold and scrolls away, and any tall column drags the whole page long.
`fixed` root takes **definite height** (`h-dvh` / `h-full`) plus `overflow-hidden`.

## Plan (mandatory)

Emit before code (one block):

1. **Frame** — `fixed` or `document`, one clause of why
2. **Surface + audience** — e.g. “B2B dashboard for ops”
3. **Layout concept** — 1 sentence + ASCII wireframe (regions only)
4. **Density** — spacious | comfortable | dense
5. **Focal point** — the single thing that wins the squint test
6. **Signature bet** — one layout risk (asymmetric hero, bento, sticky subnav…) or “none”

If the plan looks like a generic SaaS card kit, revise once before coding.

## Spacing (8pt)

```css
--space-xs: 0.25rem; /* 4 */  --space-sm: 0.5rem;  /* 8 */
--space-md: 1rem;    /* 16 */ --space-lg: 1.5rem; /* 24 */
--space-xl: 2rem;    /* 32 */ --space-2xl: 3rem;  /* 48 */
--space-3xl: 4rem;   /* 64 */ --space-4xl: 6rem;  /* 96 */
```

- Invariant: within_group &lt; between_groups &lt; between_sections (~1.5–2×).
- Siblings: **`gap` only** — no child-margin column math.
- No off-scale magic px. Fluid: `clamp(var(--space-lg), 4vw, var(--space-3xl))`.

## Gestalt → hierarchy

- Group with **proximity first**; cards/borders are a tax.
- Squint: 1 dominant → secondary → chrome. One focal point.
- Adjacent levels ≥ **1.5×** size/weight (or clear 400/700 pair).
- Tools order: space → size → weight → color.
- Optical center ≈ 5–8% above geometric (modals/heroes).
- Critical nav/list items: first or last, not mid-buried.

## Composition core

- Flex=1D, Grid=2D. Intrinsic: `repeat(auto-fit, minmax(min(100%, 280px), 1fr))`.
- Break identical 3–6 card grids; never nest cards.
- Body measure 45–75ch. ≤2 alignment types per section.
- Full height: `dvh` over `vh`; never a lone `h-screen`.
- Mobile &lt;768: declare collapse for every multi-col block.
- Columns 4/8/12; gutters 16–32; prefer `@container` when the component owns width.

## Shell (always if app chrome)

- **One scroll owner per pane.** Name it before you write `overflow` anywhere.
- Height down: definite-height chain; scrolling child **`min-h-0`**; overflow axis **`min-w-0`**.
- Chrome: `shrink-0`. Main: `min-width: 0`.
- In a `fixed` frame, charts / maps / media / iframes need a **bounded** height
  (fixed value, `aspect-ratio`, or a `minmax(0,1fr)` grid row) — they have no
  intrinsic size and will otherwise push the frame open.
- Details + symptom→cause table → [references/shell.md](references/shell.md).

## Radii / z

- Radius by role (input &lt; card &lt; modal). Nested: outer ≈ inner + gap.
- z: dropdown 10 → sticky 20 → modal-backdrop 30 → modal 40 → toast 50 → tooltip 60. No 9999.

## Global ban

Equal spacing · nested cards · every section card-wrapped · icon+title+text card rows as default · monotone dashboards · numbered eyebrows · fake div “screenshots” · undeclared mobile collapse · flex `calc` columns · Grid-for-everything · `z-9999` · **`min-height:100dvh` as a `fixed` shell root** · **scrollable flex child without `min-h-0`** · **sidebar that scrolls away with the document** · **unbounded chart/media height inside a `fixed` frame**

## Pre-ship

- [ ] Frame named before code; root matches the table
- [ ] Plan block existed and was followed
- [ ] Correct recipe loaded for the surface
- [ ] Exactly one scroll owner per pane; every scroller has `min-h-0`
- [ ] Squint = one focal point; spacing rhythm holds
- [ ] Mobile collapse explicit
- [ ] Surface-specific checklist in the recipe file passes

References: ui-craft, impeccable/atelier, shadcn-layouts, interface-design, taste-skill, Vizro, Owl grid/spacing, DESIGN.md.
