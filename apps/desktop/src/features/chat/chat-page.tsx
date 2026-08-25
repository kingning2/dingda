/**
 * 客户会话收件箱 — 三栏布局，参考 Shadcn Admin inbox-1。
 *
 * @see https://shadcnblocks-admin.vercel.app/project-management/inbox-1
 */

import { useEffect, useMemo, useState } from "react";
import { PageScaffold } from "@desk/ui";
import { OWNER_ID } from "@desk/platform/constants";
import { accountList, type XianyuAccount } from "@desk/platform/ipc/account";
import {
  channelProductHeadinfo,
  type ProductHeadInfo,
} from "@desk/platform/ipc/channel";
import { orderList, type Order } from "@desk/platform/ipc/order";
import { formatAmount } from "@desk/utils";
import { managePath } from "@desk/platform/compile";
import { useWorkspaceNav } from "../../app/use-workspace-tabs";
import { conversationNeedsReply, lastMessagePreview, useChannelInbox } from "./use-channel-inbox";
import { InboxPanel } from "./inbox-panel";
import { ThreadPanel } from "./thread-panel";
import { CustomerPanel } from "./customer-panel";
import { formatChatTime } from "./format";

/** 客户会话页。 */
export function ChatPage() {
  const { selectTab } = useWorkspaceNav();
  const {
    loading,
    error,
    messages,
    selectedId,
    selectedConversation,
    threadMessages,
    refresh,
    selectConversation,
    sendMessage,
    accountFilter,
    setAccountFilter,
    filteredConversations,
  } = useChannelInbox();

  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [infoOpen, setInfoOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [replyDraft, setReplyDraft] = useState("");
  const [buyerOrders, setBuyerOrders] = useState<Order[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [headInfo, setHeadInfo] = useState<ProductHeadInfo | null>(null);

  useEffect(() => {
    void accountList(OWNER_ID)
      .then(setAccounts)
      .catch(() => setAccounts([]));
  }, []);

  const accountMetaById = useMemo(() => {
    const map = new Map<string, { label: string; avatarUrl: string }>();
    for (const account of accounts) {
      map.set(account.account_id, {
        label: account.display_name || account.account_id,
        avatarUrl: account.avatar_url || "",
      });
    }
    return map;
  }, [accounts]);

  const inboxConversations = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const sorted = [...filteredConversations].sort(
      (a, b) => Number(b.updated_at) - Number(a.updated_at),
    );
    if (!query) {
      return sorted;
    }
    return sorted.filter((conversation) => {
      const haystack = [
        conversation.peer_name,
        conversation.peer_id,
        conversation.item_title,
        conversation.item_id,
        accountMetaById.get(conversation.account_id)?.label,
        lastMessagePreview(conversation.id, messages),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [filteredConversations, searchQuery, accountMetaById, messages]);

  const previousConversations = useMemo(() => {
    if (!selectedConversation?.peer_id) {
      return [];
    }
    return filteredConversations
      .filter(
        (item) =>
          item.peer_id === selectedConversation.peer_id && item.id !== selectedConversation.id,
      )
      .sort((a, b) => Number(b.updated_at) - Number(a.updated_at))
      .slice(0, 5);
  }, [filteredConversations, selectedConversation]);

  const selectedPeerId = selectedConversation?.peer_id ?? "";

  useEffect(() => {
    if (!infoOpen || !selectedPeerId) {
      setBuyerOrders([]);
      return;
    }
    let cancelled = false;
    setOrdersLoading(true);
    setOrdersError(null);
    orderList({ owner_id: OWNER_ID, page: 1, page_size: 50, buyer_id: selectedPeerId })
      .then(([list]) => {
        if (!cancelled) {
          setBuyerOrders(list);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setOrdersError(cause instanceof Error ? cause.message : String(cause));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setOrdersLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [infoOpen, selectedPeerId]);

  useEffect(() => {
    if (!infoOpen || !selectedId) {
      setHeadInfo(null);
      return;
    }
    let cancelled = false;
    channelProductHeadinfo(selectedId)
      .then((data) => {
        if (!cancelled) {
          setHeadInfo(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHeadInfo(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [infoOpen, selectedId]);

  const firstOrder = buyerOrders[0];
  const buyerFishNick = firstOrder?.buyer_fish_nick?.trim() || undefined;
  const buyerNick = firstOrder?.buyer_nick?.trim() || undefined;
  const peerName =
    selectedConversation?.peer_name?.trim() ||
    selectedConversation?.peer_id ||
    "未知联系人";
  const accountLabel = selectedConversation
    ? (accountMetaById.get(selectedConversation.account_id)?.label ??
      selectedConversation.account_id)
    : "";
  const needsReply = selectedConversation
    ? conversationNeedsReply(selectedConversation.id, messages)
    : false;
  const lastMessageTime = threadMessages.length
    ? formatChatTime(threadMessages[threadMessages.length - 1].created_at)
    : "";
  const itemPrice =
    selectedConversation?.item_price != null
      ? formatAmount(selectedConversation.item_price)
      : undefined;

  const headTitle =
    (typeof headInfo?.title === "string" && headInfo.title) ||
    (typeof headInfo?.itemTitle === "string" && headInfo.itemTitle) ||
    undefined;
  const headPrice =
    headInfo?.price != null && String(headInfo.price) ? String(headInfo.price) : undefined;
  const headImage =
    (typeof headInfo?.image === "string" && headInfo.image) ||
    (typeof headInfo?.mainImg === "string" && headInfo.mainImg) ||
    (typeof headInfo?.pic === "string" && headInfo.pic) ||
    undefined;

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <PageScaffold scroll={false} fill containerPadding="sm" className="min-h-0">
      <div className="flex min-h-0 flex-1 overflow-hidden rounded-[var(--radius-xl)] border border-border/80 bg-card/80 backdrop-blur-sm">
        <InboxPanel
          loading={loading}
          conversations={inboxConversations}
          messages={messages}
          selectedId={selectedId}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          accounts={accounts}
          accountFilter={accountFilter}
          onAccountFilterChange={setAccountFilter}
          refreshing={refreshing}
          onRefresh={() => void handleRefresh()}
          accountMetaById={accountMetaById}
          onSelectConversation={selectConversation}
          onGoToAccounts={() => selectTab(managePath("accounts"))}
        />
        <ThreadPanel
          selectedConversation={selectedConversation}
          peerName={peerName}
          accountLabel={accountLabel}
          threadMessages={threadMessages}
          error={error}
          infoOpen={infoOpen}
          needsReply={needsReply}
          draft={replyDraft}
          onDraftChange={setReplyDraft}
          onToggleInfo={() => setInfoOpen((open) => !open)}
          onSend={sendMessage}
        />
        {infoOpen ? (
          <CustomerPanel
            selectedConversation={selectedConversation}
            peerName={peerName}
            buyerFishNick={buyerFishNick}
            buyerNick={buyerNick}
            accountLabel={accountLabel}
            headTitle={headTitle}
            headPrice={headPrice}
            headImage={headImage}
            itemPrice={itemPrice}
            threadMessages={threadMessages}
            needsReply={needsReply}
            lastMessageTime={lastMessageTime}
            buyerOrders={buyerOrders}
            ordersLoading={ordersLoading}
            ordersError={ordersError}
            previousConversations={previousConversations}
            onSelectConversation={selectConversation}
            onInsertSuggestedReply={setReplyDraft}
          />
        ) : null}
      </div>
    </PageScaffold>
  );
}
