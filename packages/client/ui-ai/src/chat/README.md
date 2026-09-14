# `chat/` —— 聊天记录

左侧聊天面板的全部实现。**这里不出现任何具体块的名字** —— 块通过注册表解析。

## 文件

| 文件 | 职责 | 关键符号 |
|------|------|----------|
| `types.ts` | 块的数据形状与渲染契约，纯类型 | `ChatBlock` / `ChatTurn` / `ChatBlockProps` / `ChatRenderContext` |
| `registry.ts` | 「块类型 → 块组件」映射 | `registerBlock` / `resolveBlock` |
| `schedule.ts` | 后端消息 → 渲染轮次（纯函数） | `scheduleTurns` / `scheduleMessage` / `blocksForPhase` |
| `chat-block.tsx` | 注册表的**唯一消费点**；副作用导入 `../blocks` | `ChatBlock` |
| `chat-turn.tsx` | 一轮：用户块 + 其后助手块 | `ChatTurn` |
| `working-status.tsx` | Codex 风格状态行与 `└` 详情推导 | `WorkingIndicator` / `resolveWorkingDetails` |
| `use-sticky-and-follow.ts` | sticky 分区索引 + 是否跟随底部 | `useStickyAndFollow` |
| `chat.tsx` | 面板本体：轮次 + 虚拟滚动 + 装配输入框 | `Chat` |

## 加一个聊天块（四步，零处改 `Chat`）

```tsx
// 1. 新建 packages/client/ui-ai/src/blocks/browser-frame.tsx
import { registerBlock } from "../chat/registry";
import type { ChatBlockProps } from "../chat/types";

export function BrowserFrameBlock({ block }: ChatBlockProps<"browserFrame">) {
  return <img src={block.screenshotUrl} alt={block.title} />;
}

// 2. 文件末尾自注册
registerBlock("browserFrame", BrowserFrameBlock);
```

```ts
// 3. chat/types.ts —— ChatBlock 联合加一支
| { kind: "browserFrame"; id: string; title: string; screenshotUrl: string }
```

```ts
// 4. blocks/index.ts —— 加一行副作用导入
import "./browser-frame";
```

完成后 `Chat`、`registry`、`chat-block` 都不用改。

## 两个容易踩的坑

**① 副作用导入不能删。**
块的注册发生在**模块加载时**。`chat-block.tsx` 顶部那行 `import "../blocks"`
是唯一让块文件被加载的地方 —— 删了它，所有块都不会注册，
表现是每条消息都渲染成「未知块类型」。加了新块但忘了改 `blocks/index.ts`
也是同样的症状，所以未注册时渲染的是**可见占位**而不是静默跳过。

**② `blocks/index.ts` 不 re-export 块组件。**
要渲染块就走 `resolveBlock`。直接 import 具体块会把「谁认识哪个块」重新散出去，
注册表就白做了。

## 与 `blocks/` 的分工

- `chat/` —— **怎么排**：轮次切分、阶段裁剪、虚拟滚动、状态行、注册表
- `blocks/` —— **怎么画**：4 个块各自的 DOM 与交互

`chat/` 不 import 任何具体块；`blocks/` 只 import `chat/registry` 与 `chat/types`。
方向是单向的。

## 为什么用注册表而不是一张 `BLOCKS` 表

改之前 `scheduler.tsx` 里有一张写死的 `BLOCKS` 映射 + 一个 `switch`，
加块类型要改同一个 1122 行文件的两处。现在加块只碰「新建块文件 + 装配点一行」，
且分派只剩 `chat-block.tsx` 里的 `<Block block={block} context={context} />` 一行。
