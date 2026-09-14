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
 *   - 那行 `import "../blocks"` 是**副作用导入，不能删**：块的注册发生在模块加载时，
 *     没人 import `blocks/index.ts` 就等于一个块都没注册。放在这里是因为本文件是
 *     注册表的唯一消费点 —— 「渲染块之前，先确保块都注册好了」。
 */

import "../blocks";
import { resolveBlock } from "./registry";
import type { ChatBlock as ChatBlockData, ChatRenderContext } from "./types";

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
