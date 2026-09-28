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

CLI 会列出全部五个 skill（Web UI 4 个 + 工程化 1 个），询问要装到哪些 Agent（Cursor、Claude Code、Codex 等），然后写入对应目录。

### 2. 只装某一个 Skill

```bash
npx skills add bo-516/NiceDesign --skill web-color-depth
npx skills add bo-516/NiceDesign --skill web-layout
npx skills add bo-516/NiceDesign --skill web-interaction
npx skills add bo-516/NiceDesign --skill web-animation
npx skills add bo-516/NiceDesign --skill wish
```

`--skill` 后面写 skill 名即可，不用带分类目录。

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
```

仓库里的 `web/`、`engineering/` 只是分类目录。拷贝时拷具体的 skill 文件夹，不要整个分类目录一起拷：Agent 只扫描 skills 目录下一层，`.cursor/skills/web/web-layout/` 这样多套一层就识别不到了。

每个 skill 必须是「文件夹 + `SKILL.md`」，不要把文件摊平。
`web-layout` 带一个 `references/` 目录（landing / dashboard / shell 配方），`wish` 带 `references/template.md`（方案文档骨架）和 `references/example.md`（精简档样例），`SKILL.md` 会按需加载，请整个文件夹一起拷贝。

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
| [`wish`](skills/engineering/wish/SKILL.md) | 一句话需求 → 零上下文也能照做的开发方案：背景、目标 / 非目标、成品形态（线框 / 示例 I/O）、需求、技术设计、实施步骤、测试验收、风险；小任务自动用精简档；另带 `references/template.md` 骨架和 `references/example.md` 样例 |

用法：

```text
/wish 给订单列表加导出 CSV
```

1. 先读仓库（README、依赖清单、目录结构、相关模块、已有 `docs/`），代码能回答的不问。
2. 目标默认从需求和代码推断，受众或动机不清时才问。信息不够时反问：每轮最多 4 个问题、最多 2 轮，每题 3–5 个选项，推荐项排第一；也可以直接回答「你定」。
3. 按规模分档：预估不到半天或改动少于 3 个文件用精简档（成品形态、需求、技术设计合成一节，上线只留一行）；涉及数据迁移、鉴权、支付或公开 API 的一律用完整档。
4. 写入 `docs/YY-MM-DD-<slug>.md`，例如 `docs/26-09-23-export-orders-csv.md`；文档语言跟随你的输入。
5. 之后的补充说明会更新同一个文件（Revision +1，并记一行 Changelog），不会另起新文件。

只出方案，不写代码。

## 理念

- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **两类** — `web/`：颜色/深度 · 布局 · 交互 · 动画（阴影归入颜色）。`engineering/`：留下产物的工作流 skill，比如开发方案。
- Web 类从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## 许可

[MIT](LICENSE)
