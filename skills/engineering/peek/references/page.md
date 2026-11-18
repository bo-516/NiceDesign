# Preview page

Copy `assets/shell.html` to the preview path, then fill its three slots.
Change nothing else in it: the shell draws the controls, the spotlight, the
lists, and the reply line from the config.

| Slot | Find | Holds |
|---|---|---|
| CSS | `<style id="stage-css">` | Stage styles. Every selector starts with `#stage` |
| Stage | `<div id="stage">` | Markup of the screen or component being changed |
| Config | `<script type="application/json" id="peek-config">` | The JSON below |

## Config

```json
{
  "title": "MePage paywall: loading and failure toast",
  "rev": 1,
  "frame": "phone",
  "view": "spotlight",
  "sides": ["before", "after"],
  "scenes": [
    {"id": "loading", "label": "Loading", "badge": "new", "note": "Tap a card: its arrow becomes a 12px spinner, both cards lock"},
    {"id": "failed", "label": "Load failed", "badge": "new", "note": "Toast for 2 s, then the cards unlock"},
    {"id": "idle", "label": "Idle"}
  ],
  "start": "loading",
  "variants": [
    {"id": "toast", "label": "Toast position", "on": ["failed"], "options": [
      {"id": "bottom", "label": "Bottom", "rec": true, "why": "80 call sites use the default"},
      {"id": "top", "label": "Top"}
    ]}
  ],
  "stress": {"label": "Longest copy (de)", "text": {"failed": "Produkte konnten nicht geladen werden"}},
  "flows": {"open": [{"scene": "loading", "ms": 1200}, {"scene": "failed", "ms": 2000}, {"scene": "idle"}]},
  "behavior": [{"what": "Second tap while loading", "before": "opens a second paywall", "after": "ignored"}],
  "basis": [{"what": "Toast at the bottom", "source": "src/views/login/LoginPage.vue:123 (80 call sites)", "kind": "convention"}],
  "files": {"change": [{"path": "src/utils/paywall.ts", "what": "catch + toast"}], "keep": ["Paywall UI itself"]},
  "ui": {"before": "改前", "after": "改后"}
}
```

- Required: `title`, `scenes` (≥ 1 with a `badge`). Everything else is
  optional; omit what the change doesn't need.
- `frame`: `phone` (390 wide) or `desktop` for a whole screen; `none` for a
  lone component or a diagram.
- `view`: how a framed page opens: `spotlight` (default) or `closeup`.
- `sides`: nothing exists before the change → `["after"]`.
- `badge`: `new`, `changed`, `removed`. A scene without one is a resting
  look: not in the scene strip, reached only by a click or a flow.
- `on`: the scenes where the variant shows a difference. Its switch appears
  only there.
- `kind`: `code` (a file:line), `convention` (how the project does it
  elsewhere, with a count), `guess` (neither).
- `ui`: the shell's own labels, in the user's language. Keys: `before`,
  `after`, `spot`, `close`, `lift`, `behavior`, `basis`, `change`, `keep`,
  `copy`, `copied`, `ok`, `okHint`, `rec`, `new`, `changed`, `removed`,
  `guess`, `lint`.
- Ids are lowercase kebab-case. A variant id is never `side`, `scene`,
  `stress`, or `view`.
- The config never contains the text `</script`.

## Budget

The shell prints a red notice on the page while a limit is broken.

| | Limit |
|---|---|
| Scenes with a badge | ≤ 4 |
| Scenes without | ≤ 2 |
| Variant groups | ≤ 2; ≤ 3 options each; `on` required |
| `label` | ≤ 20 columns (a CJK character is 2) |
| `note` | ≤ 90 columns |
| Marked regions per scene | ≤ 3 (neighbours merge) |

What earns a control:

- **Scene**: a look the change adds, alters, or removes. Not an untouched
  neighbour, not the same look with other data, not the end of a flow that
  looks like another scene.
- **Variant**: a decision the project and the request leave open, and whose
  options look different in the stage. The recommended option first, with a
  `why`. An open decision with nothing to see → a question in the Show
  message.
- **Behavior**: a change with nothing to see (timing, requests, storage,
  routing, error handling) → one `behavior` row. Never a scene or a variant.
- **Stress**: only when the change puts new or changed text in a box that
  can't grow. `text` holds the longest locale's strings. The page has one
  language, the user's; there is no language switch.

