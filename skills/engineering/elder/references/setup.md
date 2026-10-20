# Setup

Use this when `shog config show` lists no entry for you and no `default`, when
`shog run` says "no shoggoth set", or when the user runs `/elder config`. The
setting is the shoggoth's CLI, model, and effort for the agent you run in.
Don't ask about your own model.

## Questions

There are two rounds, because the model options depend on the CLI. Each
question has 2–4 options.

1. **CLI.** Run `shog doctor --elder <you>`.
   - Offer up to 4 installed CLIs, in recommended order. Give each option one
     line: what it is, and its gate.
   - One installed → skip this round and name it. None → say what to install,
     and stop.
   - If the user types a CLI that isn't installed, save it, and say it must be
     installed and signed in before the first run.
2. **Model and effort, in one call.** Run `shog models <cli>`.
   - **Model**: the recommended pick, marked "(Recommended)", then up to 3
     others from the CLI's list, a cheaper one and a stronger one first when
     they're listed. Fewer than 2 options → add "CLI default" (save without
     `--model`).
   - **Effort**: the recommended level plus up to 3 others. Skip this for
     Cursor, whose model id sets the effort.
3. **Grok Build only**: confirm that it gets no approvals and runs with full
   permissions. Yes → save with `--permissions full`. No → back to step 1.
4. **Save**: `shog config set --elder <you> --cli … --model … --effort …`.
   A model the CLI doesn't list is saved with a warning.
5. **Tell the user in one line** what's saved, and that `/elder config` changes
   it. Add the doctor's `permissions` line: the shoggoth follows their own
   settings, and in a mode that never asks, it won't ask either. Then resume
   the task.

## Recommending

- **CLI**: agy first, since its gate is the only one tested end to end; then
  codex, claude, cursor; grok last, since it has no gate.
  - A CLI from another vendor adds a second opinion.
  - The same CLI on a cheaper model also works.
- **Model and effort**: use the pick `shog models` prints. Don't default to the
  smallest model. For mostly mechanical work, offer the fast model second.

## Asking

- **Claude Code**: use AskUserQuestion. Its "Other" is the typing slot.
- **No choice UI**: number the options, and end with "or type your own".
- **Labels**: the id plus "(Recommended)" or "(current)". Put the one-line
  reason in the description.
- **Language**: the user's. Ids stay verbatim.

## /elder config

- **No change named**: run `shog config show`, then both rounds. The
  recommended option stays first; mark the current one "(current)".
- **A change named** ("用 flash", "effort high", "换成 codex"): pass only that
  flag, such as `shog config set --elder <you> --effort high`. `config set`
  merges into the existing entry; a new `--cli` starts it fresh, so ask round 2
  again.
- **"删掉" or "重置"**: run `shog config unset --elder <you>`.
- **Another agent's setting** ("Codex 那边用 sol"): pass that agent as
  `--elder`.
