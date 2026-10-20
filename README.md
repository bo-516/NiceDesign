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
| [`elder`](skills/engineering/elder/SKILL.md) | Two agents on one job, the way Devin Fusion pairs them: your agent is the elder and plans, decides, and reviews, while a shoggoth, a worker agent CLI on any model (Antigravity, Codex, Cursor, Claude Code, or Grok Build), does the hands-on work. The first run asks which shoggoth, model, and effort to use, and that's the whole setup; `/elder config` changes it. The shoggoth gets your agent's permissions: your own allow, ask, and deny rules and your approval mode apply to it, so it asks only where your agent would, and those requests come back to your conversation with the elder; scope breaks inside the repo are flagged afterwards. Every round is checked against the git diff and the shoggoth's own log, so a made-up "tests pass" gets caught. It runs only when you call it (`/elder`, or `$elder` in Codex); agents never start it on their own | 两个 agent 搭档干活，参考 Devin Fusion：你的 agent 当 elder（远古者），负责规划、拍板、审查；shoggoth（修格斯）负责动手，它是另一个 agent CLI（Antigravity、Codex、Cursor、Claude Code、Grok Build 都行），模型随意。第一次用时会问你用哪个 shoggoth、什么模型和思考强度，这就是全部配置，之后用 `/elder config` 修改。shoggoth 的权限和你的 agent 一致：你配的允许、询问、拒绝规则和审批模式同样管它，该问的才问，问题都回到你和 elder 的对话里；每一轮都拿 git diff 和 shoggoth 自己的日志核对，编出来的「测试通过」会被抓出来。只能手动调用（`/elder`，Codex 里是 `$elder`），agent 不会自己触发 |

`wish2human` and `wish2ai` are entry points into `wish`; install `wish` alongside them.
`wish2human` / `wish2ai` 只是 `wish` 的入口，需要和 `wish` 一起安装。

```text
/wish 给订单列表加导出 CSV
→ 导出范围？ A. 当前筛选结果 (Recommended)  B. 全部订单  C. 勾选的行 …
→ docs/26-09-23-export-orders-csv.html

/wish2ai 给订单列表加导出 CSV
→ docs/26-09-23-export-orders-csv.md

/elder docs/26-09-23-export-orders-csv.md
→ 用哪个 shoggoth 干活？ A. agy (Recommended)  B. codex  C. grok …（只在第一次问）
→ 分工：接口和列格式 elder 定，实现和测试交给 shoggoth（agy · gemini-4-argon · medium）
→ shoggoth 想运行 `pnpm add csv-stringify`：允许一次 / 这个任务都允许 / 拒绝 (Recommended)
→ shoggoth run 01 · flags: none · changes: 3 files · checks: pnpm vitest exit 0
```

**Why elder and shoggoth** — They stand in for Devin Fusion's lead and sidekick. In Lovecraft's *At the Mountains of Madness*, the Elder Things bred shoggoths to build their cities, and the shoggoths, left unwatched, rose against them. So here the shoggoth does the labor, and anything past its brief needs your yes. AI people also draw a large model as a shoggoth wearing a smiley-face mask.
**命名由来** — 对应 Devin Fusion 里的 lead 和 sidekick。出自洛夫克拉夫特的《疯狂山脉》：远古者（Elder Things）造出修格斯（shoggoth）替自己盖城，没人盯着，修格斯就造了反。所以这里 shoggoth 只管干活，越出 brief 的事都要你点头。AI 圈也爱把大模型画成戴着笑脸面具的修格斯。

## Philosophy · 理念

- **Rules over essays** — keep context small; ship decisions, not process theater.
- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **Two shelves** — `web/`: color/depth · layout · interaction · animation (shadows live with color). `engineering/`: workflow skills that leave an artifact behind, such as a plan, or a change a shoggoth made and the elder checked.
- **两类** — `web/`：颜色/深度 · 布局 · 交互 · 动画（阴影归入颜色）。`engineering/`：留下产物的工作流 skill，比如方案，或 shoggoth 做完、elder 验过的改动。
- Web skills are distilled from community & official sources (frontend-design, ui-craft, taste-skill, impeccable, greensock/gsap-skills, DESIGN.md, and others) into compact rule packs.
- Web 类从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## License · 许可

MIT
