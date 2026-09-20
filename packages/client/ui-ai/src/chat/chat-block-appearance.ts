/**
 * 聊天块的入场判定与 ID 收集。
 *
 * 职责：
 *   区分「这轮刚出现的块」和「历史 / 虚拟滚动重挂载的块」，让入场动画只给新块。
 *
 * 设计说明：
 *   - ID 集合由 Chat 持有；ChatTurn 卸载不会丢历史，滚动回来不会重新播放。
 *   - 子会话里的块也一并登记，避免同一 id 在不同层级拿到不一致的动画判断。
 */

import type { ChatBlock, ChatTurn } from "./types";

/**
 * 收集一轮或多轮里的全部块 id。
 *
 * # Arguments
 *
 * * `turns` - 聊天轮次
 *
 * # Returns
 *
 * 所有块 id；子会话块会递归收集
 */
export function collectChatBlockIds(turns: ChatTurn[]): Set<string> {
  const ids = new Set<string>();

  const addBlock = (block: ChatBlock) => {
    ids.add(block.id);
    if (block.kind === "child") block.blocks.forEach(addBlock);
  };

  for (const turn of turns) {
    if (turn.user) ids.add(turn.user.id);
    turn.blocks.forEach(addBlock);
  }

  return ids;
}
