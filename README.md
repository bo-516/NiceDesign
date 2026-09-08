**English** | [中文](README.zh-CN.md)

# NiceDesign

Short, rule-only agent skills for web UI — color & depth, layout, interaction, GSAP-first animation. Less fluff. More rules.

## How to download / install

Requires [Node.js](https://nodejs.org/) 18+. No global install needed — `npx` runs the CLI once.

### 1. Install the whole pack (recommended)

```bash
npx skills add https://github.com/bo-516/NiceDesign
```

Shorthand:

```bash
npx skills add bo-516/NiceDesign
```

The CLI lists the four skills, asks which agents to target (Cursor, Claude Code, Codex, …), and copies them into the right directory.

### 2. Install one skill only

```bash
npx skills add bo-516/NiceDesign --skill web-color-depth
npx skills add bo-516/NiceDesign --skill web-layout
npx skills add bo-516/NiceDesign --skill web-interaction
npx skills add bo-516/NiceDesign --skill web-animation
```

### 3. Project vs global

| Scope | Command | Where it lands |
|-------|---------|----------------|
| This repo only (default) | `npx skills add bo-516/NiceDesign` | e.g. `.cursor/skills/`, `.claude/skills/` |
| All your projects | `npx skills add bo-516/NiceDesign -g` | e.g. `~/.cursor/skills/`, `~/.claude/skills/` |

Skip prompts (CI / scripts):

```bash
npx skills add bo-516/NiceDesign --all -y
```

### 4. Manual install (no CLI)

```bash
git clone https://github.com/bo-516/NiceDesign.git
```

Copy each folder under `skills/` into your agent's skills directory:

| Agent | Project | Global |
|-------|---------|--------|
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.codex/skills/` | `~/.codex/skills/` |
| GitHub Copilot | `.github/skills/` | — |

Example for Cursor (project):

```bash
cp -R NiceDesign/skills/web-layout .cursor/skills/web-layout
```

Each skill is a folder with a `SKILL.md`. Do not flatten the files.

### 5. Update / uninstall

```bash
npx skills update          # pull latest
npx skills list            # see what's installed
npx skills remove web-layout
```

Works with Cursor, Claude Code, Codex, and other agents that support the [Agent Skills](https://agentskills.io) format.

## Skills

| Skill | What it covers |
|-------|----------------|
| [`web-color-depth`](skills/web-color-depth/SKILL.md) | Palettes, OKLCH tokens, dark mode, layered shadows / elevation |
| [`web-layout`](skills/web-layout/SKILL.md) | Spacing scale, grids, hierarchy, app shells, composition bans |
| [`web-interaction`](skills/web-interaction/SKILL.md) | Control states, forms, micro-feedback, CSS motion budgets |
| [`web-animation`](skills/web-animation/SKILL.md) | GSAP-first timelines, ScrollTrigger, React cleanup, perf |

## Philosophy

- **Rules over essays** — keep context small; ship decisions, not process theater.
- **One pack, four lenses** — color/depth · layout · interaction · animation. Shadows live with color (elevation).
- Distilled from community & official sources (frontend-design, ui-craft, taste-skill, impeccable, greensock/gsap-skills, DESIGN.md, and others) into compact rule packs.

## License

[MIT](LICENSE)
