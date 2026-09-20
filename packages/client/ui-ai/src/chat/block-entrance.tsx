/**
 * 聊天块入场包装器。
 *
 * 职责：
 *   给真正新增的块播一次入场动画，并保证父级重渲染不会中途取消动画。
 *
 * 设计说明：
 *   - `active` 只在首次渲染读取；之后 Chat 会把 id 写入已见集合，包装器不能因此丢动画。
 *   - 历史块和虚拟滚动重挂载的块 active=false，因此不会反复闪动。
 */

import type { ReactNode } from "react";
import { useState } from "react";
import { cn } from "@v2/ui-primitives/utils";

interface BlockEntranceProps {
  active: boolean;
  children: ReactNode;
}

/** 包裹一个聊天块；是否播放入场动画只在挂载时决定。 */
export function BlockEntrance({ active, children }: BlockEntranceProps) {
  const [animate] = useState(active);

  return <div className={cn("min-w-0", animate && "chat-block-enter")}>{children}</div>;
}
