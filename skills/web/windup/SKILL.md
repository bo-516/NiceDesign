---
name: windup
description: >-
  Make an SVG move: animated icons, logo reveals, loaders, draw-on, character
  loops, small scenes. Art and motion stay separate: a static rest pose
  (art.svg) plus a motion score (score.json), compiled by a bundled script to
  one CSS-animated SVG and checked on a frame strip. Give it a description or
  an existing SVG. Not for charts, page scroll choreography (web-animation),
  Lottie or Rive, or photoreal illustration.
disable-model-invocation: true
---
# Windup

**Terms**

- **art**: `art.svg`, the static rest pose. Correct when opened alone.
- **part**: an element with an `id` that moves as one piece, normally
  `<g id="arm" transform="translate(38 52)">`. Its geometry is drawn around
  local (0,0), which is its pivot; the `translate` places it. Parts nest.
- **score**: `score.json`, all motion. Refers to parts by id. No geometry.
- **clip**: one preset or one keyframe track on one part, with a start and a
  duration.
- **beat**: a named time range with one purpose.
- **strip**: sampled frames on one sheet, plus a text report of each part's
  box per frame.

**Input**: the text after the command. An SVG path or pasted SVG → animate
that art: do Rig instead of Block and Draw. Paths are relative to this
skill's folder. CLI: `node scripts/windup.mjs <lint|rig|compile|strip|presets>`.

**Files**: one folder: the one the user names, else `<slug>/` in the working
directory (2–4 words, kebab-case). It keeps `art.svg`, `score.json`,
`out.svg`, `out.html`. `still.*`, `sheet.*`, `marks.*` are scratch.

**Reference**: [references/score.md](references/score.md) and the `presets`
command are the whole interface. Don't read `windup.mjs` to learn it.

## Flow

1. **Target** — canvas, duration, loop. Unstated → one standalone `.svg`,
   looping. Ask only when the input is empty.
2. **Block** — a parts table: id, parent, box, pivot, z-order. No geometry.
3. **Draw** — write `art.svg` by §Art. Run `strip art.svg` (no score): it
   prints each part's box and pivot and renders the rest pose. Read the
   table, then look at the image.
4. **Rig** (given art) — `rig art.svg --marks`, then one
   `rig art.svg --group "name=3,4@center" … -o art.svg` call. Never retype a
   coordinate.
5. **Score** — run `presets`, then write `score.json` by
   [references/score.md](references/score.md): beats, then preset clips,
   then custom keys. Add one `checks` entry per order, direction,
   containment, or end state the request states: usually 2–6, not one per
   part.
6. **Strip** — `strip art.svg score.json`. Read the report, then look at the
   sheet. Fix `art.svg` or `score.json` and rerun. At most 3 rounds; then
   list what still fails.
7. **Compile** — `compile art.svg score.json -o out.svg --player out.html`.
8. **Deliver** — `out.svg`, `out.html`, the check results, and what was not
   verified. With a browser tool, open `out.html?t=<seconds>` at up to 3
   moments (it freezes there); without one, say no browser was used. The
   compiler is tested in Chrome only.

## Art

- `viewBox="0 0 W H"`, no `width`/`height`. Icon 24 or 48; logo 120–200;
  scene 320×180 or 400×300. `<title>` first.
- Integers; `.5` only to align a 1px stroke.
- Each part: `<g id="kebab-name" data-box="x y w h" transform="translate(px py)">`
  with geometry around (0,0). `data-box` is the box from Block; lint compares
  it with what was drawn.
- Rotation and scale happen about the pivot. A child part's `translate` is
  relative to its parent's pivot.
- `rect circle ellipse line polygon` before `path`. A path: relative commands
  after the first `M`, at most 12 commands.
- Mirror and repeat with `<use>` and `transform="… scale(-1 1)"`.
- At most 5 colors plus neutrals, as classes in `<style>`.
- Static only: no `@keyframes`, `animation`, `<animate>`, `transform-origin`.

## Ban

- Editing `out.svg` by hand
- A timing number anywhere but `score.json`
- Retyping the geometry of given art
- Freehand photoreal or textured illustration; ask for an asset
- Reporting a check you didn't run or a frame you didn't look at
