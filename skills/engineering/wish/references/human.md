# Human mode — a page people read

Load in `human` mode. The reader is a person whose attention is the scarce thing: they review, decide,
or need to understand, and will not carry it out themselves. Say less rather than more. **Write JSON only,
never HTML**; the template renders it.

| File | Role |
|---|---|
| `assets/doc.schema.json` | The contract. Every `description` is a writing rule; read them all before writing. |
| [human-example.json](human-example.json) | A passing document. Calibrate density and tone on it, not topic or language. |
| `assets/build.py` | Validates the JSON and embeds it in `assets/template.html`. |
| `assets/embed.mjs` | Fallback when python3 is missing: embeds the same way, checks nothing. |

## Reader

- Default: smart, knows the domain, was not in this conversation, doesn't know the details (code,
  systems, earlier threads). Adjust from signals in the request or context ("给老板看", "for the new
  hire"); never ask. Write it into `reader`.
- The main text is written for that reader and stays terse. What they may not know goes into `terms`
  (side notes beside the line), marked `[[term]]` at its first use.
- What they would misread without noticing goes into a `check` (answer hidden until clicked), right
  after the passage it tests.

## Shape

Unless the task clearly needs another order:

1. `summary` — the conclusion: what gets done, the scope, the cost.
2. `decisions` — what the reader must decide; the first option is the recommendation, with its cost.
   Omit when nothing is open.
3. `h2` sections, titled in the user's language: why → what it looks like (what's out included) → how
   (options considered included) → risks and costs → steps and timeline.

## Writing

- Every block carries a fact, a number, or a decision. Numbers over adjectives.
- Decisions carry their reason; rejected options get one line.
- Point to the source (file, doc, link) instead of restating what it says.
- Usually fewer than the caps: `terms` ≤ 8, `check` ≤ 4, `decisions` ≤ 4.
- Aim for ≤ 8 minutes of reading (build.py prints the estimate). Longer → cut detail or split the task.
- `lang`: `zh-CN` for Chinese content, `en` for anything else. Omit `$schema` in docs/.

## Build

```bash
python3 <skill dir>/assets/build.py docs/YY-MM-DD-<slug>.json    # writes the .html next to it
```

Exit 1 lists every problem: fix the JSON, never the template. No dependencies: it checks the whole
schema, then terms, option groups, and table cells.

No python3: `node <skill dir>/assets/embed.mjs docs/YY-MM-DD-<slug>.json` embeds the JSON the same
way but checks nothing, so open the page and fix whatever it lists at the top. No node either: copy
`assets/template.html` to the `.html` path and replace the line
`<script type="application/json" id="doc-data">null</script>` with the JSON inside the same tag,
writing every `<` in the JSON as `\u003c` (JSON reads it back as `<`; a raw `</script>` in the
content would end the tag early).

## Gate

build.py passes (without Python: the page lists no problems at the top), and:

- [ ] The summary is a conclusion a busy reader could act on without reading further.
- [ ] Each decision's first option is one you would defend; its `why` has a number or a fact.
- [ ] Each term is something the stated reader plausibly doesn't know, not jargon you could avoid.
- [ ] Each check targets a likely misreading and its answer surprises a skimmer. A long answer means
      the passage needs fixing.
- [ ] Cut test: deleting any block loses a fact, a number, or a decision.

## Report

The `.html` path first (that's what people open), then the `.json` (what gets edited), the summary,
and the open decisions.
