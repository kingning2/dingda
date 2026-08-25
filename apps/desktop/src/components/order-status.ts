/** 订单状态 → 中文标签（chat / orders 等 feature 共用）。 */
export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: "待付款",
  paid: "待发货",
  shipped: "已发货",
  completed: "已完成",
  closed: "已关闭",
  refunded: "已退款",
  unknown: "未知",
};
