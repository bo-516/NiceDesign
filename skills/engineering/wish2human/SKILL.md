---
name: wish2human
description: >-
  Use when the user runs /wish2human with a task. The wish planning flow
  fixed to human mode: reads the repo, asks only what changes the plan, then
  writes a plan for people as a single-page HTML doc rendered from JSON
  (docs/YY-MM-DD-{slug}.html plus its .json). Same as /wish without mode
  detection. Plans only; never implements.
---
# Wish → human

Run the `wish` skill in **human** mode on this request, skipping its mode detection.

It is installed next to this one: read `../wish/SKILL.md` and follow it; its paths are relative to
`../wish/`. If that file is missing, tell the user this command needs the `wish` skill installed
alongside it, and stop.
