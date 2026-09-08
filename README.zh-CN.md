[English](README.md) | **中文**

# NiceDesign

精简、规则向的 Web UI Agent Skills：颜色与深度、布局、交互、GSAP 优先的动画。少废话，多规则。

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

CLI 会列出四个 skill，询问要装到哪些 Agent（Cursor、Claude Code、Codex 等），然后写入对应目录。

### 2. 只装某一个 Skill

```bash
npx skills add bo-516/NiceDesign --skill web-color-depth
npx skills add bo-516/NiceDesign --skill web-layout
npx skills add bo-516/NiceDesign --skill web-interaction
npx skills add bo-516/NiceDesign --skill web-animation
```

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

把 `skills/` 下的各个文件夹拷到对应 Agent 的 skills 目录：

| Agent | 项目级 | 全局 |
|-------|--------|------|
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.codex/skills/` | `~/.codex/skills/` |
| GitHub Copilot | `.github/skills/` | — |

以 Cursor 项目级为例：

```bash
cp -R NiceDesign/skills/web-layout .cursor/skills/web-layout
```

每个 skill 必须是「文件夹 + `SKILL.md`」，不要把文件摊平。

### 5. 更新 / 卸载

```bash
npx skills update          # 拉最新版本
npx skills list            # 查看已安装
npx skills remove web-layout
```

适用于 Cursor、Claude Code、Codex 等支持 [Agent Skills](https://agentskills.io) 格式的工具。

## 技能

| Skill | 覆盖内容 |
|-------|----------|
| [`web-color-depth`](skills/web-color-depth/SKILL.md) | 色板、OKLCH token、暗色模式、分层阴影与 Elevation |
| [`web-layout`](skills/web-layout/SKILL.md) | 间距阶、栅格、层次、应用壳、构图禁令 |
| [`web-interaction`](skills/web-interaction/SKILL.md) | 控件八态、表单、微反馈、CSS 动效预算 |
| [`web-animation`](skills/web-animation/SKILL.md) | GSAP 优先：时间线、ScrollTrigger、React 清理、性能 |

## 理念

- **规则重于长文** — 控制上下文体积；交付可执行决策，而不是流程表演。
- **一套四视角** — 颜色/深度 · 布局 · 交互 · 动画。阴影归入颜色（Elevation）。
- 从社区与官方来源提炼压缩而成（含 frontend-design、ui-craft、taste-skill、impeccable、greensock/gsap-skills、DESIGN.md 等）。

## 许可

[MIT](LICENSE)
