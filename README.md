# NiceDesign

Short, rule-only agent skills for web UI — color & depth, layout, interaction, GSAP-first animation. Less fluff. More rules.

精简、规则向的 Web UI Agent Skills：颜色与深度、布局、交互、GSAP 优先的动画。少废话，多规则。

## Install · 安装

```bash
npx skills add https://github.com/bo-516/NiceDesign
```

Works with Cursor, Claude Code, Codex, and other agents that support the Agent Skills format.

适用于 Cursor、Claude Code、Codex 等支持 Agent Skills 格式的工具。

## Skills · 技能

| Skill | EN | 中文 |
|-------|----|------|
| [`web-color-depth`](skills/web-color-depth/SKILL.md) | Palettes, OKLCH tokens, dark mode, layered shadows / elevation | 色板、OKLCH token、暗色模式、分层阴影与 Elevation |
| [`web-layout`](skills/web-layout/SKILL.md) | Spacing scale, grids, hierarchy, app shells, composition bans | 间距阶、栅格、层次、应用壳、构图禁令 |
| [`web-interaction`](skills/web-interaction/SKILL.md) | Control states, forms, micro-feedback, CSS motion budgets | 控件八态、表单、微反馈、CSS 动效预算 |
| [`web-animation`](skills/web-animation/SKILL.md) | GSAP-first timelines, ScrollTrigger, React cleanup, perf | GSAP 优先：时间线、ScrollTrigger、React 清理、性能 |

## Philosophy · 理念

- **Rules over essays** — keep context small; ship decisions, not process theater.
- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **One pack, four lenses** — color/depth · layout · interaction · animation. Shadows live with color (elevation).
- **一套四视角** — 颜色/深度 · 布局 · 交互 · 动画。阴影归入颜色（Elevation）。
- Distilled from community & official sources (frontend-design, ui-craft, taste-skill, impeccable, greensock/gsap-skills, DESIGN.md, and others) into compact rule packs.
- 从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## License · 许可

MIT