## Stage

The shell keeps these on `#stage`: `data-side`, `data-scene`, `data-stress`
(`on` / `off`), and `data-v-<variant id>`. Style from them:
`#stage[data-scene=loading] .card { opacity: .6 }`.

| Attribute | Effect |
|---|---|
| `data-show="<cond>"` | Element exists only while the condition holds |
| `data-go="<scene id>"` | Click → that scene |
| `data-flow="<flow id>"` | Click → runs the flow: each step sets its scene, then holds `ms` |
| `data-t="<key>"` | Stress on → its text becomes `stress.text[key]` |
| `data-mark="new\|changed\|removed"` | Part of the change. In a framed page: gets a spotlight window. Inside an SVG: colors the stroke or text |
| `data-key="<id>"` | On two elements, one per side: they are the same thing |

Condition: space = and, comma = or, `!` = not. Keys: `side`, `scene`,
`stress`, or a variant id. Example: `side:after scene:loading,failed !toast:top`.

- Every scene has both sides. Before on a `new` scene: what the user saw at
  that moment before the change. After on a `removed` scene: what replaces it.
- Markup that differs per side → two elements, `data-show="side:before"` and
  `data-show="side:after"`; the same thing on both → the same `data-key`.
- Variants apply to the After side only.
- `position: fixed` anchors to the stage, not the window.

## Views

A framed page with marks has two views; the reader switches between them.

- **Spotlight**: the whole screen, blurred except for windows around the
  marked elements and the click targets (`data-go`, `data-flow`). The shell
  measures the windows from the live page, so they follow anything that
  moves; neighbours ≤ 12px apart share one. Windows over 55% of the frame (a
  new screen) → no blur.
- **Close-up**: zooms to one marked region, ≤ 3×. Before / After switch in
  place.
- Keys: ← → step through the scenes, Space switches sides. Holding the blur
  lifts it.

- Mark the smallest element that holds the change, not its container. An
  element the change only pushes aside is not marked.
- Never add an element only to carry a mark (an overlay, a wrapper).
- A restyle of a whole surface (a panel's or screen's material, background,
  theme) → no mark: the side switch shows it, the scene `note` names it.
- Marked elements and what touches them are exact. Blocks further away may
  be labeled boxes at their real size and position.
- `frame: none` has no views.

## Content

- **Scope**: the change adds, moves, or resizes something on a screen → the
  whole screen at real proportions, framed. The change stays inside one
  component → that component alone, `frame: none`.
- **Real values**: colors, radii, spacing, type sizes, durations, and copy
  come from the source, tokens, and theme files. Plain CSS. No CDN, no
  external request, no build step, unless the host allowlists one.
- **Real assets**: images as data URIs, ≤ 150 KB each; downscale larger ones
  (`sips -Z 600`, ImageMagick). Icons: the project's own SVG path, inlined.
  An asset you can't get → a labeled box, listed in `basis` as a guess.
- **Before** is the current code, read now.
- **Notes**: each `note` says what triggers the scene and what differs.
- **Flows**: the real elements are clickable and run the real sequence with
  the real durations, ending on a resting look. Unknown latency → 1200 ms,
  listed as a guess. No control in the stage that the product doesn't have.
- **Basis**: one row per visual decision. Every guess is listed.
- **Files**: every product file the build will touch, one line each. `keep`:
  what the reader might expect to change but won't.
- **Non-visual change** (flow, state machine, data shape, architecture): the
  stage is one inline SVG, `frame: none`. Scenes are scenarios (happy path,
  failure…). Added, altered, and dropped nodes and edges carry `data-mark`.
  Colors: `var(--pk-fg)`, `var(--pk-mute)`, `var(--pk-line)`. Text ≥ 12px.
- **Size**: file ≤ 400 KB. Shown inline in chat → whole page ≤ 500px tall
  (stage ≤ 260px); taller → pane or browser.

## Self-check

Before showing:

- The page opens with no console error and no red budget notice (use a
  browser tool if you have one).
- Before and After differ on every scene with a badge; every flow ends on a
  resting look.
- Before matches the current code.
- Everything new or altered in the stage carries `data-mark`, except a
  whole-surface restyle; nothing else does.
- Spotlight: each window hugs what it marks. An oval, or one window over most
  of the frame on a scene whose change is smaller → re-mark.
- `git status` shows no product file changed.
