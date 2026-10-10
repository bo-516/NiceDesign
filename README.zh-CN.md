[English](README.md) | **中文**

# NiceDesign

精简、规则向的 Agent Skills：Web UI（颜色与深度、布局、交互、GSAP 优先的动画）+ 工程化（开发方案）。少废话，多规则。

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

CLI 会列出全部七个 skill（Web UI 4 个 + 工程化 3 个），询问要装到哪些 Agent（Cursor、Claude Code、Codex 等），然后写入对应目录。

### 2. 只装某一个 Skill

```bash
npx skills add bo-516/NiceDesign --skill web-color-depth
npx skills add bo-516/NiceDesign --skill web-layout
npx skills add bo-516/NiceDesign --skill web-interaction
npx skills add bo-516/NiceDesign --skill web-animation
npx skills add bo-516/NiceDesign --skill wish
npx skills add bo-516/NiceDesign --skill wish --skill wish2human --skill wish2ai
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
```

仓库里的 `web/`、`engineering/` 只是分类目录。拷贝时拷具体的 skill 文件夹，不要整个分类目录一起拷：Agent 只扫描 skills 目录下一层，`.cursor/skills/web/web-layout/` 这样多套一层就识别不到了。

每个 skill 必须是「文件夹 + `SKILL.md`」，不要把文件摊平。
`web-layout` 带一个 `references/` 目录（landing / dashboard / shell 配方），`wish` 带 `references/`（两种模式的写作规则、Markdown 骨架和两份样例）和 `assets/`（HTML 模板、JSON Schema、`build.py`），`SKILL.md` 会按需加载，请整个文件夹一起拷贝。

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

| Skill | 覆盖内容 |
|-------|----------|
| [`web-color-depth`](skills/web/web-color-depth/SKILL.md) | 色板、OKLCH token、暗色模式、分层阴影与 Elevation |
| [`web-layout`](skills/web/web-layout/SKILL.md) | 骨架选择（视口锁定 / 文档滚动）、滚动归属、间距阶、栅格、层次、应用壳；另带 `references/` 场景配方 |
| [`web-interaction`](skills/web/web-interaction/SKILL.md) | 控件八态、表单、微反馈、CSS 动效预算 |
| [`web-animation`](skills/web/web-animation/SKILL.md) | GSAP 优先：时间线、ScrollTrigger、React 清理、性能 |

### 工程化 · Engineering（`skills/engineering/`）

| Skill | 覆盖内容 |
|-------|----------|
| [`wish`](skills/engineering/wish/SKILL.md) | 一句话需求 → 开发方案。默认写给人看；要求「给 AI 看」时写给 AI 照做 |
| [`wish2human`](skills/engineering/wish2human/SKILL.md) | 固定写给人看：由 JSON 渲染的单文件 HTML |
| [`wish2ai`](skills/engineering/wish2ai/SKILL.md) | 固定写给 AI 照做：零上下文也能照着实现的 Markdown 方案 |

用法：

```text
/wish 给订单列表加导出 CSV          # 默认：给人看
/wish 给订单列表加导出 CSV，给 AI 看  # 切到给 AI 的版本
/wish2human 给订单列表加导出 CSV
/wish2ai 给订单列表加导出 CSV
```

两种模式共用前半段：

1. 先读仓库（README、依赖清单、目录结构、相关模块、已有 `docs/`），代码能回答的不问。
2. 信息不够时只问内容，不问形式（给谁看、写多深、用哪种模式都有默认值）：每轮最多 4 个问题、最多 2 轮，每题 3–5 个选项，推荐项排第一；也可以直接回答「你定」。
3. 文档语言跟随你的输入；之后的补充说明会更新同一份文档（修订号 +1，记一行变更），不会另起新文件。

**给人看（默认）**：AI 只写 JSON（按 `assets/doc.schema.json`），`build.py` 校验后嵌进模板，生成 `docs/YY-MM-DD-<slug>.html`，JSON 源文件放在旁边。页面：

- 结论放最前，「需要你决定」的事每项都带建议和成本。
- 术语在右侧边注里解释，和正文对齐；窄屏点开看。
- 自检题点击才显示答案，专门针对最容易读错的地方。
- 可收起的目录带阅读进度；可调字号、行距、字距、字体；浅色 / 深色跟随系统，也可手动切换。

**给 AI 照做**：写入 `docs/YY-MM-DD-<slug>.md`。按规模分档：预估不到半天或改动少于 3 个文件用精简档；涉及数据迁移、鉴权、支付或公开 API 的一律用完整档。

只出方案，不写代码。

## 理念

- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **两类** — `web/`：颜色/深度 · 布局 · 交互 · 动画（阴影归入颜色）。`engineering/`：留下产物的工作流 skill，比如开发方案。
- Web 类从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## 许可

[MIT](LICENSE)
