/**
 * 商品监控契约 — 与 Python `api/watch.py` 的 DTO 对齐。
 *
 * 职责：
 *     定义「监控目标快照 / 价格历史点 / 变更事件」三份线协议类型，纯类型零运行时。
 *
 * 设计说明：
 *     - 只声明前端真正消费的形状。`/v1/watch/summary` 与 `/v1/watch/poll` 前端暂不调用，
 *       故不在此声明 —— 类型放这里等于宣告「有人要用」，留着不用就是无声的债。
 *     - 涨跌口径由后端算（`price_drop` = 首价 − 现价，正数表示已降价），前端不重算。
 *       两边各算一份的话，对不上时无从判断谁对。
 *     - 状态字段一律 `string`：后端 DTO 就是 `str`，值域由 Python 侧
 *       `contracts.watch.SoldState` / `WatchState` 保证。前端在 `monitor-format.ts`
 *       用映射函数容错 —— 联合类型收窄遇到脏数据时会给出虚假的类型安全感。
 */

/** 监控开关状态：前端 PATCH 时构造，值域与 Python `WatchState` 一致。 */
export type MonitorState = "active" | "paused" | "archived";

/** 监控目标当前快照（列表与详情共用）。 */
export interface MonitorTargetItem {
  target_id: string;
  platform: string;
  item_id: string;
  /** 首次轮询前为空串，轮询后由后端回填。 */
  title: string;
  url: string;
  image_url: string | null;
  /** active / paused / archived。 */
  state: string;
  /** unknown / on_sale / sold / delisted / gone。 */
  sold_state: string;
  first_price: number | null;
  last_price: number | null;
  min_price: number | null;
  max_price: number | null;
  /** 首价 − 现价；正数表示已降价。后端算，前端不重算。 */
  price_drop: number | null;
  price_drop_ratio: number | null;
  last_want_count: string | null;
  last_status_text: string | null;
  poll_interval_seconds: number;
  next_poll_at: number;
  last_poll_at: number | null;
  /** 最近一次轮询的失败原因；成功时为 null。 */
  last_error: string | null;
  fail_count: number;
  /** 已监控时长（小时）。 */
  watched_hours: number;
  created_at: number;
  updated_at: number;
}

/** 价格历史上的一个观测点（只增不改）。 */
export interface MonitorPointItem {
  observed_at: number;
  price: number | null;
  /** 原始价格文案，解析不出数字时仍有值。 */
  price_text: string | null;
  want_count: string | null;
  browse_count: string | null;
  sold_state: string;
  status_text: string | null;
}

/** 由价格点序列推导出的一次变更。 */
export interface MonitorChangeItem {
  /** price_drop / price_rise / sold / delisted / gone / relisted。 */
  kind: string;
  observed_at: number;
  from_price: number | null;
  to_price: number | null;
  delta: number | null;
  delta_ratio: number | null;
  /** 后端生成的中文文案，前端直接展示，不重新拼。 */
  message: string;
}

/** 加入监控的一条商品。标题/链接/封面可省，首次轮询后自动补齐。 */
export interface MonitorAddItemInput {
  platform: string;
  item_id: string;
  title?: string;
  url?: string;
  image_url?: string | null;
  account_id?: string | null;
}

/** 批量加入监控的请求体。 */
export interface MonitorAddRequest {
  items: MonitorAddItemInput[];
  /** 轮询间隔秒；不传用后端默认（6 小时），夹在 60 ~ 604800。 */
  poll_interval_seconds?: number;
}

/** 加入监控结果。 */
export interface MonitorAddResponse {
  ok: boolean;
  /** 本次实际写入（含同 platform+item_id 已存在而复用）的条数。 */
  added: number;
  targets: MonitorTargetItem[];
}

/** 监控列表。 */
export interface MonitorListResponse {
  ok: boolean;
  total: number;
  targets: MonitorTargetItem[];
}

/** 单条监控详情。 */
export interface MonitorDetailResponse {
  ok: boolean;
  target: MonitorTargetItem;
  points: MonitorPointItem[];
  changes: MonitorChangeItem[];
}

/** 调整监控状态或轮询间隔。 */
export interface MonitorPatchRequest {
  state?: MonitorState;
  poll_interval_seconds?: number;
}

/** 移除监控结果。 */
export interface MonitorDeleteResponse {
  ok: boolean;
  removed: boolean;
}
