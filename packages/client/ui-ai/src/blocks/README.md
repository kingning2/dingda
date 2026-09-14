# blocks/

聊天块与块级渲染基元。块按 `kind` 注册到 `chat/registry.ts`，由 `chat/chat-block.tsx` 统一分派。

## 块列表

| 文件 | kind | 说明 |
|------|------|------|
| `user.tsx` | `user` | 用户消息，含重发按钮 |
| `thinking.tsx` | `thinking` | 思考过程，默认折叠 |
| `step.tsx` | `step` | 工具调用结果（浏览/爬取/搜索/比对） |
| `text.tsx` | `text` | 助手正文 |

## 块级渲染基元

| 文件 | 说明 |
|------|------|
| `collapse.tsx` | Foldable：lifecycleOpen + 用户手点锁定 |
| `thinking-orb.tsx` | Codex 风格活动符 `•` |
| `use-reveal-text.ts` | 80ms 合并 + ~2s CharReveal；历史挂载即落定 |

## 加一个新块

1. 新建 `<kind>.tsx`，实现 `ChatBlockComponent<"<kind>">`。
2. 文件末尾 `registerBlock("<kind>", <Component>)`。
3. `index.ts` 加 `import "./<kind>"`（副作用导入，确保注册）。
4. `chat/chat-block.tsx` 的 `ChatBlock` 联合类型加 `"<kind>"`。

块组件只接收 `{ block, context }`，不直接碰 store 或路由。
