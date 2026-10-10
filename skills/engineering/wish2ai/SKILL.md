---
name: wish2ai
description: >-
  Write a plan to hand to an AI agent to carry out (写方案交给 AI 执行). Use
  when the user wants a plan, spec, or task brief that Codex, Cursor, Claude
  Code, or another agent will work from (给 AI 看 / 让 AI 照着做 / 交给 agent),
  or runs /wish2ai. Reads the context, asks only what changes the plan, then
  writes a self-contained Markdown plan that a reader with no context can
  carry out (docs/YY-MM-DD-{slug}.md). Plans only; never does the work.
---
# Wish → AI

Run the `wish` skill in **ai** mode on this request, skipping its mode detection.

It is installed next to this one: read `../wish/SKILL.md` and follow it; its paths are relative to
`../wish/`. If that file is missing, tell the user this command needs the `wish` skill installed
alongside it, and stop.
