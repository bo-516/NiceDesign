# Dashboard / admin layout recipe

Load with web-layout for dashboards, admin, analytics, dense product UI.

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
- Charts without adjacent context (label, period, delta)

## Dashboard pre-ship

- [ ] Density dial stated; not airy-marketing
- [ ] ≥3 content types or deliberate single-focus
- [ ] KPI/chart spans make sense; rectangles clean
- [ ] Shell scroll + sidebar per shell.md
- [ ] Skeletons match final layout
