/**
 * 块渲染入口：装配注册表 + 转发分派器。
 *
 * 职责：
 *   副作用导入 `blocks/index.ts`（让所有块在模块加载时完成自注册），再把分派器转发出去。
 *
 * 设计说明：
 *   - 那行 `import "../blocks"` 是**副作用导入，不能删**：块的注册发生在模块加载时，
 *     没人 import `blocks/index.ts` 就等于一个块都没注册。放在这里是因为本文件是
 *     「聊天渲染」的入口 —— 「渲染块之前，先确保块都注册好了」。
 *   - 分派器本体在 `dispatch.tsx`（那里不触发注册表装配，子会话块要用它渲染子块）。
 *     两个文件别合并：合并出来的环见 dispatch.tsx 的注释。
 *   - 转发而不是让调用方直接 import dispatch：Chat 的两个消费点
 *     （chat.tsx / chat-turn.tsx）只 import 一处，装配注册表这件事就不会漏。
 */

import "../blocks";

export { ChatBlock } from "./dispatch";
