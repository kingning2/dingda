/**
 * Chat Feature — 客户会话收件箱。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */

import { MessageSquare } from "@desk/ui/icons";

export { ChatPage } from "./chat-page";
export { InboxPanel } from "./inbox-panel";
export type { InboxPanelProps } from "./inbox-panel";
export { ThreadPanel } from "./thread-panel";
export type { ThreadPanelProps } from "./thread-panel";
export { CustomerPanel } from "./customer-panel";
export type { CustomerPanelProps } from "./customer-panel";
export { ConversationAvatar } from "./conversation-avatar";
export { InfoSection, InfoRow } from "./info-section";
export { formatChatTime } from "./format";
export { useChannelInbox } from "./use-channel-inbox";

/** Chat 功能路由与侧栏元信息。 */
export const chatFeature = {
  id: "chat",
  path: "/features/chat",
  navItem: {
    id: "chat",
    path: "/features/chat",
    label: "客户会话",
    icon: MessageSquare,
  },
};
