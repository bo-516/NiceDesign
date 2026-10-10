---
name: wish2ai
description: >-
  Use when the user runs /wish2ai with a task. The wish planning flow fixed
  to AI mode: reads the repo, asks only what changes the plan, then writes a
  self-contained Markdown plan an agent or engineer can build from cold
  (docs/YY-MM-DD-{slug}.md). Same as /wish without mode detection. Plans
  only; never implements.
---
# Wish → AI

Run the `wish` skill in **ai** mode on this request, skipping its mode detection.

It is installed next to this one: read `../wish/SKILL.md` and follow it; its paths are relative to
`../wish/`. If that file is missing, tell the user this command needs the `wish` skill installed
alongside it, and stop.
