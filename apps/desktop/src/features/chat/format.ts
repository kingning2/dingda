/**
 * 会话时间格式化 — 兼容毫秒字符串（created_at）与 ISO 时间（下单时间）。
 * 统一输出 `MM-DD HH:mm`；非法输入返回空串。
 */
export function formatChatTime(value?: string | number | null): string {
  if (value == null) {
    return "";
  }
  let ms: number;
  if (typeof value === "number") {
    ms = value;
  } else if (/^\d+$/.test(value)) {
    ms = Number(value);
  } else {
    ms = new Date(value).getTime();
  }
  if (!Number.isFinite(ms) || ms <= 0) {
    return "";
  }
  return new Date(ms).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** 相对时间 — 对齐 Shadcn Admin inbox-1（如「6 小时前」）。 */
export function formatRelativeTime(value?: string | number | null): string {
  if (value == null) {
    return "";
  }
  let ms: number;
  if (typeof value === "number") {
    ms = value;
  } else if (/^\d+$/.test(value)) {
    ms = Number(value);
  } else {
    ms = new Date(value).getTime();
  }
  if (!Number.isFinite(ms) || ms <= 0) {
    return "";
  }
  const diff = Date.now() - ms;
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  const week = 7 * day;
  if (diff < minute) {
    return "刚刚";
  }
  if (diff < hour) {
    return `${Math.floor(diff / minute)} 分钟前`;
  }
  if (diff < day) {
    return `${Math.floor(diff / hour)} 小时前`;
  }
  if (diff < week) {
    return `${Math.floor(diff / day)} 天前`;
  }
  return formatChatTime(ms);
}

/** 会话列表标题 — 商品咨询优先，否则买家昵称。 */
export function conversationSubject(conversation: {
  item_title?: string;
  peer_name?: string;
  peer_id: string;
}): string {
  const item = conversation.item_title?.trim();
  if (item) {
    return item.length > 48 ? `${item.slice(0, 48)}…` : item;
  }
  return conversation.peer_name?.trim() || conversation.peer_id || "未知会话";
}
