# Landing / marketing layout recipe

Load with web-layout for landings, portfolios, launch pages.

## Density defaults

- Density: spacious–comfortable. Section py often `--space-3xl`–`--space-4xl` (vary for rhythm; don’t equalize).
- Variance: prefer asymmetric / split / bento over centered-everything.

## Hero (hard)

- Must fit initial viewport: H1 ≤2 lines; sub ≤20 words and ≤4 lines; primary CTA visible without scroll.
- Top padding ≤ ~6rem (`pt-24`). Don’t float hero mid-viewport with huge `pt`.
- Max 4 text slots: (eyebrow XOR brand strip) + H1 + sub + CTAs (1 primary + ≤1 secondary).
- Ban inside hero: trust micro-strip, pricing tease, feature bullets, logo wall, tagline under CTAs.
- Logo / “Trusted by” wall = **next section**, real SVG marks, logos only (no category labels under each).
- Font scale with asset: long H1 → don’t start at 7xl/8xl; typical `text-4xl md:text-5xl lg:text-6xl`.
- Height: `min-h-[100dvh]` not `h-screen`.

## Section system

- Each section answers one question; cut decorative sections.
- **Layout family ≤1 use per page** (split, bento, quote, metrics strip, FAQ, pricing, full-bleed media…).
- Zigzag image↔text: max 2 consecutive; then break (full-bleed / bento / stacked).
- Eyebrow budget: ≤ ceil(sectionCount / 3); no `01 / About` unless ordered process.
- Split-header ban: no “left giant title + right floating paragraph”; stack H + body ≤65ch.
- Features: prefer 2–3 asymmetric rows with real visuals — never default 3 equal icon cards.
- Bento: N items → N cells; ≥2–3 cells need image/tint/pattern (not all cream text tiles).
- Long lists (&gt;5): not bare `divide-y` ul — cards, 2-col groups, accordion, or marquee (≤1 marquee/page).

## Nav

- One line at desktop; height ≤80px (prefer 64–72). Condense before wrapping.

## Rhythm numbers

| Region | Guidance |
|--------|----------|
| Major section gap | 80–160px equivalent (token `--space-3xl`–`4xl`, vary) |
| In-section stack | `--space-md`–`lg` |
| Content column | max ~65–75ch for prose |

## Landing ban

- Identical feature card grids
- Scroll cues (“Scroll to explore”)
- Mid-page theme invert (whole page one theme)
- Duplicate CTA intents (“Contact” + “Let’s talk”)
- Div-fake product screenshots in hero

## Landing pre-ship

- [ ] Hero viewport + 4-slot rule
- [ ] Layout families unique; zigzag ≤2
- [ ] Eyebrow count OK
- [ ] Logo wall under hero
- [ ] Nav single-line desktop
