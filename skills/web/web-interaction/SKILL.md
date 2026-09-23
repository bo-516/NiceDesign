---
name: web-interaction
description: >-
  Use when designing hover/focus/active/disabled/loading/error states, forms,
  buttons, micro-interactions, or CSS transition budgets. Distilled from
  impeccable interaction, better-ui, micro-interactions, Vercel guidelines,
  taste-skill.
---
# Web Interaction

Rules for controls, states, and micro-feedback. Motion budgets that are not GSAP timelines belong here; scroll/timeline choreography → web-animation.

## Eight states (every interactive control)

| State | Treatment |
|-------|-----------|
| Default | Rest styles |
| Hover | Contrast↑; optional lift (`translateY(-1px)`) + shadow↑ |
| Focus | Visible ring (`:focus-visible`); never `outline: none` without replacement |
| Active/pressed | `scale(0.96–0.98)` or `translateY(1px)` |
| Disabled | Opacity↓ + `pointer-events: none` / `aria-disabled`; not color alone |
| Loading | Skeleton matching final shape &gt; generic spinner |
| Error | Inline message + `aria-describedby`; border/icon |
| Empty/success | Directional empty; success confirmation |

Hover ≠ focus. Design both.

## Forms

- Visible `<label>`; placeholders are not labels.
- Validate on blur (except password strength).
- Error below field; helper optional above/below consistently.
- CTA text one line at desktop; one label per intent page-wide.
- Button text vs fill ≥ 4.5:1 (large text 3:1).

## Feedback contracts

- Interaction feedback ≤ **100ms** perceived.
- Hover: transform + color + shadow together when elevating; never change `font-weight` / padding / border-width on hover (layout jump).
- Disable pointer events on exiting elements.
- Optimistic UI only for low-stakes actions.
- Destructive: prefer undo over confirm when possible.

## Micro-motion (CSS / small UI)

```css
--motion-fast: 120ms;   /* color, opacity, tooltip */
--motion-base: 200ms;   /* dropdown, toggle, tab */
--motion-medium: 280ms; /* modal, drawer */
--motion-slow: 400ms;   /* page/sheet — rare */
--ease-out: cubic-bezier(0.22, 1, 0.36, 1);
```

- Exit ≈ **75%** of enter duration.
- List properties: never `transition: all`.
- Animate **transform / opacity** only for continuous motion.
- Stagger siblings **30–80ms** (marketing may 100–150ms).
- High-frequency (shortcuts, typing): **no animation**.
- Dashboard/settings: micro only; no entrance carnival.
- Bounce/elastic banned on functional UI.
- Honor `prefers-reduced-motion` (keep loaders + focus perceptible).

## Pointer / touch

- Touch targets ≥ 44px.
- `:hover` gated with `@media (hover: hover)`.
- `touch-action` / tap-highlight as needed.

## Ban

- Hover-only affordances with no focus style
- Spinner for known layouts (use skeleton)
- Duplicate CTAs with same intent
- `transition: all`
- Motion that blocks input while stagger plays
