---
name: wish2human
description: >-
  Write a plan for people to read, review, or decide on (写方案给人看). Use
  when the plan is for a teammate, lead, reviewer, or stakeholder (方案评审 /
  给老板或同事看 / 让人拍板), or the user runs /wish2human. Reads the context,
  asks only what changes the plan, then writes a single-page HTML doc
  rendered from JSON: decisions with recommendations up front, side notes for
  terms, hidden-answer self-checks (docs/YY-MM-DD-{slug}.html + .json). Plans
  only; never does the work.
---
# Wish → human

Run the `wish` skill in **human** mode on this request, skipping its mode detection.

It is installed next to this one: read `../wish/SKILL.md` and follow it; its paths are relative to
`../wish/`. If that file is missing, tell the user this command needs the `wish` skill installed
alongside it, and stop.
