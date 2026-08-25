import {
  Button,
  Input,
  Loading,
  ScrollArea,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@desk/ui";
import { MessageSquare, RefreshCw } from "@desk/ui/icons";
import type { ChannelConversation, ChannelMessage } from "@desk/contracts";
import type { XianyuAccount } from "@desk/platform/ipc/account";
import { conversationNeedsReply, lastMessagePreview } from "./use-channel-inbox";
import { conversationSubject, formatRelativeTime } from "./format";

export interface InboxPanelProps {
  loading: boolean;
  conversations: ChannelConversation[];
  messages: ChannelMessage[];
  selectedId: string | null;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  accounts: XianyuAccount[];
  accountFilter: string;
  onAccountFilterChange: (accountId: string) => void;
  refreshing: boolean;
  onRefresh: () => void;
  accountMetaById: Map<string, { label: string; avatarUrl: string }>;
  onSelectConversation: (id: string) => void;
  onGoToAccounts: () => void;
}

/** 会话收件箱（左栏）— 参考 Shadcn Admin inbox-1。 */
export function InboxPanel({
  loading,
  conversations,
  messages,
  selectedId,
  searchQuery,
  onSearchChange,
  accounts,
  accountFilter,
  onAccountFilterChange,
  refreshing,
  onRefresh,
  accountMetaById,
  onSelectConversation,
  onGoToAccounts,
}: InboxPanelProps) {
  const pendingCount = conversations.filter((item) =>
    conversationNeedsReply(item.id, messages),
  ).length;

  return (
    <aside className="flex w-[min(100%,20rem)] shrink-0 flex-col border-r border-border/70 bg-transparent">
      <div className="space-y-3 border-b border-border px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <h2 className="text-[length:var(--text-sm)] font-semibold text-foreground">收件箱</h2>
            {conversations.length > 0 ? (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[length:var(--text-xs)] tabular-nums text-muted-foreground">
                {conversations.length}
              </span>
            ) : null}
            {pendingCount > 0 ? (
              <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[length:var(--text-xs)] text-primary">
                {pendingCount} 待回复
              </span>
            ) : null}
          </div>
          <Button
            size="icon"
            variant="ghost"
            aria-label="刷新"
            disabled={refreshing}
            onClick={onRefresh}
            className="size-8 shrink-0"
          >
            <RefreshCw
              className={`size-3.5 ${refreshing ? "animate-spin" : ""}`}
              aria-hidden
            />
          </Button>
        </div>

        <Input
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索会话…"
          className="h-8 bg-muted/30"
        />

        <Select
          value={accountFilter || "__all__"}
          onValueChange={(value) => onAccountFilterChange(value === "__all__" ? "" : value)}
        >
          <SelectTrigger className="h-8 bg-muted/30">
            <SelectValue placeholder="全部账号" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">全部账号</SelectItem>
            {accounts.map((account) => (
              <SelectItem key={account.account_id} value={account.account_id}>
                {account.display_name || account.account_id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {loading ? (
          <div className="flex justify-center py-8">
            <Loading />
          </div>
        ) : conversations.length === 0 ? (
          <div className="space-y-3 px-4 py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
            <MessageSquare className="mx-auto size-8 opacity-40" aria-hidden />
            <p>{searchQuery.trim() ? "没有匹配的会话" : "暂无会话"}</p>
            {!searchQuery.trim() ? (
              <>
                <p className="text-[length:var(--text-xs)]">
                  请先在账号管理连接闲鱼账号，未读消息会自动同步到这里。
                </p>
                <Button size="sm" variant="outline" onClick={onGoToAccounts}>
                  前往账号管理
                </Button>
              </>
            ) : null}
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {conversations.map((conversation) => {
              const active = conversation.id === selectedId;
              const preview = lastMessagePreview(conversation.id, messages);
              const needsReply = conversationNeedsReply(conversation.id, messages);
              const title = conversationSubject(conversation);
              const accountLabel =
                accountMetaById.get(conversation.account_id)?.label ?? conversation.account_id;
              const relativeTime = formatRelativeTime(conversation.updated_at);

              return (
                <li key={conversation.id}>
                  <button
                    type="button"
                    className={`flex w-full flex-col gap-1 px-3 py-3 text-left transition-colors duration-150 hover:bg-muted/40 ${
                      active ? "bg-muted/60" : ""
                    }`}
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="line-clamp-1 text-[length:var(--text-sm)] font-medium text-foreground">
                        {title}
                      </span>
                      {relativeTime ? (
                        <span className="shrink-0 text-[length:var(--text-xs)] text-muted-foreground">
                          {relativeTime}
                        </span>
                      ) : null}
                    </div>
                    <p className="line-clamp-2 text-[length:var(--text-xs)] leading-relaxed text-muted-foreground">
                      {preview || "暂无消息"}
                    </p>
                    <div className="flex items-center justify-between gap-2 pt-0.5">
                      <span className="truncate text-[length:var(--text-xs)] text-muted-foreground/80">
                        {accountLabel}
                      </span>
                      {needsReply ? (
                        <span className="flex shrink-0 items-center gap-1 text-[length:var(--text-xs)] text-primary">
                          <span className="size-1.5 rounded-full bg-primary" aria-hidden />
                          待回复
                        </span>
                      ) : null}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </ScrollArea>
    </aside>
  );
}
