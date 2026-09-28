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

| Skill | EN | 中文 |
|-------|----|------|
| [`web-color-depth`](skills/web/web-color-depth/SKILL.md) | Palettes, OKLCH tokens, dark mode, layered shadows / elevation | 色板、OKLCH token、暗色模式、分层阴影与 Elevation |
| [`web-layout`](skills/web/web-layout/SKILL.md) | Frame choice (viewport-locked vs document-scroll), scroll ownership, spacing scale, grids, hierarchy, app shells | 骨架选择（视口锁定 / 文档滚动）、滚动归属、间距阶、栅格、层次、应用壳 |
| [`web-interaction`](skills/web/web-interaction/SKILL.md) | Control states, forms, micro-feedback, CSS motion budgets | 控件八态、表单、微反馈、CSS 动效预算 |
| [`web-animation`](skills/web/web-animation/SKILL.md) | GSAP-first timelines, ScrollTrigger, React cleanup, perf | GSAP 优先：时间线、ScrollTrigger、React 清理、性能 |

### Engineering · 工程化 — [`skills/engineering/`](skills/engineering)

| Skill | EN | 中文 |
|-------|----|------|
| [`wish`](skills/engineering/wish/SKILL.md) | `/wish <task>` → reads the repo, asks up to 4 multiple-choice questions when the request is thin, writes a dev plan a zero-context reader can build from to `docs/YY-MM-DD-<slug>.md` | `/wish <需求>` → 先读仓库，信息不够时带 3–5 个选项反问，在 `docs/YY-MM-DD-<slug>.md` 写出零上下文也能照做的开发方案 |

```text
/wish 给订单列表加导出 CSV
→ 导出范围？ A. 当前筛选结果 (Recommended)  B. 全部订单  C. 勾选的行 …
→ docs/26-09-23-export-orders-csv.md
```

## Philosophy · 理念

- **Rules over essays** — keep context small; ship decisions, not process theater.
- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **Two shelves** — `web/`: color/depth · layout · interaction · animation (shadows live with color). `engineering/`: workflow skills that leave an artifact behind, such as a dev plan.
- **两类** — `web/`：颜色/深度 · 布局 · 交互 · 动画（阴影归入颜色）。`engineering/`：留下产物的工作流 skill，比如开发方案。
- Web skills are distilled from community & official sources (frontend-design, ui-craft, taste-skill, impeccable, greensock/gsap-skills, DESIGN.md, and others) into compact rule packs.
- Web 类从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## License · 许可

MIT
