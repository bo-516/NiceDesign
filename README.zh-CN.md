[English](README.md) | **中文**

# NiceDesign

精简、规则向的 Agent Skills：Web UI（颜色与深度、布局、交互、GSAP 优先的动画）+ 工程化（动手前先写方案 + 派活给另一个 agent 并审查）。少废话，多规则。

## 如何下载 / 安装 Skill

需要 [Node.js](https://nodejs.org/) 18+。不必全局安装 CLI，用 `npx` 即可临时执行。

### 1. 安装整包（推荐）

```bash
npx skills add https://github.com/bo-516/NiceDesign
```

简写：

```bash
npx skills add bo-516/NiceDesign
```

CLI 会列出全部八个 skill（Web UI 4 个 + 工程化 4 个），询问要装到哪些 Agent（Cursor、Claude Code、Codex 等），然后写入对应目录。

### 2. 只装某一个 Skill

```bash
npx skills add bo-516/NiceDesign --skill web-color-depth
npx skills add bo-516/NiceDesign --skill web-layout
npx skills add bo-516/NiceDesign --skill web-interaction
npx skills add bo-516/NiceDesign --skill web-animation
npx skills add bo-516/NiceDesign --skill wish
npx skills add bo-516/NiceDesign --skill wish --skill wish2human --skill wish2ai
npx skills add bo-516/NiceDesign --skill elder
```

`--skill` 后面写 skill 名即可，不用带分类目录。`wish2human`、`wish2ai` 只是 `wish` 的入口，要和 `wish` 一起装。

### 3. 项目级 vs 全局

| 范围 | 命令 | 落盘位置 |
|------|------|----------|
| 仅当前仓库（默认） | `npx skills add bo-516/NiceDesign` | 如 `.cursor/skills/`、`.claude/skills/` |
| 本机所有项目 | `npx skills add bo-516/NiceDesign -g` | 如 `~/.cursor/skills/`、`~/.claude/skills/` |

跳过交互（适合 CI / 脚本）：

```bash
npx skills add bo-516/NiceDesign --all -y
```

### 4. 手动安装（不用 CLI）

```bash
git clone https://github.com/bo-516/NiceDesign.git
```

把 `skills/` 下各分类里的 skill 文件夹拷到对应 Agent 的 skills 目录：

| Agent | 项目级 | 全局 |
|-------|--------|------|
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.codex/skills/` | `~/.codex/skills/` |
| GitHub Copilot | `.github/skills/` | — |

以 Cursor 项目级为例：

```bash
cp -R NiceDesign/skills/web/web-layout .cursor/skills/web-layout
cp -R NiceDesign/skills/engineering/wish .cursor/skills/wish
cp -R NiceDesign/skills/engineering/wish2human .cursor/skills/wish2human
cp -R NiceDesign/skills/engineering/wish2ai .cursor/skills/wish2ai
cp -R NiceDesign/skills/engineering/elder .cursor/skills/elder
```

仓库里的 `web/`、`engineering/` 只是分类目录。拷贝时拷具体的 skill 文件夹，不要整个分类目录一起拷：Agent 只扫描 skills 目录下一层，`.cursor/skills/web/web-layout/` 这样多套一层就识别不到了。

每个 skill 必须是「文件夹 + `SKILL.md`」，不要把文件摊平。
`web-layout`、`wish`、`elder` 的文件夹里还有 `references/`、`assets/`、`scripts/`、`agents/` 等子目录，`SKILL.md` 会按需读取，请整个文件夹一起拷贝。

### 5. 更新 / 卸载

```bash
npx skills update          # 拉最新版本
npx skills list            # 查看已安装
npx skills remove web-layout
```

如果 `npx skills update` 没拉到新版本，重新执行一次 `npx skills add bo-516/NiceDesign` 即可覆盖安装。

适用于 Cursor、Claude Code、Codex 等支持 [Agent Skills](https://agentskills.io) 格式的工具。

## 技能

### Web UI · 界面（`skills/web/`）

| Skill | 适合做什么 |
|-------|------------|
| [`web-color-depth`](skills/web/web-color-depth/SKILL.md) | 定配色、搭颜色 token 和暗色模式，给卡片、菜单、弹窗配合适的阴影层级 |
| [`web-layout`](skills/web/web-layout/SKILL.md) | 搭落地页、仪表盘、应用壳：页面骨架、间距、栅格、响应式，以及该让哪块区域滚动 |
| [`web-interaction`](skills/web/web-interaction/SKILL.md) | 让按钮、输入框、表单好用：悬停、聚焦、加载、报错等状态，点击反馈，不拖沓的过渡 |
| [`web-animation`](skills/web/web-animation/SKILL.md) | 加动效：入场动画、滚动触发、固定与视差，在 React 里用 GSAP 不泄漏、不卡顿 |

### 工程化 · Engineering（`skills/engineering/`）

| Skill | 适合做什么 |
|-------|------------|
| [`wish`](skills/engineering/wish/SKILL.md) | 动手之前先想清楚：新功能、重构、运营活动、流程改版都适用。先读现有材料、只问关键问题，再写成能评审、能交接的方案；默认写给人看，也能写给 AI 执行 |
| [`wish2human`](skills/engineering/wish2human/SKILL.md) | 出一份同事看得懂、老板能拍板的方案：结论放最前，每个待决事项都附带建议，术语旁边就有解释 |
| [`wish2ai`](skills/engineering/wish2ai/SKILL.md) | 出一份丢给 AI 就能开工的方案：交给 Codex、Cursor、Claude Code，每一步做到什么算完、怎么验收都写在里面，不用来回追问 |
| [`elder`](skills/engineering/elder/SKILL.md) | 两个 agent 搭档干活，参考 Devin Fusion：你的 agent 当 elder（远古者），负责规划、拍板、审查；shoggoth（修格斯）负责动手，它是另一个 agent CLI（Antigravity、Codex、Cursor、Claude Code、Grok Build 都行），模型随意。第一次用时会问你用哪个 shoggoth、什么模型和思考强度，这就是全部配置，之后用 `/elder config` 修改。shoggoth 的权限和你的 agent 一致：你配的允许、询问、拒绝规则和审批模式同样管它，该问的才问，问题都回到你和 elder 的对话里，仓库内越出范围的改动跑完后会标出来；每一轮都拿 git diff 和 shoggoth 自己的日志核对，编出来的「测试通过」会被抓出来。只能手动调用（`/elder`，Codex 里是 `$elder`），agent 不会自己触发 |

用法：

```text
/wish 给订单列表加导出 CSV            # 默认：给人看
/wish 双十一会员召回活动              # 不写代码的事也行
/wish 给订单列表加导出 CSV，交给 AI 做  # 切到给 AI 的版本
/wish2human 新人入职流程改版
/wish2ai 给订单列表加导出 CSV
```

两种模式共用前半段：

1. 先读上下文：在代码仓库里读 README、依赖清单、目录结构、相关模块和已有 `docs/`；不在仓库里就读你指给它的文件、链接和笔记。材料能回答的不问。
2. 信息不够时只问内容，不问形式（给谁看、写多深、用哪种模式都有默认值）：每轮最多 4 个问题、最多 2 轮，每题 3–5 个选项，推荐项排第一；也可以直接回答「你定」。
3. 文档语言跟随你的输入；之后的补充说明会更新同一份文档（修订号 +1，记一行变更），不会另起新文件。

**给人看（默认）**：生成 `docs/YY-MM-DD-<slug>.html`，单个文件，浏览器直接打开，发给别人也能直接看。页面：

- 结论放最前，「需要你决定」的事每项都带建议和成本。
- 术语在右侧边注里解释，和正文对齐；窄屏点开看。
- 自检题点击才显示答案，专门针对最容易读错的地方。
- 可收起的目录带阅读进度；可调字号、行距、字距、字体；浅色 / 深色跟随系统，也可手动切换。

**交给 AI 执行**：生成 `docs/YY-MM-DD-<slug>.md`，零上下文也能照着做：目标、成品、每一步做到什么算完、怎么验收、有哪些风险都写清楚。小改动写得短；涉及数据迁移、鉴权、支付或公开 API 的写得更完整。

只出方案，不动手做：不写代码、不发消息、不发布。

**/elder：远古者指挥，修格斯干活**

命名由来：elder 和 shoggoth 对应 Devin Fusion 里的 lead 和 sidekick，名字出自洛夫克拉夫特的《疯狂山脉》。远古者（Elder Things）造出修格斯（shoggoth）替自己盖城，没人盯着，修格斯就造了反。所以这里 shoggoth 只管干活，越出 brief 的事都要你点头。AI 圈也爱把大模型画成戴着笑脸面具的修格斯。

只能手动调用：`/elder`（Codex 里是 `$elder`）。agent 不会根据对话自己触发它。

```text
/elder 给订单列表加导出 CSV                  # 用默认的 shoggoth
/elder 用 flash 把 moment 换成 dayjs         # 这一次换个模型
/elder docs/26-09-23-export-orders-csv.md    # 照 /wish2ai 的方案做
/elder config                                # 换 CLI、模型、思考强度
/elder config effort high                    # 只改一项
```

1. 你的 agent 当 elder：读材料、拆分工、写简报（brief）。需要拍板的事，比如产品和接口设计、安全相关的逻辑，以及最终验收，都留给它自己。
2. shoggoth 是另一个跑在 headless 模式下的 agent CLI：Antigravity（agy）、Codex、Cursor、Claude Code、Grok Build，模型随便配。同一个 CLI 换个模型也行，比如 Codex Astra 当 elder、Codex 6.1 Sol 当 shoggoth。
3. 唯一的配置就是选 shoggoth，而且不用手写：第一次用 `/elder` 时，elder 会先问你用哪个 CLI（只列本机装了的），再按这个 CLI 问模型和思考强度。每题推荐项排第一，最后一项可以自己输入。答完存成默认配置，之后用 `/elder config` 修改。elder 就是你正在用的 agent，不用配。
4. 权限不用另外配置，shoggoth 直接沿用你的 agent 自己的权限设置（全局加项目，agy、Claude Code、Codex、Cursor、Grok Build 都支持）：
   - 写 `.git/` 和 hook 文件一律拒绝。
   - 你配的拒绝规则直接拒，询问规则问你，允许规则放行。
   - 你的 agent 设成不问（agy `always-proceed`、Claude Code `bypassPermissions`、Codex `never` 加完全访问、Cursor `unrestricted`、Grok Build always-approve），shoggoth 也不问；设成从不问、直接拒（`dontAsk`），该问的就直接拒。
   - 其余情况，仓库内的读写、只读命令（`ls`、`git status`、`rg` 等），以及你批准过的命令，直接放行。「这个任务都允许」只放行一字不差的同一条命令，参数一变就再问。
   - Codex 当 shoggoth 时，在自己的沙箱里（只能写仓库、不能联网）跑命令不经过审批，只有想出沙箱时才过这一关。
   - 别的命令、仓库外的文件、联网、MCP 工具，shoggoth 都会停下来等你，elder 在主会话里问你「允许一次 / 这个任务都允许 / 拒绝」。拒绝时可以附一句话给 shoggoth，它会照着改做法。
   - 仓库内越出 brief 范围的改动不会被拦下，跑完在摘要里标出来。
   - 派活前，elder 会把要跑的验证命令列出来，让你一次批完，后面只有意外情况才会打扰你。
   - 不想审批，就把 `permissions` 设成 `full`。Grok Build 暂时没有审批这道门，只能这样跑，选它时会先跟你确认。
5. 每一轮结束，`scripts/shoggoth.py` 会给一份摘要：
   - 以 git diff 为准列出实际改了什么、有没有越界。
   - shoggoth 报告里说「通过」的检查，会拿去和它自己的命令日志核对，没跑过的、跑挂了的都会标出来。
   - 你批了什么、拒了什么。
   - 最后附一行撤销命令（只读的侦察 run 没有）。
6. 改得不对，就带着反馈回到同一个会话继续改；两轮还不行，或者它理解错了意图，elder 收回来自己做。不 commit、不 push。

## 理念

- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **两类** — `web/`：颜色/深度 · 布局 · 交互 · 动画（阴影归入颜色）。`engineering/`：留下产物的工作流 skill，比如方案，或 shoggoth 做完、elder 验过的改动。
- Web 类从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## 许可

[MIT](LICENSE)
