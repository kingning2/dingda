/**
 * 一轮对话。
 *
 * 职责：
 *   渲染「一条用户消息 + 其后全部助手块」—— 虚拟滚动与 sticky 分区的最小单位。
 *
 * 设计说明：
 *   - 用户块与助手块各包一层：两者上下间距不同（`py-2` vs `space-y-4 py-3`），
 *     这是原有视觉约定，不是冗余嵌套。
 *   - 助手块为空时留一个 `h-2` 占位：否则虚拟项测量高度会是 0，滚动会跳。
 *   - 阶段裁剪只作用于助手块；用户块永远原样渲染。
 *   - 阶段裁剪只作用于助手块；用户块永远原样渲染。
 */

import { blocksForPhase } from "./schedule";
import { ChatBlock } from "./chat-block";
import { BlockEntrance } from "./block-entrance";
import type { AgentRunPhase } from "@v2/ui-agent/run/phase";
import type { ChatRenderContext, ChatTurn as ChatTurnData } from "./types";
import type { ReactNode } from "react";
/** 一轮对话：用户消息 + 助手消息（含时间线与块序列）。 */
export function ChatTurn({
  turn,
  runPhase,
  context,
  status = null,
  newBlockIds = null,
}: {
  turn: ChatTurnData;
  runPhase: AgentRunPhase | null;
  context: ChatRenderContext;
  /** 当前轮尾部状态；只有最末活动轮由 Chat 传入。 */
  status?: ReactNode | null;
  /** 本轮里还没登记过的块 id；历史块不在这个集合里。 */
  newBlockIds?: Set<string> | null;
}) {
  const assistantBlocks = blocksForPhase(turn.blocks, runPhase);

  return (
    <section className="relative">
      {turn.user ? (
        <div className="py-2">
          <ChatBlock block={turn.user} context={context} />
        </div>
      ) : null}
      {assistantBlocks.length > 0 ? (
        <div className="space-y-4 py-3">
          {assistantBlocks.map((block) => (
            <BlockEntrance
              key={block.id}
              active={Boolean(newBlockIds?.has(block.id))}
            >
              <ChatBlock block={block} context={context} />
            </BlockEntrance>
          ))}
          {status ? <BlockEntrance active={Boolean(status)}>{status}</BlockEntrance> : null}
        </div>
      ) : (
        status ? <div className="py-3">{status}</div> : <div className="h-2" aria-hidden />
      )}
    </section>
  );
}
