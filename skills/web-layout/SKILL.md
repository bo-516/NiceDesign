---
name: web-layout
description: >-
  Use when building page structure, spacing, grids, dashboards, app shells,
  landing composition, responsive layout, or visual hierarchy. Loads surface
  recipes for landing/dashboard/shell. Distilled from ui-craft, impeccable,
  taste-skill, shadcn-layouts, interface-design.
---
# Web Layout

Rules only. One skill: core below + surface recipes in `references/`.
**Before coding any non-trivial surface:** run §Plan, then load the matching recipe.

| Surface | Load |
|---------|------|
| Landing / marketing / portfolio | [references/landing.md](references/landing.md) |
| Dashboard / admin / analytics | [references/dashboard.md](references/dashboard.md) |
| App chrome / sidebar / scroll regions | [references/shell.md](references/shell.md) |
| Mixed | shell + the primary surface recipe |

## Plan (mandatory)

Emit before code (one block):

1. **Surface + audience** — e.g. “B2B dashboard for ops”
2. **Layout concept** — 1 sentence + ASCII wireframe (regions only)
3. **Density** — spacious | comfortable | dense
4. **Focal point** — the single thing that wins the squint test
5. **Signature bet** — one layout risk (asymmetric hero, bento, sticky subnav…) or “none”

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
- Full height: `min-h-[100dvh]` not lone `h-screen`.
- Mobile &lt;768: declare collapse for every multi-col block.
- Columns 4/8/12; gutters 16–32; prefer `@container` when the component owns width.

## Shell (always if app chrome)

- Height down: `h-full` chain; scrolling child **`min-h-0`**; overflow axis **`min-w-0`**.
- Chrome: `shrink-0`. Main: `min-width: 0`.
- Details → [references/shell.md](references/shell.md).

## Radii / z

- Radius by role (input &lt; card &lt; modal). Nested: outer ≈ inner + gap.
- z: dropdown 10 → sticky 20 → modal-backdrop 30 → modal 40 → toast 50 → tooltip 60. No 9999.

## Global ban

Equal spacing · nested cards · every section card-wrapped · icon+title+text card rows as default · monotone dashboards · numbered eyebrows · fake div “screenshots” · undeclared mobile collapse · flex `calc` columns · Grid-for-everything · `z-9999`

## Pre-ship

- [ ] Plan block existed and was followed
- [ ] Correct recipe loaded for the surface
- [ ] Squint = one focal point; spacing rhythm holds
- [ ] Shell scroll OK if app chrome
- [ ] Mobile collapse explicit
- [ ] Surface-specific checklist in the recipe file passes

References: ui-craft, impeccable/atelier, shadcn-layouts, interface-design, taste-skill, Vizro, Owl grid/spacing, DESIGN.md.
