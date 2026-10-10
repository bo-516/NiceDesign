---
name: wish
description: >-
  Turn a request into a plan before anyone starts the work: a proposal, plan,
  or spec (方案 / 计划 / 提案 / 技术方案) for a feature, project, process change,
  campaign, event, or any task worth thinking through first. Use when someone
  asks for one or runs /wish. Writes for people by default: a single-page HTML
  doc rendered from JSON, with decisions up front, side notes for terms, and
  hidden-answer self-checks (docs/YY-MM-DD-{slug}.html + .json). Writes a
  self-contained Markdown plan instead when it is meant for an AI or agent to
  carry out (交给 AI / 给 AI 看 / 2ai). Reads the context first (the repo, or
  the files the user points to); asks at most 4 multiple-choice questions,
  only when the request is underspecified. Plans only; never does the work.
---
# Wish

A wish granted literally is a bug. Clarify first, then grant.

Rules only. The output is a file, not a chat essay. **Plan only — never do the work itself here: no
product code, nothing sent, nothing published.** Paths below are relative to this skill's directory.

**Input** = the text after the command (Claude Code appends it as `ARGUMENTS:`). Empty → ask what to plan,
offering 3–5 candidates read from the context (README roadmap, TODO/FIXME, recent commits, the user's notes).

Works for any role: engineering, product, design, ops, marketing. In a code repo the plan is usually a
build; elsewhere it may be a launch, a process, a campaign, an event.

## Mode

| Mode | Reader | Output | Rules |
|---|---|---|---|
| `human` (default) | People who review, decide, or need to understand; their attention is scarce | `docs/YY-MM-DD-<slug>.json` → `.html` | [references/human.md](references/human.md) |
| `ai` | An agent (or person) who will carry it out cold, without this conversation | `docs/YY-MM-DD-<slug>.md` | [references/ai.md](references/ai.md) |

- `/wish2human` → `human`; `/wish2ai` → `ai`. No detection.
- `/wish` → `human`, unless the plan is for an agent to carry out: "for AI / an agent / Codex / Cursor",
  "交给 AI", "给 AI 看", "让 AI / agent 照着做", "2ai", "markdown plan". Never ask which mode; name it in
  the report.
- A follow-up keeps the mode of the file it edits.

## Flow

1. **Read** — the context. In a repo: README, manifests (`package.json`, `pyproject.toml`, `go.mod`…),
   tree to depth 2, the modules the wish touches, existing `docs/`. Otherwise: the files, links, and
   notes the user points to. Tools, vendors, or APIs the plan leans on: check current docs if a web
   tool exists. Skim, don't audit. Never ask what the material answers.
2. **Gap check** — mark every row of §Sufficiency `known` / `inferred` / `unknown`.
3. **Ask** — only `unknown` rows that change the approach, the scope, or the finished look (§Asking).
   Everything else becomes an assumption in the doc. Nothing to ask → write straight away.
4. **Write** — load the mode's rules file and follow it; save per §File.
5. **Gate** — run the mode's gate; fix the doc until it passes.
6. **Report** — path, ≤5-line summary, open decisions / questions, the mode used. Offer the next step;
   don't start it.

**Follow-ups** ("补充…", "also…", answers to open questions) → edit the same file (human: the `.json`,
then rebuild), bump the revision, add a changelog line. User approves → `approved` / `Confirmed`.
New file only for a different task.

## Sufficiency

| # | Dimension | Unknown → ask when |
|---|---|---|
| 1 | Goal & audience — the problem, who it's for, why now | the audience or the motive is unclear (default: infer it from the wish and the context) |
| 2 | Scope — first version in, explicitly out | the wish fits more than one size |
| 3 | Finished look — what the result is: a screen, an API, a file, a page, an event, a process | more than one plausible form |
| 4 | Means — stack, tools, channels, people | the context doesn't settle it |
| 5 | Inputs & dependencies — data, systems, other teams, approvals | implied but unnamed |
| 6 | Done — acceptance criteria, success metric | not derivable from 1–3 |
| 7 | Constraints — deadline, budget, compliance, security, performance, accessibility | the domain makes it load-bearing |

## Asking

- Ask only when the answer changes the approach, the scope, or the finished look — content, never form.
  Who reads it, how deep, what tone, which mode: defaults, corrected after the draft.
- ≤4 questions per round, ≤2 rounds; every question of a round in one message.
- Each question: **3–5 concrete options**, the recommended one first, marked `(Recommended)` with a
  one-line why. A free-text answer is always accepted.
- Options are real alternatives grounded in the context ("reuse `src/api/client.ts`" vs "a new SDK
  wrapper"; "the existing newsletter list" vs "a new segment"), never yes / no / other.
- Native choice UI if the agent has one (Claude Code `AskUserQuestion`: give 3–4 options; its
  automatic Other takes the free-text answer); otherwise numbered questions with options A–E in chat.
- "You decide" / "你定" / "skip" → take every recommendation and record each as an assumption.
- Too big for one doc (several independent parts, weeks of work) → make "how to split" one of the
  questions; plan slice 1 in full, list the rest as later phases.

## File

- Path: `<git root>/docs/YY-MM-DD-<slug>.<ext>`; create `docs/` if missing; outside a repo, use the
  working directory.
- Date: today, local time, two-digit year — run `date +%y-%m-%d` if unsure.
  Example: `docs/26-09-23-export-orders-csv.html`.
- Slug: 2–5 words, lowercase ASCII kebab-case, English even when the doc isn't.
- Name taken: same task → update that file; different task → append `-2`.
- User named a path or file name → theirs wins.
- Language: the user's, headings included; code, paths, and identifiers stay verbatim.

## Ban

- Doing the work while planning: writing product code, sending messages, buying, publishing
- Asking what the context already answers; yes/no questions; >4 questions per round; asking about form
- Filler — "ensure good performance", "follow best practices", "improve the user experience", "boost
  engagement": give a number or delete it
- Invented files, APIs, numbers, or names presented as real
- Pasting the whole doc into chat
