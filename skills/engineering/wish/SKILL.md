---
name: wish
description: >-
  Use when the user runs /wish with a task, or asks for a development plan,
  tech spec, or implementation plan (开发方案 / 技术方案) for a feature,
  refactor, bugfix, or new project. Reads the repo first, asks at most 4
  multiple-choice questions (3–5 options each) only when the request is
  underspecified, then writes a self-contained plan to docs/YY-MM-DD-{slug}.md
  (e.g. docs/26-09-23-export-orders-csv.md) that a reader with zero context can
  build from. Plans only; never implements.
---
# Wish

A wish granted literally is a bug. Clarify first, then grant: a plan a stranger can build from.

Rules only. The output is a file, not a chat essay. **Plan only — never write or edit product code here.**

**Input** = the text after `/wish` (Claude Code appends it as `ARGUMENTS:`). Empty → ask what to plan,
offering 3–5 candidates read from the repo (README roadmap, TODO/FIXME, recent commits).

## Flow

1. **Read** — README, manifests (`package.json`, `pyproject.toml`, `go.mod`…), tree to depth 2, the
   modules the wish touches, existing `docs/`. External APIs / libraries the plan leans on: check
   current docs if a web tool exists. Skim, don't audit. Never ask what the code answers.
2. **Gap check** — mark every row of §Sufficiency `known` / `inferred` / `unknown`.
3. **Ask** — only `unknown` rows that change architecture, scope, or the finished look (§Asking).
   Everything else becomes an assumption in the doc. Nothing to ask → write straight away.
4. **Write** — pick the tier (§Tier), fill [references/template.md](references/template.md), and match the
   density and tone of [references/example.md](references/example.md); save per §File.
5. **Gate** — run §Gate; fix the doc until it passes.
6. **Report** — path + ≤5-line summary + open questions. Offer the next step; don't start it.

**Follow-ups** (“补充…”, “also…”, answers to open questions) → edit the same file, bump `Revision`,
add a Changelog line. User approves → `Status: Confirmed`. New file only for a different task.

## Sufficiency

| # | Dimension | Unknown → ask when |
|---|---|---|
| 1 | Goal & users — the problem, who it's for, why now | the audience or the motive is unclear (default: infer it from the wish and the repo) |
| 2 | Scope — MVP in, explicitly out | the wish fits more than one size |
| 3 | Finished look — UI, API shape, CLI output, file format | more than one plausible form |
| 4 | Platform & stack | the repo doesn't settle it (greenfield) |
| 5 | Integrations & data — sources, auth, external systems | implied but unnamed |
| 6 | Done — acceptance criteria, success metric | not derivable from 1–3 |
| 7 | Non-functional — perf, security, compat, i18n, a11y | the domain makes it load-bearing |

## Asking

- Ask only when the answer changes architecture, scope, or the finished look.
- ≤4 questions per round, ≤2 rounds; every question of a round in one message.
- Each question: **3–5 concrete options**, the recommended one first, marked `(Recommended)` with a
  one-line why. A free-text answer is always accepted.
- Options are real alternatives grounded in the repo (“reuse `src/api/client.ts`” vs “new SDK
  wrapper”), never yes / no / other.
- Native choice UI if the agent has one (Claude Code `AskUserQuestion`: give 3–4 options; its
  automatic Other takes the free-text answer); otherwise numbered questions with options A–E in chat.
- “You decide” / “你定” / “skip” → take every recommendation and record each as an assumption.
- Too big for one doc (several independent subsystems, weeks of work) → make “how to split” one of
  the questions; plan slice 1 in full, list the rest as Phases.

## Tier

Once scope is settled, estimate hours and files touched; write it in the header's `Estimate` row.

- **Lite** — under half a day or fewer than 3 files: §5–7 merge into one Design section, §10 shrinks to
  one line (mechanics in the template's notes). [references/example.md](references/example.md) is a Lite plan.
- **Full** — everything else, and any data migration, auth, payments, or public-API change regardless of size.

## File

- Path: `<git root>/docs/YY-MM-DD-<slug>.md`; create `docs/` if missing; outside a repo, use the
  working directory.
- Date: today, local time, two-digit year — run `date +%y-%m-%d` if unsure.
  Example: `docs/26-09-23-export-orders-csv.md`.
- Slug: 2–5 words, lowercase ASCII kebab-case, English even when the doc isn't.
- Name taken: same task → update that file; different task → append `-2`.
- User named a path or file name → theirs wins.
- Language: the user's, headings included; code, paths, and identifiers stay verbatim.

## Writing

- Scale with §Tier, never by silently dropping a section — one that doesn't apply says `N/A — <reason>`.
- Say each thing once; every sentence carries a path, a number, a behaviour, or a decision. No preamble
  (“This document describes…”), no closing summary — TL;DR is the only summary.
- Real paths only; files that don't exist yet are marked `(new)`. No invented API presented as existing.
- Numbers over adjectives: “fast” → “p95 < 200 ms”; “large export” → “≤ 50k rows”.
- Every FR maps to ≥1 acceptance criterion; every step has a “done when”.
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
- [ ] No undefined jargon; no TBD without an owner in Open questions; no “as discussed” pointing at the chat.
- [ ] Cut test: outside TL;DR, deleting any sentence loses a fact.

## Ban

- Writing or editing product code while planning
- Asking what the repo already answers; yes/no questions; >4 questions per round
- Filler — “ensure good performance”, “follow best practices”, “improve the user experience”, “ensure scalability”: give a number
  or delete it
- “A clean, modern UI” with no wireframe or example
- Invented file paths or APIs presented as existing
- Pasting the whole doc into chat
