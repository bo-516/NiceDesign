---
name: wish2ai
description: >-
  Write a development plan to hand to an AI agent (写开发计划交给 AI). Use when
  the user wants a plan, spec, or task brief that Codex, Cursor, Claude Code,
  or another agent will build from (给 AI 看 / 让 AI 照着做 / 交给 agent 开发),
  or runs /wish2ai. Reads the repo, asks only what changes the plan, then
  writes a self-contained Markdown plan that a reader with no context can
  build from (docs/YY-MM-DD-{slug}.md). Plans only; never implements.
---
# Wish → AI

Run the `wish` skill in **ai** mode on this request, skipping its mode detection.

It is installed next to this one: read `../wish/SKILL.md` and follow it; its paths are relative to
`../wish/`. If that file is missing, tell the user this command needs the `wish` skill installed
alongside it, and stop.
