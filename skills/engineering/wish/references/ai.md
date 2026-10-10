# AI mode — a plan a stranger can carry out

Load in `ai` mode. The reader does exactly what the file says and has nothing else to go on, so say
more rather than less. Fill [ai-template.md](ai-template.md); match the density and tone of
[ai-example.md](ai-example.md). Save as `docs/YY-MM-DD-<slug>.md`.

The template is shaped for software. For other work keep its spine (TL;DR, goals, finished look,
steps with "done when", acceptance, risks) and mark the code-only parts `N/A — <reason>`.

## Tier

Once scope is settled, estimate hours and files touched; write it in the header's `Estimate` row.

- **Lite** — under half a day or fewer than 3 files: §5–7 merge into one Design section, §10 shrinks to
  one line (mechanics in the template's notes). [ai-example.md](ai-example.md) is a Lite plan.
- **Full** — everything else, and any data migration, auth, payments, or public-API change regardless of size.

## Writing

- Scale with §Tier, never by silently dropping a section — one that doesn't apply says `N/A — <reason>`.
- Say each thing once; every sentence carries a path, a number, a behaviour, or a decision. No preamble
  ("This document describes…"), no closing summary — TL;DR is the only summary.
- Real paths only; files that don't exist yet are marked `(new)`. No invented API presented as existing.
- Numbers over adjectives: "fast" → "p95 < 200 ms"; "large export" → "≤ 50k rows".
- Every FR maps to ≥1 acceptance criterion; every step has a "done when".
- Decisions carry their reason; rejected alternatives get one line each.
- Web UI wish with `web-layout` installed → write §Finished look from its Frame + Plan block
  (frame, density, focal point, ASCII wireframe).

## Gate (cold reader)

Someone who has read nothing but this file can answer:

- [ ] Why build it, for whom, and what is explicitly out?
- [ ] What does the finished thing look like — wireframe, example I/O, or sample output?
- [ ] Which files change and which appear — with real paths?
- [ ] In what order to build, and how to verify each step?
- [ ] When is it done — is every acceptance criterion testable?
- [ ] No undefined jargon; no TBD without an owner in Open questions; no "as discussed" pointing at the chat.
- [ ] Cut test: outside TL;DR, deleting any sentence loses a fact.

## Ban

- "A clean, modern UI" with no wireframe or example
