# score.json

This page and `node scripts/puppet.mjs presets` are the whole interface.
`presets` lists every preset with what it animates, its defaults, and its
parameters.

```json
{
  "canvas": [320, 180],
  "duration": 4,
  "loop": false,
  "beats": { "rise": [0, 1.2], "idle": [1.2, 4] },
  "clips": [
    { "part": "sun", "preset": "slide-in", "from": "bottom", "beat": "rise" },
    { "part": "rays", "preset": "spin" },
    { "part": ["cloud-l", "cloud-r"], "preset": "slide-in", "from": "left", "at": "<0.2", "stagger": 0.15 },
    { "part": ["cloud-l", "cloud-r"], "preset": "float", "beat": "idle" },
    { "part": "bird", "preset": "draw", "at": 1.2, "dur": 0.5 },
    { "part": "bird", "prop": "rotate", "at": ">", "times": 2,
      "keys": [[0, 0], [0.3, -12, "out"], [0.6, 0, "inOut"]] }
  ],
  "checks": [
    { "order": ["sun", "cloud-l"] },
    { "moves": "sun", "dir": "up", "in": "rise" }
  ]
}
```

## Fields

| Field | Meaning |
|---|---|
| `canvas` | `[W, H]`, equal to the art's viewBox |
| `duration` | seconds, required |
| `loop` | `true` repeats forever; every channel must end where it starts |
| `beats` | `{ name: [start, end] }` |
| `part` | an id, or a list of ids with `stagger` seconds between them |
| `at` | seconds (default 0); `"<"` starts with the previous clip, `">"` after it; `"<0.2"`, `">0.2"` add an offset; or a beat name |
| `beat` | start at the beat; loop presets fill it |
| `dur` | seconds; each preset has a default |
| `times` | play a one-shot preset or a keys clip N times |
| `period` | loop presets: seconds per cycle; must divide the clip length |
| `offstage` | `true`: this clip may leave the canvas |

## Presets

| Kind | Presets |
|---|---|
| in (ends at the rest pose) | `fade-in` `pop` `grow` `slide-in` (`from`, `dist`) `drop` `draw` `wipe` (`from`) |
| out (starts at it) | `fade-out` `shrink` `slide-out` (`to`, `dist`) `erase` |
| loop | `spin` (`turns`, `dir`) `float` `pulse` `sway` `blink` `wiggle` (`amp`) `march` `orbit` (`center`) |
| emphasis | `shake` `bounce` `flash` `nod` |
| path | `follow` (`path`: id or d string; `rotate: "auto"`) `morph` (`to`: id or d string) |

- Sides are `left right top bottom`. `from: "left"` enters from the left.
- `draw`, `erase`, `march` need stroked geometry with `fill="none"`.
- `morph` needs the same path commands on both sides.
- Clips on different channels, or several transform clips on one part, may
  overlap: they add up. Two `draw`, `fill`, `stroke`, or `d` clips on one
  part may not overlap.

## Keys clips

`{ "part", "prop", "keys": [[t, value, ease?], …] }`. `t` is seconds from the
clip start; the first key is at 0. The ease belongs to the segment that ends
at that key.

- Props: `x y rotate scale scaleX scaleY opacity` (offsets from the rest
  pose: 0, 0, 0, 1, 1, 1, 1), `fill stroke` (colors), `strokeWidth`,
  `draw` (0–1), `d` (path strings), `along` (0–1, with `path`).
- Eases: `linear in out inOut back steps(n)` or `[x1, y1, x2, y2]`.
  Default `inOut`.
- `"loop": true` repeats the keys to the end of the score or beat.

## Checks

`strip` runs them. `in` is a beat name or `[t0, t1]`, default the whole
score. `at` is seconds, `"start"`, `"end"`, or a beat name (its start).
Ranges are sampled 30 times a second; a hidden part is skipped.

| Check | Passes when |
|---|---|
| `{ "order": ["a", "b"] }` | each part's first in clip (else its first clip) starts later than the one before it |
| `{ "moves": "a", "dir": "up", "in": "rise" }` | from the start of the range to its end, the box center moves `up down left right` by 0.5 units or more; `cw ccw` compare the part's own rotation |
| `{ "inside": "a", "of": "canvas", "in": … }` | `a`'s box stays inside the canvas, part `of`'s box, or `[x, y, w, h]` |
| `{ "apart": ["a", "b"], "in": … }` | the two boxes never overlap |
| `{ "still": "a", "in": "idle" }` | `a`'s box does not change |
| `{ "same": [0, "end"] }` | every channel has the same value at both times |
| `{ "visible": "a", "at": "end" }`, `{ "hidden": "a", "at": 0 }` | `a` is drawn with opacity above 0.02, or not, at that time |

Always checked without an entry: a looping score looks the same at its end
as at 0; clips fit inside `duration`; a visible part leaving the canvas is
flagged in the report.

## Motion

- One focal move per beat. Stagger 0.04–0.15s instead of moving everything at once.
- Entrances 0.3–0.6s, exits shorter, idle loops 2–6s per cycle.
- In a looping score, every part that enters must also leave, or start visible.
