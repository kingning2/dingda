---
name: pi-hooks
description: pi（叮答主力编码 agent）的项目级扩展机制。要给本仓加 pi hook/extension、调 /命令（prompt template）、改 skill 加载位置、或排查扩展没生效时使用。含三种挂载点、事件面、本仓两个真实扩展示例与新增步骤。
---

# pi 扩展与 Hook 指南（.pi/）

## 1. 三个挂载点（本仓约定）

| 位置 | 是什么 | 生效方式 |
|------|--------|----------|
| `.pi/skills/<name>/SKILL.md` | 项目级 skill（本仓：py-dev、rs-dev、web-dev、pi-hooks） | 项目受信后启动自动发现；description 决定何时被加载 |
| `.pi/prompts/<name>.md` | prompt 模板，文件名即 `/命令` | frontmatter 可选 `description`、`argument-hint` |
| `.pi/extensions/<name>.ts` | 扩展（hook、自定义工具、自定义命令） | **自动发现**；`/reload` 热载；`pi -e ./path.ts` 仅用于快速调试 |

全局位置在 `~/.pi/agent/{skills,prompts,extensions}/`；本仓约定**项目级东西只放 `.pi/`**，
不再使用 `.cursor/`、`.agents/`（已删除，勿再创建）。

## 2. extension 事件面（`pi.on(event, handler)`）

| 事件组 | 典型事件 | 用途 |
|--------|----------|------|
| 启动/资源 | `session_start` / `session_shutdown` | 开资源、清资源 |
| 工具 | `tool_call` / `tool_result` | 拦截、改写、缓存工具调用与结果 |
| 回合 | `agent_settled` / `agent_start` | 回合结束兜底清理 |
| 输入/UI | input 事件、`ctx.ui`（select/confirm/input/notify） | 交互确认门 |
| 其他 | `bash` spawn hook、model 请求头、compaction 定制 | 命令改写、上下文定制 |

能力清单：`pi.registerTool()`（LLM 可调工具）、`pi.registerCommand()`（`/命令`）、
`pi.appendEntry()`（跨会话持久状态）、`ctx.ui.custom()`（复杂 TUI 组件）。

## 3. 本仓两个真实扩展（新增前先读）

| 文件 | 职责 | 用到的事件 |
|------|------|-----------|
| `.pi/extensions/simplify-ignore.ts` | `/* simplify-ignore-start */ … end */` 代码块在 read 前替换为占位符、edit/write 后展开，保护块不被简化 | `tool_call` `tool_result` `agent_settled` `session_shutdown` + `registerCommand("simplify-restore")` |
| `.pi/extensions/sdd-cache.ts` | 带 url 的工具调用前用 HTTP 304 语义（ETag/If-Modified-Since）复验本地缓存，命中则拦截返回缓存正文 | `tool_call` `tool_result` |

## 4. 新增一个 hook（四步）

1. 建 `.pi/extensions/<kebab-name>.ts`，入口形状照抄本仓实证：

```ts
// <kebab-name> —— 一句话职责。
// 职责：…  设计说明：… （照本仓文件头惯例，注明移植来源如有）
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

export default function myHook(pi: ExtensionAPI): void {
	pi.on("tool_call", async (event, ctx: ExtensionContext) => {
		// 返回 { block: true, reason } 可拦截调用
	});
	pi.registerCommand("my-command", { handler: async (ctx) => { ... } });
}
```

2. 缩进用 tab（与本仓两个扩展现状一致）。
3. `/reload` 热载验证；调试期可 `pi -e ./.pi/extensions/my-hook.ts`。
4. 写不动 TUI 交互时用 `ctx.ui.confirm()`，不要静默吞错误——扩展抛错会打断回合。

## 5. 注意项

- 扩展是**可执行代码**，会被无条件信任：只放本仓约定的守卫/缓存类扩展，不装来路不明的。
- `tool_call` 拦截要保持快（同步优先）；慢 IO 放 `tool_result` 之后异步落盘（sdd-cache 形状）。
- prompt 模板文件名即命令名：`review.md` → `/review`；`argument-hint` 用 `<必填>` `[可选]`。
- 改了 skill 的 frontmatter（name/description）需要重启会话，`/reload` 只对 extensions 生效。
