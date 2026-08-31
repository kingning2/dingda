/**
 * Tauri IPC command → 日志用中文名称。
 *
 * 日志面板展示 `command=插件列表`（中文名），不暴露 snake_case 原名。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */

/** IPC command 中文名（与 Rust `generate_handler!` 对齐）。 */
export const IPC_COMMAND_LABELS: Readonly<Record<string, string>> = {
  agent_ping: "Agent 探活",
  app_version: "应用版本",
  agent_reply: "Agent 对话",
  agent_run_start: "启动 Agent Run",
  agent_run_pause: "暂停 Agent Run",
  agent_run_resume: "恢复 Agent Run",
  agent_run_cancel: "取消 Agent Run",
  agent_run_status: "Agent Run 状态",
  agent_run_get: "读取 Agent Run",
  agent_run_list: "Agent Run 列表",
  ai_config_get: "读取 AI 配置",
  ai_config_set: "保存 AI 配置",
  ai_providers_catalog: "读取 AI 平台目录",
  ai_list_models: "拉取 AI 模型列表",
  ai_account_balance: "查询 AI 余额",
  copilot_ready: "副驾就绪检查",
  copilot_run_start: "启动副驾对话",
  copilot_run_abort: "取消副驾对话",
  ["ai_test_api_key"]: "测试 API 密钥",
  plugin_list: "插件列表",
  plugin_install: "插件安装",
  plugin_uninstall: "插件卸载",
  account_list: "账号列表",
  account_create: "新建账号",
  account_update: "更新账号",
  account_set_status: "设置账号状态",
  account_delete: "删除账号",
  account_probe_login: "探测账号登录态",
  ali1688_search: "1688 商品搜索",
  xianyu_search: "闲鱼商品搜索",
  account_qr_start: "发起扫码登录",
  account_qr_check: "检查扫码状态",
  account_qr_cancel: "取消扫码登录",
  account_connect: "连接账号",
  account_disconnect: "断开账号",
  account_connection_state: "账号连接状态",
  order_list: "订单列表",
  order_get: "订单详情",
  order_update_status: "更新订单状态",
  order_update_delivery: "更新发货信息",
  order_create: "创建订单",
  order_delete: "删除订单",
  item_list: "商品列表",
  item_get: "商品详情",
  item_update: "更新商品",
  risk_log_list: "风控日志",
  risk_log_today_rate: "今日风控比率",
  risk_log_clear: "清空风控日志",
  risk_log_clear_processing: "清空处理中风控",
  risk_config_get: "读取风控配置",
  risk_config_set: "保存风控配置",
  user_setting_get: "读取用户设置",
  user_setting_set: "保存用户设置",
  dashboard_stats: "仪表盘统计",
  channel_state_get: "读取渠道状态",
  channel_state_set: "设置渠道状态",
  channel_connect: "连接渠道",
  channel_disconnect: "断开渠道",
  channel_send: "发送渠道消息",
  channel_qr_start: "发起渠道扫码",
  channel_qr_check: "检查渠道扫码",
  channel_qr_cancel: "取消渠道扫码",
  license_status: "授权状态",
  license_machine_code: "机器码",
  license_activate: "激活授权",
  platform_descriptors: "平台能力描述",
  log_clear: "清空日志",
  log_recent: "最近日志",
  log_write: "写入日志",
};

/**
 * 解析 IPC command 的中文日志名。
 *
 * @author Xiaoman
 * @created 2026-08-19
 *
 * @param command - Tauri command 名
 * @returns 中文名；未登记时返回「未命名调用」
 */
export function ipcCommandLabel(command: string): string {
  return IPC_COMMAND_LABELS[command] ?? "未命名调用";
}
