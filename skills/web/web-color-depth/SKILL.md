---
name: web-color-depth
description: >-
  Use when choosing palettes, CSS color tokens, dark mode, elevation, or
  box-shadows for web UI. Covers color system + shadow/depth rules distilled
  from frontend-design, ui-craft, taste-skill, better-colors, DESIGN.md,
  smooth-shadows.
---
# Web Color & Depth

Rules only. No process narration.

## Color system

- Prefer **OKLCH** for scales; hold hue, vary L/C.
- Product UI: **≥90% neutrals + 1 accent**. Semantic only: success / warning / error / info.
- Marketing may commit harder; still **one primary accent** unless brief says otherwise.
- Tint neutrals (warm ~60° or cool ~250°); avoid pure `#000` / `#fff` on large surfaces.
- **One accent lock**: same accent across the whole page/app surface.
- Never default: purple→cyan gradients, neon glow, Inter+slate-900 purple SaaS look, cream+brass+espresso “premium” default.
- Max accent saturation usually **&lt; 80%** unless brand demands it.
- Interactive states **increase contrast** vs rest (hover/active/focus).
- Prefer **APCA** / WCAG AA min (text 4.5:1, UI 3:1). Mid-lightness surfaces (L≈0.4–0.7) are contrast traps.
- Dark mode: `color-scheme`; elevate with **white alpha overlays** (≈6/8/12%) not inventing random lighter greys; reduce shadow intensity.
- P3: ship sRGB-safe default, richer chroma under `@media (color-gamut: p3)`.
- Never grey text on saturated fills — use darker shade of the fill or alpha of on-color.
- Tokens: primitives → semantic (`--surface-*`, `--text-*`, `--status-*`, `--interactive-*`). No raw hex in components.

## Shadow / elevation

```css
--shadow-sm: 0 1px 2px rgb(0 0 0 / 0.05);
--shadow-md: 0 4px 6px rgb(0 0 0 / 0.07), 0 1px 3px rgb(0 0 0 / 0.06);
--shadow-lg: 0 10px 15px rgb(0 0 0 / 0.1), 0 4px 6px rgb(0 0 0 / 0.05);
--shadow-xl: 0 20px 25px rgb(0 0 0 / 0.1), 0 8px 10px rgb(0 0 0 / 0.04);
```

- Prefer **layered** shadows (ambient + direct), soft blur, real offset — not zero-offset glow halos.
- Tint shadow toward surface hue when possible; avoid dirty pure-black on warm UIs.
- **Cards only when elevation = hierarchy**. Prefer spacing / hairline / surface tint first.
- Dark mode: shadow often fails → use `0 0 0 1px rgb(255 255 255 / 0.08)` ring / inset highlight.
- One elevation language per project: border **or** shadow for resting cards (no ghost-card both).
- Ban: hard comic `4px 4px 0` (unless brutalist brief), neon outer glow as primary affordance, decorative blur orbs.
- Image edge: inset outline `rgb(0 0 0 / 0.1)` light / `rgb(255 255 255 / 0.1)` dark — not tinted palette greys.
- Optional craft: multi-layer stacks (3–6 layers) for soft depth; one strength per component state.

## Do / Don't

| Do | Don't |
|----|--------|
| CSS variables for all colors/shadows | Magic hex / one-off shadow in components |
| Accent 3–5 placements above the fold | Rainbow accents competing |
| Soft layered elevation | Soft grey `rgba(0,0,0,.1)` under every identical card |
