# Preview page

Copy `assets/shell.html` to the preview path, then fill its three slots.
Change nothing else in it: the shell draws the controls, the lists, and the
reply line from the config.

| Slot | Find | Holds |
|---|---|---|
| CSS | `<style id="stage-css">` | Stage styles. Every selector starts with `#stage` |
| Stage | `<div id="stage">` | Markup of the changed region |
| Config | `<script type="application/json" id="peek-config">` | The JSON below |

## Config

```json
{
  "title": "MePage paywall: loading and failure toast",
  "summary": "One line: what to click and what to look at",
  "rev": 1,
  "frame": "phone",
  "sides": ["before", "after"],
  "states": [
    {"id": "idle", "label": "Idle", "note": "One line shown under the stage"},
    {"id": "loading", "label": "Loading", "badge": "new", "note": "Arrow becomes a 12px spinner; both cards lock"}
  ],
  "start": "idle",
  "variants": [
    {"id": "toast", "label": "Toast position", "options": [
      {"id": "bottom", "label": "Bottom", "rec": true, "why": "80 call sites use the default"},
      {"id": "top", "label": "Top"}
    ]}
  ],
  "locales": [{"id": "zh-CN", "label": "中文"}, {"id": "en", "label": "EN"}],
  "text": {"zh-CN": {"failed": "商品加载失败"}, "en": {"failed": "Failed to load products"}},
  "flows": {"open": [{"state": "loading", "ms": 1200}, {"state": "error", "ms": 2000}, {"state": "idle"}]},
  "basis": [{"what": "Toast at the bottom", "source": "src/views/login/LoginPage.vue:123 (80 call sites)", "kind": "convention"}],
  "files": {"change": [{"path": "src/utils/paywall.ts", "what": "catch + toast"}], "keep": ["Paywall UI itself"]},
  "ui": {"before": "改前", "after": "改后"}
}
```

- Required: `title`, `states` (≥ 1). Everything else is optional; omit what
  the change doesn't need.
- `frame`: `phone` (390 wide) for mobile screens, `desktop` for web pages,
  `none` for a component or a diagram.
- `sides`: nothing exists before the change → `["after"]`.
- `badge`: `new`, `changed`, `removed`; omit when the state is untouched.
- `kind`: `code` (a file:line), `convention` (how the project does it
  elsewhere, with a count), `guess` (neither).
- `ui`: the shell's own labels, in the user's language. Keys: `before`,
  `after`, `marks`, `basis`, `change`, `keep`, `copy`, `copied`, `ok`, `rec`,
  `new`, `changed`, `removed`, `guess`.
- Ids are lowercase kebab-case. A variant id is never `side`, `state`,
  `locale`, or `marks`.
- The config never contains the text `</script`.

## Stage

The shell keeps these on `#stage`: `data-side`, `data-state`, `data-locale`,
and `data-v-<variant id>`. Style from them:
`#stage[data-state^=loading] .card { opacity: .6 }`.

| Attribute | Effect |
|---|---|
| `data-show="<cond>"` | Element exists only while the condition holds |
| `data-go="<state id>"` | Click → that state |
| `data-flow="<flow id>"` | Click → runs the flow: each step sets its state, then holds `ms` |
| `data-t="<key>"` | Text comes from `text[locale][key]` |
| `data-mark="new\|changed\|removed"` | Outlined when the reader turns Marks on. Inside an SVG: colors the stroke or text, always |

Condition: space = and, comma = or, `!` = not. Keys: `side`, `state`,
`locale`, or a variant id. Example: `side:after state:loading,error !toast:top`.

- Markup that differs per side → two elements, `data-show="side:before"` and
  `data-show="side:after"`.
- The Before side disables `new` states and all variants; the After side
  disables `removed` states. Write Before-only CSS under
  `#stage[data-side=before]`.

## Content

- **Scope**: the changed region plus the least context that makes it
  recognisable. A layout change → the whole page at real proportions;
  untouched blocks may be labeled boxes.
- **Real values**: colors, radii, spacing, type sizes, durations, and copy
  come from the source, tokens, and theme files. Plain CSS. No CDN, no
  external request, no build step, unless the host allowlists one.
- **Real assets**: images as data URIs, ≤ 150 KB each; downscale larger ones
  (`sips -Z 600`, ImageMagick). Icons: the project's own SVG path, inlined.
  An asset you can't get → a labeled box, listed in `basis` as a guess.
- **Before** is the current code, read now.
- **States**: each state the change adds, alters, or removes, plus the ones
  beside it: idle, loading, empty, error, success, disabled, longest text.
  ≤ 8. Each `note` says what triggers the state and what differs.
- **Flows**: the real elements are clickable and run the real sequence with
  the real durations. Unknown latency → 1200 ms, listed as a guess.
- **Variants**: only decisions the project and the request leave open.
  ≤ 3 groups, 2–3 options each, the recommended one first with a `why`.
- **Locales**: copy changes in a localised project → the source locale plus
  the one with the longest strings.
- **Basis**: one row per visual decision. Every guess is listed.
- **Files**: every product file the build will touch, one line each. `keep`:
  what the reader might expect to change but won't.
- **Non-visual change** (flow, state machine, data shape, architecture): the
  stage is one inline SVG. States are scenarios (happy path, failure…).
  Added, altered, and dropped nodes and edges carry `data-mark`. Colors:
  `var(--pk-fg)`, `var(--pk-mute)`, `var(--pk-line)`. Text ≥ 12px.
- **Size**: file ≤ 400 KB. Shown inline in chat → whole page ≤ 500px tall
  (stage ≤ 260px); taller → pane or browser.

## Self-check

Before showing:

- The page opens with no console error (use a browser tool if you have one).
- Every state shows something different; every flow ends in a resting state.
- Before matches the current code.
- Everything new or altered in the stage carries `data-mark`.
- `git status` shows no product file changed.
