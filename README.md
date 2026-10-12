# NiceDesign

Short, rule-only agent skills — web UI craft plus engineering workflow. Less fluff. More rules.

精简、规则向的 Agent Skills：Web UI 设计 + 工程化工作流。少废话，多规则。

## Install · 安装

```bash
npx skills add https://github.com/bo-516/NiceDesign
```

Works with Cursor, Claude Code, Codex, and other agents that support the Agent Skills format.

适用于 Cursor、Claude Code、Codex 等支持 Agent Skills 格式的工具。

## Skills · 技能

### Web UI · 界面 — [`skills/web/`](skills/web)

| Skill | Use it for | 适合做什么 |
|-------|------------|------------|
| [`web-color-depth`](skills/web/web-color-depth/SKILL.md) | Picking a palette, setting up color tokens and dark mode, giving cards, menus, and modals the right shadow depth | 定配色、搭颜色 token 和暗色模式，给卡片、菜单、弹窗配合适的阴影层级 |
| [`web-layout`](skills/web/web-layout/SKILL.md) | Laying out a landing page, dashboard, or app shell: structure, spacing, grids, responsive behavior, and which area scrolls | 搭落地页、仪表盘、应用壳：页面骨架、间距、栅格、响应式，以及该让哪块区域滚动 |
| [`web-interaction`](skills/web/web-interaction/SKILL.md) | Making buttons, inputs, and forms feel right: hover, focus, loading, and error states, click feedback, snappy transitions | 让按钮、输入框、表单好用：悬停、聚焦、加载、报错等状态，点击反馈，不拖沓的过渡 |
| [`web-animation`](skills/web/web-animation/SKILL.md) | Adding motion: entrance animations, scroll-triggered effects, pinning and parallax, GSAP in React without leaks or jank | 加动效：入场动画、滚动触发、固定与视差，在 React 里用 GSAP 不泄漏、不卡顿 |

### Engineering · 工程化 — [`skills/engineering/`](skills/engineering)

| Skill | Use it for | 适合做什么 |
|-------|------------|------------|
| [`wish`](skills/engineering/wish/SKILL.md) | Thinking a task through before anyone starts: a new feature, a refactor, a campaign, a process change. It reads what's already there, asks only what matters, then writes a plan you can review or hand off — for people by default, or for an AI agent to carry out | 动手之前先想清楚：新功能、重构、运营活动、流程改版都适用。先读现有材料、只问关键问题，再写成能评审、能交接的方案；默认写给人看，也能写给 AI 执行 |
| [`wish2human`](skills/engineering/wish2human/SKILL.md) | Plans your team can follow and your lead can sign off on: the conclusion comes first, every open decision carries a recommendation, and jargon is explained right beside the text | 出一份同事看得懂、老板能拍板的方案：结论放最前，每个待决事项都附带建议，术语旁边就有解释 |
| [`wish2ai`](skills/engineering/wish2ai/SKILL.md) | Plans an agent can pick up and run with: hand one to Codex, Cursor, or Claude Code, and every step already says what done looks like and how to check it — no back-and-forth | 出一份丢给 AI 就能开工的方案：交给 Codex、Cursor、Claude Code，每一步做到什么算完、怎么验收都写在里面，不用来回追问 |

`wish2human` and `wish2ai` are entry points into `wish`; install `wish` alongside them.
`wish2human` / `wish2ai` 只是 `wish` 的入口，需要和 `wish` 一起安装。

```text
/wish 给订单列表加导出 CSV
→ 导出范围？ A. 当前筛选结果 (Recommended)  B. 全部订单  C. 勾选的行 …
→ docs/26-09-23-export-orders-csv.html

/wish2ai 给订单列表加导出 CSV
→ docs/26-09-23-export-orders-csv.md
```

## Philosophy · 理念

- **Rules over essays** — keep context small; ship decisions, not process theater.
- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **Two shelves** — `web/`: color/depth · layout · interaction · animation (shadows live with color). `engineering/`: workflow skills that leave an artifact behind, such as a plan.
- **两类** — `web/`：颜色/深度 · 布局 · 交互 · 动画（阴影归入颜色）。`engineering/`：留下产物的工作流 skill，比如方案。
- Web skills are distilled from community & official sources (frontend-design, ui-craft, taste-skill, impeccable, greensock/gsap-skills, DESIGN.md, and others) into compact rule packs.
- Web 类从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## License · 许可

MIT
