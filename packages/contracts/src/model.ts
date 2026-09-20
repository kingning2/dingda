/**
 * 模型配置契约 — 与 Python 侧 `contracts/llm.py` 逐字段对齐。
 *
 * 职责：
 *     供应商目录、模型凭据记录、新建 / 修改请求、可用模型列表、连通性检测结果。
 *
 * 设计说明：
 *     - `api_key` 只出现在**请求**方向；**响应**方向永远只有 `api_key_masked`。
 *       前端不得为了「编辑时回填」而索要原文
 *     - `base_url` 的「不改」与「清空」靠**字段在不在请求体里**区分：字段不出现 = 不改，
 *       出现且为 `null` = 恢复供应商默认地址。与 Python 侧的 `model_fields_set` 同一约定，
 *       所以拼请求体时要「按需加字段」，不要把所有字段填成 `undefined` 一起发
 *     - 供应商 id 是 `string` 而不是联合类型：目录由服务端数据驱动，写死枚举等于
 *       把「新增供应商」变成一次前端发版
 *     - **拉模型列表拉不到不是错误**：与检测端点同口径，回 200 + `ok: false` + `message`。
 *       前端据此把「模型卡片」退回成手填输入框，而不是弹一个错误框
 */

/** 目录里的一行：某个 OpenAI 兼容供应商的静态事实。 */
export interface LlmProviderItem {
  id: string;
  name: string;
  base_url: string;
  default_model: string | null;
  api_key_envs: string[];
  /** 没有默认模型（豆包只认 `ep-` 接入点 ID）→ 表单必须要求用户手填。 */
  requires_model: boolean;
}

export interface LlmProviderListResponse {
  ok: boolean;
  items: LlmProviderItem[];
}

/** 一条凭据的展示形状。`api_key` 永不出现，只给掩码。 */
export interface LlmCredentialItem {
  credential_id: string;
  provider: string;
  provider_name: string;
  label: string;
  model: string;
  /** 用户自定义地址；`null` 表示跟随供应商默认。 */
  base_url: string | null;
  /** 实际会用的地址（`base_url` 为空时由服务端补上供应商默认）。 */
  effective_base_url: string;
  api_key_masked: string;
  has_api_key: boolean;
  is_active: boolean;
  /** Unix 秒；从未检测过为 `null`。 */
  last_check_at: number | null;
  last_check_ok: boolean | null;
  last_check_message: string | null;
  created_at: number;
  updated_at: number;
}

export interface LlmCredentialListResponse {
  ok: boolean;
  items: LlmCredentialItem[];
  active_id: string | null;
}

export interface LlmCredentialCreateBody {
  provider: string;
  api_key: string;
  model?: string;
  label?: string;
  base_url?: string | null;
  /** 新建即生效；默认 true。只在「先囤一把备用」时传 false。 */
  activate?: boolean;
}

/** 改凭据：字段缺省 = 不改。 */
export interface LlmCredentialUpdateBody {
  provider?: string;
  model?: string;
  api_key?: string;
  label?: string;
  base_url?: string | null;
}

export interface LlmCredentialResponse {
  ok: boolean;
  item: LlmCredentialItem;
}

export interface LlmCredentialDeleteResponse {
  ok: boolean;
  deleted: boolean;
}

/**
 * POST `/v1/llm/models` — 按一组连接参数拉可用模型（凭据**还没保存**时用）。
 *
 * 没有 `model` 字段：拉列表本就是为了知道该填什么模型。
 */
export interface LlmModelListBody {
  provider: string;
  /** key 原文；只在请求方向出现，不会回显。 */
  api_key: string;
  /** 自定义地址；不传用供应商默认。 */
  base_url?: string | null;
}

/**
 * 某个账号可用的模型列表。
 *
 * 拉不到时 `ok: false` + `message`，不是 HTTP 错误 —— 与检测端点同一口径。
 */
export interface LlmModelListResponse {
  ok: boolean;
  provider: string;
  models: string[];
  /** 目录里的默认模型；前端据此给对应卡片挂「默认」徽章。 */
  default_model: string | null;
  /** 凭据当前填的模型；从表单拉取时为 `null`。 */
  current_model: string | null;
  /** 拉不到时的原因（含 `llm.*` 语义）；成功为 `null`。 */
  message: string | null;
}

/** 一次连通性检测的结果。`code` 复用后端 `llm.*` 错误码。 */
export interface LlmCheckView {
  ok: boolean;
  message: string;
  code?: string | null;
  latency_ms?: number | null;
  reply?: string | null;
  model: string;
  provider: string;
}

export interface LlmCheckResponse {
  ok: boolean;
  check: LlmCheckView;
}

/** POST /v1/llm/credentials/import-env — 收编 `.env` 里那份配置。 */
export interface LlmImportEnvResponse {
  ok: boolean;
  imported: boolean;
  item: LlmCredentialItem | null;
  message: string;
}
