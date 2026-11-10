---
name: peek
description: >-
  Show a change before making it (先看效果再动手): an interactive before/after
  preview page (HTML; an SVG diagram for non-visual changes) built from the
  project's real code and assets. Nothing else is edited until the user says
  OK. Always use on /peek or "先给我看看效果 / 先看效果 / 先出预览 / show me
  first / preview it first". Also use unprompted before a large visible
  change: a page or section re-layout, a new screen, a new multi-state flow.
  Not for small edits: copy, a color, spacing, an icon.
---
# Peek

**Terms**

- **change**: what the user asked for.
- **preview**: one self-contained HTML file showing the change before and
  after. Built from `assets/shell.html` by the rules in
  [references/page.md](references/page.md).
- **product files**: every file except the preview.
- **state**: one frozen look of the changed region (idle, loading, error…).
- **variant**: a design decision still open, shown as a switch in the preview.
- **gate**: the stop between preview and build. Only the user's explicit OK
  passes it.

**Input**: the text after the command. Empty, and a change was just discussed
→ that change. Empty otherwise → ask what to change. Paths are relative to
this skill's folder.

## When

| | Change |
|---|---|
| Always | `/peek`; the user asks to see it first |
| On your own | Re-layout of a page or section. A new screen, modal, drawer, or step. A flow that adds ≥ 3 states. A restyle across ≥ 3 components. More than one plausible look, where a wrong guess costs more rework than a preview |
| Never on your own | Copy, a color, a spacing or size tweak, an icon swap, one prop. A change with nothing to see |

- On your own → say so in one line, then start at Read.
- "直接改 / just do it / skip" → no peek for this change.
- In between → no peek. Say in one line what will look different, then do it.

## Flow

1. **Read** — the code being changed, and how the project already does the
   same kind of thing (toasts, loaders, spacing, tokens, copy tone): count the
   call sites. Collect real assets, real copy, every locale touched.
2. **Preview** — write the preview. No product file is edited, nothing is
   installed, migrated, or generated.
3. **Show** — per §Show. End the turn with ≤ 5 lines: what to click, the
   guesses, the open variants. Ask for the OK.
4. **Gate** — wait.
   - OK ("ok / 可以 / 就这样 / go", or the reply line copied from the page) →
     Build. A variant the user didn't name → its recommended option.
   - Feedback → edit the same file, `rev` + 1, show again. Feedback is not OK.
   - A question → answer it. Still gated.
5. **Build** — implement the confirmed revision: every state, the chosen
   variants, nothing more. Something forces a visible difference (an API
   can't, a component lacks the prop) → stop, update the preview, gate again.
6. **Check** — run the project's checks. Then compare each state of the
   preview with the result: look at it if you have a browser or simulator
   tool, else compare the values in code. Report per state: match or
   deviation; then the files changed. Never report a match you didn't check.

## File

- Path: the host's artifact or scratch directory if it has one; else
  `<os temp dir>/peek/<slug>.html`. Inside the repo only when the user names
  a path.
- Slug: 2–5 words, lowercase ASCII kebab-case.
- One file per change. Revisions overwrite it.
- Page language: the user's. Code, paths, identifiers stay verbatim.

## Show

- The host renders HTML inline or in a pane (Antigravity `<agent-embed>`,
  Claude Code preview pane or artifact, Cursor browser) → use that. Where the
  host's own embedding rules (CSP, theming, size) conflict with page.md, the
  host's win.
- Otherwise open the file (`open` / `xdg-open` / `start`) and give its path.
- Never paste the HTML into chat.

## Ban

- Editing a product file before the gate passes
- Reading silence, feedback, or a question as OK
- A preview made after the change is built
- Invented assets, copy, or values shown as the project's; a guess not listed
  as a guess
- A static screenshot or prose description where the page could be clicked
- Peeking at a trivial edit nobody asked to see
