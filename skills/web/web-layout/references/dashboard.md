# Dashboard / admin layout recipe

Load with web-layout for dashboards, admin, analytics, dense product UI.
Pair it with [shell.md](shell.md) — a dashboard is app chrome, so the frame decision comes first.

## Fit decision (before the grid)

| | One screen (`fixed`) | Scrolling board (`fixed` shell, scrolling main) |
|---|---|---|
| Use when | wall display, ops console, “everything at a glance” | many modules, exploration, drill-down |
| Main region | `grid-template-rows: auto minmax(0,1fr)` — rows share leftover height | `overflow-auto`, modules stack |
| Panels | `min-height: 0`, body scrolls inside | natural height is fine |
| Charts | bounded row or `aspect-ratio` | fixed height per chart |

Either way the **shell** is viewport-locked and the sidebar never scrolls away.
Only the main region's behaviour differs. Never express “one screen” with panel
`min-height` values — stacked minimums are additive and always overflow.

## Density defaults

- Density: **comfortable → dense**. Prefer 8px rhythm; mono/`tabular-nums` for metrics.
- Variance: low–mid (symmetric grids OK). Don’t import landing drama.

## Information architecture

- Squint: primary KPI or live work surface wins; filters secondary; chrome quiet.
- ≥**3 content types** per main viewport when possible (e.g. KPI + chart + table/list). Monotone equal cards = failure.
- Primary metric may get accent tint; siblings stay neutral — no identical colored top borders on every card.
- Comparisons: plain secondary text (“+12% vs last week”), not candy pills by default.

## Grid / KPI

- 12-col mental model (or CSS grid equivalent). Every widget a clean rectangle — no ragged spans.
- KPI tiles: short (often 2–3 cols × 1 row). Charts need more rows (≥2–3). Tables full width or explicit span.
- Filters: page-level vs container-level — don’t duplicate. Sticky filter bar only if scroll is long.
- Sparklines OK on KPIs; chart type matches data (time → line/area; rank → bar). Avoid pie/3D.

## Charts inside the frame

- Every chart lives in a container with a decided height; the chart is `100%` of it.
- A chart library default height (commonly 300px) × a few stacked panels is what
  makes the right column taller than the viewport. Size containers, not charts.
- Re-measure on container resize (`ResizeObserver` / the library's resize call),
  and dispose on unmount — a chart that only sizes on mount is wrong after collapse.

## Chrome pairing

- Use [shell.md](shell.md) for sidebar/header/scroll.
- Sidebar: subtle bg tint &gt; full-black slab. Width ~240–280 = nav serves content; ≥320 = peers.
- Don’t wrap every module in a heavy card — denser UIs use hairlines / surface steps.

## States as layout

- Reserve space for loading skeletons matching final geometry.
- Empty/error: still occupy the same regions (no layout jump to a lone illustration).

## Dashboard ban

- Landing heroes / big marketing whitespace inside app
- 6 identical metric cards with same border accent
- Equal padding everywhere (kills hierarchy)
- Horizontal scroll of the whole app shell
- Panel `min-height` stacks used to express a one-screen layout
- Charts without adjacent context (label, period, delta)

## Dashboard pre-ship

- [ ] Fit decision stated: one screen vs scrolling board
- [ ] Density dial stated; not airy-marketing
- [ ] ≥3 content types or deliberate single-focus
- [ ] KPI/chart spans make sense; rectangles clean
- [ ] Charts bounded; resize handled
- [ ] Shell scroll + sidebar per shell.md
- [ ] Skeletons match final layout
