---
name: web-animation
description: >-
  Use when adding web animation, scroll effects, timelines, pinning, parallax,
  or GSAP/ScrollTrigger/React animation. Distilled from official
  greensock/gsap-skills plus ui-craft and taste-skill motion budgets.
---
# Web Animation (GSAP-first)

Distilled from greensock/gsap-skills + ui-craft/taste motion rules. Prefer **GSAP** for timelines, scroll, SVG, sequencing. CSS/`motion` OK for trivial hover.

## Decision

1. Justify: hierarchy / state / space / story — else cut.
2. Frequency: 100+/day → none; occasional → 200–300ms; once → may delight.
3. One authored moment &gt; fade-slide every section.
4. Claimed motion intensity must actually ship; else lower the dial.
5. Marquee ≤1 per page. No scroll-jacking / `window.onscroll` polling.

## Library choice

| Need | Use |
|------|-----|
| Timeline, scrub, pin, SVG morph, interruptible sequence | **GSAP** |
| Trivial opacity/transform hover | CSS transition |
| React layout shared-element only | Motion OK; don't mix GSAP+Motion in same tree |

Install: `gsap` (+ `@gsap/react` in React). Always `gsap.registerPlugin(...)` before use.

## GSAP core

- Tweens: `to` / `from` / `fromTo` / `set`. camelCase props.
- Prefer aliases: `x y scale rotation xPercent yPercent`; **`autoAlpha`** over `opacity` when hiding.
- Don't animate `width/height/top/left` if transform works.
- Ease: `power2.out` default; `none` for scrub-linked; no bounce on chrome.
- Stagger: `0.1` or `{ each, from }`. Prefer stagger over many delayed tweens.
- Sequence with **timeline**, not chained `delay`.
- Relative: `"+=20"`. `overwrite: "auto"` when fighting.
- Stacked `from`/`fromTo` on same prop → later ones `immediateRender: false`.
- Defaults: `gsap.defaults({ duration: 0.6, ease: "power2.out" })`.
- Hot mouse follow: `gsap.quickTo()`.

## Accessibility / responsive

```js
const mm = gsap.matchMedia();
mm.add({
  isDesktop: "(min-width: 800px)",
  reduceMotion: "(prefers-reduced-motion: reduce)"
}, (ctx) => {
  const { reduceMotion } = ctx.conditions;
  gsap.to(".el", { y: reduceMotion ? 0 : 40, duration: reduceMotion ? 0 : 0.8 });
});
// unmount: mm.revert()
```

## ScrollTrigger

```js
gsap.registerPlugin(ScrollTrigger);
gsap.timeline({
  scrollTrigger: {
    trigger: ".section",
    start: "top top",
    end: "+=1000",
    scrub: 1,      // OR toggleActions — not both
    pin: true,     // animate children, not the pinned el
    // markers: true // dev only
  }
}).to(".a", { x: 100 }).to(".b", { autoAlpha: 0 });
```

- Put ScrollTrigger on **timeline / top-level tween**, never nested child tweens.
- Create triggers **top→bottom** or set `refreshPriority`.
- After DOM/fonts/images change: `ScrollTrigger.refresh()`.
- Fake horizontal: pin wrapper; animate inner `x`/`xPercent` with **`ease: "none"`**; nested triggers use `containerAnimation`.
- Cleanup SPA: `ScrollTrigger.getAll().forEach(t => t.kill())` or context revert.

## React

```js
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP, ScrollTrigger);
useGSAP(() => {
  gsap.from(".item", { autoAlpha: 0, y: 24, stagger: 0.08 });
}, { scope: containerRef });
```

- Prefer `useGSAP` + `scope`; else `gsap.context` + `ctx.revert()`.
- Event-created tweens → wrap with `contextSafe`.
- No GSAP during SSR.

## Performance

- Compositor only: transform + opacity (+ autoAlpha).
- `will-change: transform` only while animating.
- Kill off-screen / route-leave animations.
- Batch lists: `ScrollTrigger.batch` for enter staggers.

## Patterns (minimal)

**Sticky stack:** pin each card `start: "top top"`, `pinSpacing: false`; scale/fade driven by next card scrub.

**Reveal:** `from` autoAlpha+y once in view (`toggleActions` or batch) — not every dashboard widget.

## Ban

- ScrollTrigger on timeline children
- scrub + toggleActions together
- ease ≠ `none` on horizontal scrub track
- markers in production
- elastic/bounce on buttons
- Entrance animations on every page load / every metric card
- Mixing GSAP and Motion on the same nodes
