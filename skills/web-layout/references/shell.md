# App shell / scroll / chrome recipe

Load with web-layout whenever there is a sidebar, top nav, split panes, or inner scrolling.

## Frame first

| | `fixed` — viewport-locked | `document` — page scrolls |
|---|---|---|
| Root | `height: 100dvh; overflow: hidden; display: flex` | `min-height: 100dvh; display: flex; flex-direction: column` |
| Chrome | always visible, `flex-shrink: 0` | header `position: sticky; top: 0` |
| Scrolling | inside named regions | the document |
| Content longer than a screen | region scrolls, frame does not move | page grows |

`height` vs `min-height` is the whole difference. `min-height` on a `fixed` root is
the single most common app-shell bug: the shell grows with content, so a sidebar
sized to the shell becomes document-tall and scrolls out of view, while a tall right
column silently drags the page long. Write `height` (or `h-dvh` / `h-full`) plus
`overflow: hidden`, and give every scrolling region `min-height: 0`.

## Constraint model

- **Height flows down** from `html/body/#root`. A `fixed` frame needs a definite
  height somewhere: either `100dvh` at the shell root, or `height: 100%` on
  `html, body, #root` and `h-full` below it. `h-full` under an `auto`-height
  ancestor silently resolves to `auto` — the chain must be unbroken.
- **Width** is often content-sized — cap with `max-w-*` or grid tracks.
- A flex/grid child that scrolls **must** have `min-h-0` (vertical) / `min-w-0`
  (horizontal). Missing this is the classic “page won’t scroll / overflows”.
- Fixed chrome (topbar, sidebar, tab bar, footer): `shrink-0` + stable size.
- Main / pane: `flex-1 min-h-0 min-w-0 overflow-auto` (or grid `minmax(0,1fr)`).
- **One scroll owner per pane.** Decide which element owns it before typing
  `overflow` anywhere; nested `overflow:auto` that fight produce double scrollbars.

## Canonical patterns

**Full-height app**

```text
[ viewport dvh ]
  header shrink-0
  body flex-1 min-h-0
    sidebar shrink-0        (own scroller inside: nav min-h-0 overflow-auto)
    main flex-1 min-h-0 overflow-auto
```

**Dashboard + header + scrollable table**

```text
main column flex-1 min-h-0
  toolbar shrink-0
  table region flex-1 min-h-0 overflow-auto
```

**List → detail → inspector (3 pane)**

```text
body flex-1 min-h-0
  list   w-[320px] shrink-0  min-h-0 overflow-auto
  detail flex-1 min-w-0 min-h-0 overflow-auto
  aside  w-[360px] shrink-0  min-h-0 overflow-auto
```

**Chat / composer**

```text
main flex-1 min-h-0 flex flex-col
  messages flex-1 min-h-0 overflow-auto
  composer shrink-0
```

**Single-screen dashboard (nothing scrolls)**

```css
/* rows SHARE the leftover height instead of each adding its own min-height */
.main { display: grid; grid-template-rows: auto minmax(0, 1fr); min-height: 0; }
.panel { min-height: 0; }           /* never min-height: 320px */
.panel-body { min-height: 0; overflow: auto; }
```

Stacking `min-height` on panels is how a “one screen” dashboard turns into a long
page. If it must fit, every row is `minmax(0,1fr)` and overflow goes inside panels.

**Split panes:** each pane `minmax(0,1fr)`; resizer `shrink-0`; pane body scrolls
inside, not the window (unless intentional).

## Bounded media

Charts, maps, canvases, video and iframes have no intrinsic height worth trusting.
Inside a `fixed` frame every one of them gets a bounded box:

- a fixed height (`h-[240px]`), or
- `aspect-ratio`, or
- a grid row of `minmax(0,1fr)` with the chart at `height: 100%`.

A chart library’s default (often 300px) plus a few stacked panels is exactly how the
right column ends up taller than the viewport. Size the container, let the chart fill it.

## Sticky

- Sticky headers need a scroll ancestor; don’t put `overflow: hidden` on all parents.
- Offset sticky by header height (`top: var(--header-h)`).
- Safe areas: `env(safe-area-inset-*)` on fixed chrome.
- In a `fixed` frame, chrome is already permanent — `sticky` there is redundant.

## Nav / sidebar

- Desktop nav one line; collapse to drawer/hamburger with an explicit breakpoint.
- Sidebar height = the remaining viewport under the header; the nav list scrolls
  **inside** the sidebar (`min-h-0 overflow-auto`), the page does not double-scroll.
- Pin the sidebar footer (user chip, version) with `margin-top: auto`, not spacers.
- State the collapse mode per breakpoint: `drawer` (overlay), `rail` (icons only),
  or `hidden`. “Didn’t think about narrow” is not a mode.

## Overflow

- Prefer region scroll over document scroll for app shells.
- Long tables: decide the clip strategy — horizontal scroll in the table region,
  column priority, or card stack on narrow — never silent overflow.

## Symptom → cause

| What you see | Cause |
|---|---|
| Sidebar scrolls away with the page | shell root used `min-height` instead of `height`, or sidebar sits in document flow |
| Whole page got long, right column too tall | no region owns the scroll; panels stack `min-height` |
| Region won’t scroll, content clipped | scrolling flex/grid child missing `min-h-0` |
| Two scrollbars fighting | nested `overflow:auto` with no declared primary scroller |
| `h-full` does nothing | broken height chain — an ancestor is `auto` |
| Layout jumps on mobile URL bar | `100vh` instead of `100dvh` |
| Chart grows every render | unbounded container; chart sized by its own content |
| Horizontal scrollbar on the whole app | a pane missing `min-w-0`, or a fixed-width child inside a flexible one |

## Shell ban

- `min-height: 100dvh` as a `fixed` shell root
- `h-screen` alone (mobile URL-bar jump) — prefer `dvh`
- Scrollable flex child without `min-h-0`
- Nested `overflow: auto` fighting each other without a primary scroller
- Expanding main that pushes chrome off-screen
- Unbounded chart/media height inside a `fixed` frame

## Shell pre-ship

- [ ] Frame named; root matches the frame table
- [ ] Definite-height chain intact (`dvh` at the root, or `100%` all the way down)
- [ ] Every scroller has `min-h-0` / `min-w-0`
- [ ] Chrome `shrink-0`; exactly one scroll owner per pane
- [ ] Charts/media bounded in `fixed` frames
- [ ] Narrow breakpoint: drawer / rail / hidden stated
- [ ] Checked at 1280×720 — chrome still visible, no page-level scrollbar in `fixed`
