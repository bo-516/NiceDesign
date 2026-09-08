# App shell / scroll / chrome recipe

Load with web-layout whenever there is sidebar, top nav, split panes, or inner scrolling.

## Constraint model

- **Height flows down** from `html/body/#root` with explicit heights / `h-dvh` / `h-full`.
- **Width** often content-sized — cap with `max-w-*` or grid tracks.
- Flex/grid child that scrolls **must** have `min-h-0` (vertical) or `min-w-0` (horizontal). Missing this = classic “page won’t scroll / overflows”.
- Fixed chrome (topbar, sidebar, tab bar): `shrink-0` + stable size.
- Main / pane: `flex-1 min-h-0 min-w-0 overflow-auto` (or grid `minmax(0,1fr)`).

## Canonical patterns

**Full-height app**

```text
[ viewport dvh ]
  header shrink-0
  body flex-1 min-h-0
    sidebar shrink-0
    main flex-1 min-h-0 overflow-auto
```

**Dashboard + header + scrollable table**

```text
main column flex-1 min-h-0
  toolbar shrink-0
  table region flex-1 min-h-0 overflow-auto
```

**Split panes:** each pane `minmax(0,1fr)`; resizer shrink-0; pane body scrolls inside, not the window (unless intentional).

## Sticky

- Sticky headers need a scroll ancestor; don’t put `overflow: hidden` on all parents.
- Offset sticky by header height (`top: var(--header-h)`).
- Safe areas: `env(safe-area-inset-*)` on fixed chrome.

## Nav / sidebar

- Desktop nav one line; collapse to drawer/hamburger with explicit breakpoint.
- Sidebar height = remaining viewport under header; nav list scrolls inside sidebar (`min-h-0 overflow-auto`), page doesn’t double-scroll unless designed.

## Overflow

- Prefer region scroll over document scroll for app shells.
- Long tables: decide clip strategy — horizontal scroll in table region, column priority, or card stack on narrow — never silent overflow.

## Shell ban

- `h-screen` only (mobile URL bar jump) — prefer `dvh`
- Scrollable flex child without `min-h-0`
- Nested `overflow: auto` fighting each other without a primary scroller
- Expanding main that pushes chrome off-screen

## Shell pre-ship

- [ ] dvh/full-height chain intact
- [ ] Every scroller has min-h-0/min-w-0
- [ ] Chrome shrink-0; one primary scroll owner per pane
- [ ] Narrow breakpoint: drawer/stack defined
