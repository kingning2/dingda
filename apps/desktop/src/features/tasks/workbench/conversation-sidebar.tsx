/**
 * 左侧会话栏 — 260px，绑定 agentStore。
 */

import { useMemo, useState } from "react";
import { Button, Input, ScrollArea } from "@desk/ui";
import { MessageSquarePlus, Search } from "@desk/ui/icons";
import { cn } from "@desk/ui/lib/cn";

import { useAgentStore } from "./agent-store";
import type { Conversation, ConversationStatus } from "../workbench/types";

function startOfDay(ms: number): number {
  const date = new Date(ms);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function groupConversations(items: Conversation[]) {
  const today = startOfDay(Date.now());
  const yesterday = today - 86_400_000;
  const groups: { label: string; items: Conversation[] }[] = [
    { label: "今天", items: [] },
    { label: "昨天", items: [] },
    { label: "更早", items: [] },
  ];
  for (const item of items) {
    if (item.updatedAt >= today) {
      groups[0]!.items.push(item);
    } else if (item.updatedAt >= yesterday) {
      groups[1]!.items.push(item);
    } else {
      groups[2]!.items.push(item);
    }
  }
  return groups.filter((group) => group.items.length > 0);
}

function statusDot(status: ConversationStatus) {
  switch (status) {
    case "running":
      return "bg-primary";
    case "completed":
      return "bg-emerald-500";
    case "error":
      return "bg-destructive";
    default:
      return "bg-muted-foreground/40";
  }
}

export function ConversationSidebar() {
  const conversations = useAgentStore((state) => state.conversations);
  const activeId = useAgentStore((state) => state.activeConversationId);
  const createConversation = useAgentStore((state) => state.createConversation);
  const setActiveConversation = useAgentStore((state) => state.setActiveConversation);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) {
      return conversations;
    }
    return conversations.filter((item) => item.title.toLowerCase().includes(query));
  }, [conversations, filter]);

  const groups = useMemo(() => groupConversations(filtered), [filtered]);

  return (
    <aside className="flex h-full w-[260px] min-w-[260px] shrink-0 flex-col border-r border-border/60 bg-workspace">
      <div className="flex items-center justify-between gap-2 px-3 py-3">
        <p className="text-[length:var(--text-sm)] font-semibold text-foreground">商品比价助手</p>
        <Button type="button" size="sm" variant="outline" onClick={() => createConversation()}>
          <MessageSquarePlus className="size-3.5" aria-hidden />
        </Button>
      </div>

      <div className="relative px-3 pb-2">
        <Search className="pointer-events-none absolute left-6 top-2.5 size-3.5 text-muted-foreground" />
        <Input
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="搜索会话"
          className="h-8 pl-8 text-[length:var(--text-xs)]"
        />
      </div>

      <ScrollArea className="min-h-0 flex-1 px-2">
        {groups.length === 0 ? (
          <p className="py-6 text-center text-[length:var(--text-xs)] text-muted-foreground">暂无会话</p>
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-3">
              <p className="px-2 py-1 text-[length:var(--text-xs)] font-medium text-muted-foreground">
                {group.label}
              </p>
              <ul className="space-y-0.5">
                {group.items.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={cn(
                        "w-full rounded-[var(--radius-md)] px-2 py-2 text-left transition-colors",
                        item.id === activeId ? "bg-primary/10" : "hover:bg-muted/50",
                      )}
                      onClick={() => setActiveConversation(item.id)}
                    >
                      <div className="flex items-start gap-2">
                        <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", statusDot(item.status))} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[length:var(--text-xs)] font-medium text-foreground">
                            {item.title}
                            {item.unread ? (
                              <span className="ml-1 inline-block size-1.5 rounded-full bg-primary align-middle" />
                            ) : null}
                          </p>
                          <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                            {item.status === "running" ? `进行中 ${item.progress}%` : item.status === "completed" ? "分析完成" : "等待输入"}
                          </p>
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </ScrollArea>

      <div className="border-t border-border/60 p-3">
        <Button type="button" className="w-full" size="sm" onClick={() => createConversation()}>
          <MessageSquarePlus className="size-3.5" aria-hidden />
          新建会话
        </Button>
      </div>
    </aside>
  );
}
