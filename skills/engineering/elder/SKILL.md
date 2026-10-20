---
name: elder
description: >-
  Hand hands-on work to a worker agent CLI (the shoggoth: agy, Codex, Cursor,
  Claude Code, or Grok Build); you, the elder, plan, decide, and review.
  `/elder config` changes the shoggoth's CLI, model, or effort. Approvals come
  back to this chat; each round is checked against the git diff and the
  shoggoth's log.
disable-model-invocation: true
---
# Elder

**Terms**

- **elder**: you. You plan, make the judgment calls, review, and talk to the
  user.
- **shoggoth**: a worker agent CLI, run headless by `scripts/shoggoth.py`. It
  does the hands-on work.
- **brief**: everything the shoggoth knows about a task. See
  [references/brief.md](references/brief.md).
- **run**: one brief sent to the shoggoth.
- **session**: the shoggoth's conversation across runs.
- `shog` means `python3 <this skill>/scripts/shoggoth.py` (Windows: `py -3`
  or `python` for `python3`). Paths are relative to this skill.
- **This skill's folder**: if your host didn't say, check these with your
  file tools, in order, and don't search the disk: `~/.agents/skills/elder`,
  `~/.claude/skills/elder`, `~/.gemini/config/skills/elder`,
  `~/.grok/skills/elder`, `~/.cursor/skills/elder`, then `.agents/`,
  `.claude/`, `.cursor/` in the repo. On Windows `~` is `%USERPROFILE%`.

**Input**:

- A task, or a plan file. In a `/wish2ai` plan, each step becomes a brief with
  that step's Done when; the plan's acceptance criteria and Manual check become
  your final acceptance run.
- `config`, with or without a change named after it → follow
  [references/setup.md](references/setup.md).
