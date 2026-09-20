/**
 * 注册表分派：按 kind 取块组件渲染。
 *
 * 职责：
 *   把 ChatBlock 交给注册表里对应的块组件 —— 全仓唯一一处「块类型 → 组件」的分派。
 *
 * 设计说明：
 *   - 这里没有 switch：加块类型不需要改本文件，这是注册表相对硬编码表的核心收益。
 *   - 未注册时给**可见占位**而不是返回 null：静默跳过会让「漏注册」表现为
 *     「消息凭空少一段」，完全无从排查。
 *   - 本文件**故意不 import `../blocks`**（副作用导入在 chat-block.tsx 里）。
 *     子会话块自己也要渲染子块 → 它得用这个分派器；若分派器所在的模块一并
 *     触发 `blocks/index.ts`，就形成 `blocks/child → chat/dispatch → blocks/index
 *     → blocks/child` 的加载环，子在注册前被求值。拆成两层就没有环：
 *     只想渲染块的一方 import 这里，负责装配注册表的一方 import chat-block。
 */

import { resolveBlock } from "./registry";
import type { ChatBlock as ChatBlockData, ChatRenderContext } from "./types";

/** 块分派器：按 kind 从注册表取组件并渲染。 */
export function ChatBlock({
  block,
  context,
}: {
  block: ChatBlockData;
  context: ChatRenderContext;
}) {
  const Block = resolveBlock(block.kind);
  if (!Block) return <UnknownBlock kind={block.kind} />;
  return <Block block={block} context={context} />;
}

/** 未注册的块类型占位。故意做得显眼，便于发现漏注册。 */
function UnknownBlock({ kind }: { kind: string }) {
  return (
    <p className="rounded-md border border-dashed border-destructive/60 px-3 py-2 text-xs text-destructive">
      未知块类型：{kind}
    </p>
  );
}
