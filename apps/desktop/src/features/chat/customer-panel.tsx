import { Button, Loading, ScrollArea } from "@desk/ui";
import { Bot, MessageSquare, Package, ShoppingCart, User } from "@desk/ui/icons";
import { formatAmount } from "@desk/utils";
import type { ChannelConversation, ChannelMessage } from "@desk/contracts";
import { ORDER_STATUS_LABELS } from "@components/order-status";
import type { Order } from "@desk/platform/ipc/order";
import { ConversationAvatar } from "./conversation-avatar";
import { InfoRow, InfoSection } from "./info-section";
import { conversationSubject, formatRelativeTime } from "./format";

export interface CustomerPanelProps {
  selectedConversation: ChannelConversation | null;
  peerName: string;
  buyerFishNick?: string;
  buyerNick?: string;
  accountLabel: string;
  headTitle?: string;
  headPrice?: string;
  headImage?: string;
  itemPrice?: string;
  threadMessages: ChannelMessage[];
  needsReply: boolean;
  lastMessageTime: string;
  buyerOrders: Order[];
  ordersLoading: boolean;
  ordersError: string | null;
  previousConversations: ChannelConversation[];
  onSelectConversation: (id: string) => void;
  onInsertSuggestedReply: (text: string) => void;
}

/** 客户洞察栏（右栏）— 参考 Shadcn Admin inbox-1 Inbox Agent 面板。 */
export function CustomerPanel({
  selectedConversation,
  peerName,
  buyerFishNick,
  buyerNick,
  accountLabel,
  headTitle,
  headPrice,
  headImage,
  itemPrice,
  threadMessages,
  needsReply,
  lastMessageTime,
  buyerOrders,
  ordersLoading,
  ordersError,
  previousConversations,
  onSelectConversation,
  onInsertSuggestedReply,
}: CustomerPanelProps) {
  const inboundCount = threadMessages.filter((item) => item.direction === "in").length;
  const suggestedReply = needsReply
    ? `您好，已收到您的消息。关于「${headTitle || selectedConversation?.item_title || "商品咨询"}」，我们马上为您处理，请稍候。`
    : null;

  return (
    <aside className="flex w-[min(100%,18rem)] shrink-0 flex-col border-l border-border/70 bg-muted/20">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="size-4 text-primary" aria-hidden />
          <h2 className="text-[length:var(--text-sm)] font-semibold text-foreground">客户洞察</h2>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-4 p-4">
          {!selectedConversation ? (
            <p className="py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
              选择会话查看客户信息
            </p>
          ) : (
            <>
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <ConversationAvatar name={peerName} size="md" />
                  <div className="min-w-0">
                    <p className="font-medium text-[length:var(--text-sm)] text-foreground">
                      {peerName}
                    </p>
                    {buyerFishNick || buyerNick ? (
                      <p className="text-[length:var(--text-xs)] text-muted-foreground">
                        {buyerFishNick || buyerNick}
                      </p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {needsReply ? (
                        <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[length:var(--text-xs)] text-primary">
                          待回复
                        </span>
                      ) : null}
                      {buyerOrders.length > 0 ? (
                        <span className="rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[length:var(--text-xs)] text-muted-foreground">
                          有历史订单
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <InfoSection icon={MessageSquare} title="会话状态">
                <p className="text-[length:var(--text-xs)] leading-relaxed text-muted-foreground">
                  {needsReply
                    ? "买家最新消息尚未回复，建议优先处理。"
                    : "当前会话暂无待回复消息。"}
                  {inboundCount > 0
                    ? ` 共收到 ${inboundCount} 条买家消息，最近活跃 ${lastMessageTime || "—"}。`
                    : null}
                </p>
              </InfoSection>

              {suggestedReply ? (
                <InfoSection icon={Bot} title="建议回复">
                  <p className="text-[length:var(--text-xs)] leading-relaxed text-muted-foreground">
                    可快速发送以下模板：
                  </p>
                  <p className="rounded-md border border-border/70 bg-muted/30 p-2 text-[length:var(--text-xs)] leading-relaxed text-foreground">
                    {suggestedReply}
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full"
                    onClick={() => onInsertSuggestedReply(suggestedReply)}
                  >
                    填入回复框
                  </Button>
                </InfoSection>
              ) : null}

              <InfoSection icon={User} title="买家资料">
                <InfoRow label="昵称" value={peerName} />
                <InfoRow label="买家编号" value={selectedConversation.peer_id || undefined} mono />
                <InfoRow label="鱼塘昵称" value={buyerFishNick} />
                <InfoRow label="买家昵称" value={buyerNick} />
                <InfoRow label="所属账号" value={accountLabel} />
              </InfoSection>

              <InfoSection icon={Package} title="商品信息">
                <InfoRow
                  label="商品"
                  value={headTitle || selectedConversation.item_title || undefined}
                />
                <InfoRow label="价格" value={headPrice || itemPrice} />
                {headImage ? (
                  <img
                    src={headImage}
                    alt="商品图"
                    className="mt-1 h-24 w-full rounded-lg border border-border object-cover"
                  />
                ) : null}
                <InfoRow label="商品编号" value={selectedConversation.item_id || undefined} mono />
              </InfoSection>

              <InfoSection
                icon={ShoppingCart}
                title={`订单${buyerOrders.length ? ` (${buyerOrders.length})` : ""}`}
              >
                {ordersLoading ? (
                  <div className="flex justify-center py-4">
                    <Loading size="sm" />
                  </div>
                ) : ordersError ? (
                  <p className="text-[length:var(--text-xs)] text-destructive">{ordersError}</p>
                ) : buyerOrders.length === 0 ? (
                  <p className="text-[length:var(--text-xs)] text-muted-foreground">暂无订单</p>
                ) : (
                  <div className="space-y-2">
                    {buyerOrders.map((order) => (
                      <div
                        key={order.order_no}
                        className="rounded-md border border-border/70 bg-muted/20 p-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-mono text-[length:var(--text-xs)]">
                            {order.order_no}
                          </span>
                          <span className="shrink-0 text-[length:var(--text-xs)]">
                            {ORDER_STATUS_LABELS[order.status] ?? order.status}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-2 text-[length:var(--text-xs)] text-muted-foreground">
                          <span className="truncate">
                            {order.item_title || order.item_id}
                            {order.spec_value ? ` · ${order.spec_value}` : ""}
                          </span>
                          <span className="shrink-0">
                            {formatAmount(order.amount)} × {order.quantity}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </InfoSection>

              {previousConversations.length > 0 ? (
                <InfoSection icon={MessageSquare} title="历史会话">
                  <ul className="space-y-1">
                    {previousConversations.map((conversation) => (
                      <li key={conversation.id}>
                        <button
                          type="button"
                          className="flex w-full items-start justify-between gap-2 rounded-md px-1 py-1.5 text-left transition-colors hover:bg-muted/40"
                          onClick={() => onSelectConversation(conversation.id)}
                        >
                          <span className="line-clamp-1 text-[length:var(--text-xs)] text-foreground">
                            {conversationSubject(conversation)}
                          </span>
                          <span className="shrink-0 text-[length:var(--text-xs)] text-muted-foreground">
                            {formatRelativeTime(conversation.updated_at)}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </InfoSection>
              ) : null}
            </>
          )}
        </div>
      </ScrollArea>
    </aside>
  );
}
