---
name: web-layout
description: >-
  Use when building page structure, spacing scales, grids, dashboards, app
  shells, responsive composition, or visual hierarchy. Distilled from ui-craft
  layout, impeccable layout, atelier, shadcn-layouts, interface-design,
  taste-skill, DESIGN.md.
---
# Web Layout

Rules only. Spatial structure for app/marketing UI.

## Spacing

```css
--space-xs: 0.25rem; /* 4 */
--space-sm: 0.5rem;  /* 8 */
--space-md: 1rem;    /* 16 */
--space-lg: 1.5rem;  /* 24 */
--space-xl: 2rem;    /* 32 */
--space-2xl: 3rem;   /* 48 */
--space-3xl: 4rem;   /* 64 */
--space-4xl: 6rem;   /* 96 */
```

- **Invariant:** space_within_group &lt; space_between_groups &lt; space_between_sections.
- Use **gap** for siblings; avoid child margin math.
- Never arbitrary px outside the scale.
- Density dial: spacious (py large, 1–2 items/row) ↔ dense dashboard (8px rhythm, mono numbers).

## Gestalt / hierarchy

- Group with **proximity first**; cards/borders are a tax — earn them.
- Squint test: one primary blob, then secondary, chrome last.
- Adjacent hierarchy levels need ≥ **1.5×** size/weight difference (or clear weight+tracking pair).
- Tools order: space → size → weight → color.
- Max ~4 hierarchy levels.

## Composition

- Flex = 1D; Grid = 2D. Don't default Grid when Flex is enough.
- Prefer `repeat(auto-fit, minmax(min(100%, 280px), 1fr))` for responsive grids.
- Break **identical 3-card grids**; vary spans / mix non-card content.
- Asymmetry when DESIGN_VARIANCE &gt; 4; centered OK for manifesto/auth.
- Optical center ≈ 5–8% above geometric center (modals/heroes).
- Section layout family appears **at most once** per page (landing).
- Zigzag image/text: max **2 consecutive**; then break pattern.
- App shells: height flows down (`h-full` chain); scrolling flex child needs **`min-h-0`**; fixed chrome `shrink-0`.
- Hero (marketing): fits first viewport; headline ≤2 lines; subtext ≤20 words; CTA visible; top padding ≤ `pt-24`.
- Measure body ≈ **45–75ch** (prefer &lt;80).
- Full-height: `min-h-[100dvh]`, never `h-screen` alone.
- Mobile: high-variance layouts collapse to single column; declare &lt;768 fallbacks.
- Grid columns typical: 4 / 8 / 12; gutters 16–32; declare breakpoints.

## Z-index (semantic)

```css
--z-dropdown: 10; --z-sticky: 20; --z-modal-backdrop: 30;
--z-modal: 40; --z-toast: 50; --z-tooltip: 60;
```

No `z-9999`.

## Ban

- Equal spacing everywhere
- Nested cards
- Wrapping every section in a rounded card
- Numbered eyebrows (`01 / About`) unless content is a real sequence
- Eyebrow on every section (max ~1 per 3 sections)
- Fake product UI from empty `div` rectangles
- Sidebar full-dark by default (prefer subtle tint)