- A question about the code (what's here, how it works) → answer it yourself,
  and say no shoggoth ran.
- Empty → ask what to work on.

## Setup

- The only setting is the shoggoth (CLI, model, effort) for your host; you are
  never configured.
- Pass `--elder <host>` on every call: Claude Code → `claude`, Codex → `codex`,
  Cursor → `cursor`, Antigravity → `agy`, Grok Build → `grok`; any other agent
  → its own lowercase name.
- The user's words can override the shoggoth for one run:
  `--shoggoth agy:gemini-3.8-flash` (the CLI's default effort).
- `shog` writes `~/.config/shoggoth/` and starts a CLI that needs the network;
  if your sandbox blocks either, ask the user to allow running it outside.

## Approvals

In the default `ask` mode, a gate decides each tool call, and the shoggoth gets
your permissions: the gate reads your host's own settings, global and project,
and applies them in this order.

1. **Always refused**: writes to `.git/` and the hook files, and agy's own
   subagent, commit, and deploy tools.
2. **Your rules**: deny rules refuse, ask rules wait for the user, allow rules
   pass.
3. **Your mode**:
   - Runs without asking (agy `always-proceed`, Claude Code
     `bypassPermissions`, Codex `never` with full access, Cursor
     `unrestricted`, Grok Build always-approve) → the rest passes.
   - Never asks, refuses instead (`dontAsk`, Codex `never` in a sandbox) →
     what would wait is refused.
4. **Otherwise**: reads and edits inside the repo, plain read-only commands
   (`ls`, `git status`, `rg`…), and exactly approved commands pass. Other
   commands, paths outside the repo, network, and MCP wait for the user.

`shog doctor --elder <you>` shows what the gate read. As a shoggoth, Codex
runs commands inside its sandbox (repo-only writes, no network) without the
gate, which sees only escape attempts. Grok Build has no gate.

`shog run` or `shog wait` exits 4 when a call is waiting. Then:

1. Ask the user, quoting the request: one question per request, up to 4 per
   AskUserQuestion call in Claude Code. Options: Allow once / Allow for this
   task / Deny. Recommend Deny for anything irreversible or outside the brief.
2. Run `shog answer RUN ID allow|deny`. "Allow for this task" adds `--always`:
   it approves exactly that command line; any variation asks again.
   `--note "…"` reaches the shoggoth only with a deny.
3. Run `shog wait RUN`.

Rules:

- Only the user answers requests.
- `permissions: full` (in the config, or `--permissions full`) removes the
  gate. Use it only on the user's word. Grok Build runs only with `full`.

## Flow

0. **Shoggoth**: run `shog config show`. No entry for you and no `default` →
   `references/setup.md` first. Its model sets the split and the brief detail
   (§Style in brief.md).
1. **Scope**: read only what planning needs; leave the rest for the shoggoth.
2. **Split** (§Split): show it as a short table.
3. **Brief**: one per coherent unit of work, planned, never "figure out what
   to do". Then list their Verify commands and ask the user once; pass the
   approved ones with `--allow` on every run of the task.
4. **Dispatch** (§Dispatch): answer requests as they come.
5. **Review** (§Review) every round: accept, send feedback, or take over.
6. **Report** (§Report).

## Split

**Keep** (elder):
- The plan, and the contracts between pieces.
- The user's intent.
- Anything where the judgment is the deliverable: UX and product calls, public
  API, data model, security- or money-sensitive logic, migrations.
- Changes smaller than their brief would be.
- Anything irreversible or outside the repo: push, deploy, publish, real data,
  secrets.
- Reading that informs your decisions or answers the user. A summary of it
  can't be checked against a diff, so verifying it costs as much as reading.
- The review, and the final acceptance run.

**Send** (shoggoth):
- Building a design that is already settled. Reading for it is part of the
  brief: give paths, and it finds the call sites itself.
- Mechanical changes across many files.
- Tests from cases you list.
- Lint, type, and build fixes.
- Running slow suites and fixing what fails.
- Fact gathering too big to read yourself (`--scout`), when the answer is a
  `path:line` list that one search you can re-run checks for gaps. Open-ended
  "understand X" stays with you, whatever the model.

## Dispatch

```bash
shog run --brief FILE|- --elder NAME [--allow CMD]... [--session ID] [--scope GLOB]... [--scout] [--timeout 30m]
```

- **Exit codes**: 0, the summary is printed. 4, a request is waiting. 3, still
  running after `--max` (default 9m): `shog wait RUN` with the printed `RUN=`.
  1, an error; "no shoggoth set" → `references/setup.md`, then run again.
- On any other error, on `FAILED`, or on the first run of a CLI other than agy:
  read [references/shoggoths.md](references/shoggoths.md) (per-CLI setup,
  behavior, failures), and check the summary against `git diff` by hand.
- **Claude Code**: run it in the background; act on the completion notice,
  don't poll.
- **Brief**: on stdin (`--brief -`) or as a file outside the repo, never in the
  repo. On Windows use a file: a PowerShell pipe can mangle non-ASCII text.
- **`--scope`** takes the brief's "may change" globs. Changes anywhere else are
  flagged.
- **Follow-ups**: pass `--session ID` from the summary. The context and the
  "this task" approvals carry over. A new workstream gets a new session.
- **Checkout**: one writing shoggoth at a time. Scouts may run alongside it; a
  scout summary has no undo line, and the changes it lists may be the writer's.
- **Taking over**: `shog stop RUN`.

## Review

Trust the git diff over the shoggoth's log, and the log over its report.

1. Each flag is a failed check; clear it from the diff or a re-run before
   accepting. On `GATE_BYPASSED`, stop and tell the user.
2. Read the diff of the changed files. Judge it against the brief's decisions
   and Done when, and weigh `concerns`.
3. Mid-way, re-run only the checks the log doesn't show exiting 0. Run the full
   acceptance once, at the end.
4. Decide:
   - **Accept** → the next brief.
   - **Feedback** → a brief on the same session. Give each problem as
     `path:line`: what's wrong → what's expected, plus what to keep. Answer the
     report's `questions` in it.
   - **Take over** → after two failed rounds on one problem, a misread intent,
     or a fix that needs judgment. A writer's undo line reverts a bad round.

## Cost

- Briefs point to paths. Never put file contents, secrets, or this
  conversation in one.
- Don't redo or polish the shoggoth's work; brief it instead.
- Review from the summary and the diff, not whole files. Read the event log
  only to debug.

## Report

In the user's language, cover:

- What changed, and who did it: sent, kept, or taken over, and why.
- The acceptance commands you ran, and their results. Never pass a shoggoth's
  claim on as verified.
- The approvals given.
- Shoggoth runs and tokens.
- Open questions, and follow-ups.

Don't commit, push, or deploy the shoggoth's work unless the user asked.
