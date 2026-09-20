/**
 * 子会话块：父消息时间线里嵌套折叠的 worker 详情。
 *
 * 职责：
 *   渲染一个派出的子会话 —— 头部是角色 / 状态徽标 / 当前动作，展开是子会话自己的
 *   步骤、思考与正文，收尾后附最终摘要。
 *
 * 设计说明：
 *   - 子块内部的块由 `schedule.ts` 排好放在 `block.blocks` 里，本组件只负责**摆放**：
 *     分派仍然只发生在 ChatBlock 一处（本文件 import 的是 dispatch 而不是 chat-block，
 *     否则会绕成 `blocks/child → chat-block → blocks/index → blocks/child` 的加载环）。
 *   - 只读：子会话不接受用户输入，父会话才是对话的那一方。
 *   - 文件末尾自注册，Chat 通过注册表取用，不认识本组件。
 */

import { Bot } from "lucide-react";
import { Badge } from "@v2/ui-primitives/badge";
import { cn } from "@v2/ui-primitives/utils";
import { Collapse } from "./collapse";
import { CodexActivityIndicator } from "./thinking-orb";
import { ChatBlock } from "../chat/dispatch";
import { registerBlock } from "../chat/registry";
import type { ChatBlockProps } from "../chat/types";

function ChildBlock({ block, context }: ChatBlockProps<"child">) {
  const { child, blocks, streaming } = block;

  const title = (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      {streaming ? (
        <CodexActivityIndicator className="w-3.5 shrink-0 text-[13px] text-sky-600" />
      ) : (
        <Bot className="size-3.5 shrink-0 text-muted-foreground/70" />
      )}
      <span className="min-w-0 truncate">
        <span className="font-medium text-foreground/90">{child.label || child.role}</span>
        {/* 当前动作文案由服务端下发；派工刚受理时还没有，不占位 */}
        {child.step ? <span className="text-muted-foreground"> · {child.step}</span> : null}
      </span>
    </span>
  );

  const trailing = (
    <Badge
      className={cn("h-auto shrink-0 rounded-full border-transparent text-[10px]", child.status.badge_class)}
    >
      {child.status.label}
    </Badge>
  );

  return (
    <Collapse
      testId="child-block"
      title={title}
      trailing={trailing}
      // 跑着自动摊开：用户要看的正是「子会话在干什么」；
      // 结束后不再干预（传 undefined 而不是 false），免得刚跑完就自己合上。
      lifecycleOpen={streaming ? true : undefined}
      // 展开体缩进一条，视觉上表达「这是父会话里的嵌套一层」
      bodyClassName="border-l border-border/70 pl-2.5"
    >
      <div className="space-y-1.5">
        {blocks.map((item) => (
          <ChatBlock key={item.id} block={item} context={context} />
        ))}
        {/* 摘要只在收尾后有：它是服务端在终态时写入的，运行中恒为空 */}
        {!streaming && child.summary ? (
          <p
            data-testid="child-summary"
            className="rounded-md bg-muted/40 px-2 py-1.5 text-[12px] whitespace-pre-wrap text-foreground/80"
          >
            {child.summary}
          </p>
        ) : null}
      </div>
    </Collapse>
  );
}

registerBlock("child", ChildBlock);
