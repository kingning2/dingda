/**
 * 模型凭据的展示口径与表单取值。
 *
 * 职责：
 *     把一条凭据变成页面上要显示的文字（标题、副标题、最近检测状态），
 *     把表单里的几个字符串变成请求体，把「拉到的模型列表」变成可点选的卡片数据。
 *     纯函数，不依赖 React / DOM。
 *
 * 设计说明：
 *     - **不复用 `@v2/ui-monitor/monitor-format` 的相对时间**：两个业务包之间不许互相
 *       引用（依赖方向是 ui-* → ui-layout/ui-feedback → ui-primitives → ui-theme）。
 *       这里只差十行，抄一份比拉一条横向依赖划算
 *     - `now` 必须由调用方显式传入：内部读 `Date.now()` 会让函数无法单测，
 *       同屏几条「3 分钟前」也会各算各的基准
 *     - `buildUpdateBody` 是**只放要改的字段**这条纪律的唯一落点。后端按「字段在不在
 *       请求体里」判断改不改，所以拼请求体的逻辑必须可单测，不能散在组件的提交函数里
 *     - **模型卡片只用 `id`，标签是查表来的**：`/models` 只回 id，没有展示名。
 *       认得的模型给人话标签，认不出的**原样显示 id** —— 猜一个中文名比不显示更糟，
 *       用户会照着猜的名字去控制台里找，然后找不到
 *     - 「拉模型列表」的四种状态收成一个联合类型，文案与卡片数据都由它推出：
 *       组件里不再有 `if (loading) ... else if (error) ...` 这种会漏分支的散装判断
 */

import type {
  LlmCheckView,
  LlmCredentialCreateBody,
  LlmCredentialItem,
  LlmCredentialUpdateBody,
  LlmModelListBody,
  LlmModelListResponse,
  LlmProviderItem,
} from "@v2/contracts/model";
import { isNumber, isString } from "@v2/runtime/guards";

/**
 * 认得的模型 id → 人话标签。
 *
 * 刻意保持**短**：这张表是「我们确知含义」的清单，不是模型大全。多写一条不存在的
 * 名字没有代价，但把含义写错会让用户按错误预期选模型（比如以为某个 id 更便宜）。
 * 认不出的 id 一律原样显示，不做任何推测。
 */
const KNOWN_MODEL_LABELS: Record<string, string> = {
  "deepseek-flash": "快速档，日常对话与选品",
  "deepseek-chat": "通用对话（已停用）",
  "deepseek-reasoner": "深度推理（已停用）",
};

/** 表单里的五个字段，全是字符串 —— 空串表示「没填」。 */
export interface CredentialFormValues {
  provider: string;
  label: string;
  model: string;
  apiKey: string;
  baseUrl: string;
}

/** 新建时的空表单；模型预填供应商默认值（豆包没有默认值就是空）。 */
export function emptyFormValues(provider?: LlmProviderItem): CredentialFormValues {
  return {
    provider: provider?.id ?? "",
    label: "",
    model: provider?.default_model ?? "",
    apiKey: "",
    baseUrl: "",
  };
}

/**
 * 编辑时的初值。
 *
 * **`apiKey` 刻意留空**：后端只回掩码，前端也拿不到原文。留空即「不改」，
 * 想换 key 就重新填一把 —— 这是安全设计，不是缺功能。
 */
export function formValuesFromItem(item: LlmCredentialItem): CredentialFormValues {
  return {
    provider: item.provider,
    label: item.label,
    model: item.model,
    apiKey: "",
    baseUrl: item.base_url ?? "",
  };
}

/** 卡片标题：优先用户自己起的备注名，其次供应商中文名。 */
export function credentialTitle(item: LlmCredentialItem): string {
  return isString(item.label, "").trim() || isString(item.provider_name, "").trim() || item.provider;
}

/** 从地址里取主机名；取不出来就原样回显，实在没有给破折号。 */
export function baseUrlHost(url: string): string {
  const text = isString(url, "").trim();
  if (!text) return "—";
  try {
    return new URL(text).host || text;
  } catch {
    return text;
  }
}

/** 卡片副标题：模型 + 实际会用的地址主机。 */
export function credentialSummary(item: LlmCredentialItem): string {
  const model = isString(item.model, "").trim() || "未填模型";
  return `${model} · ${baseUrlHost(item.effective_base_url)}`;
}

/** 最近一次检测的一句话。从未检测过时也要给话，不能留空 —— 空着看起来像加载失败。 */
export function describeCheckAge(item: LlmCredentialItem, now: number): string {
  const at = isNumber(item.last_check_at, 0);
  if (!at) return "尚未检测";
  const when = formatRelativeTime(at, now);
  if (item.last_check_ok === true) return `${when}检测通过`;
  if (item.last_check_ok === false) return `${when}检测失败`;
  return `${when}检测过`;
}

/** 检测结果气泡里的文案：后端已经把「连通，耗时 N ms」拼好了，直接用。 */
export function describeCheckResult(check: LlmCheckView): string {
  const message = isString(check.message, "").trim();
  if (message) return message;
  return check.ok ? "连接正常" : "检测失败";
}

/** 检测结果配色：成功走普通提示，失败走危险色。 */
export function checkTone(check: LlmCheckView): "ok" | "fail" {
  return check.ok ? "ok" : "fail";
}

/** 新建请求体：`activate` 默认 true（新建即生效），要囤备用由调用方传 false。 */
export function buildCreateBody(
  values: CredentialFormValues,
  options?: { activate?: boolean },
): LlmCredentialCreateBody {
  return {
    provider: values.provider.trim(),
    api_key: values.apiKey.trim(),
    model: values.model.trim(),
    label: values.label.trim(),
    base_url: values.baseUrl.trim() || null,
    activate: options?.activate ?? true,
  };
}

/**
 * 修改请求体：**只放要改的字段**。
 *
 * 三条规则，每条都对应后端的一个判断：
 * - `label` / `model` 总是带上（空串由后端按「保持原值」处理，语义上是用户清空了备注）
 * - `api_key` 只在用户真填了才带 —— 留空表示「不改」，带上空串会把 key 写坏
 * - `base_url` 总是带上，空串转 `null` = 恢复供应商默认地址。这是唯一需要
 *   「出现且为 null」语义的字段
 */
export function buildUpdateBody(values: CredentialFormValues): LlmCredentialUpdateBody {
  const body: LlmCredentialUpdateBody = {
    provider: values.provider.trim(),
    label: values.label.trim(),
    base_url: values.baseUrl.trim() || null,
  };
  const model = values.model.trim();
  if (model) body.model = model;
  const apiKey = values.apiKey.trim();
  if (apiKey) body.api_key = apiKey;
  return body;
}

/**
 * 表单能不能提交；不能则给一句中文原因。
 *
 * 豆包只认 `ep-` 接入点 ID，没有默认模型 —— 这类「必填但默认空」由目录的
 * `requires_model` 决定，不在前端写死供应商名单。
 */
export function formProblem(
  values: CredentialFormValues,
  provider: LlmProviderItem | undefined,
  options: { isEdit: boolean },
): string | null {
  if (!values.provider.trim()) return "请选择供应商";
  if (provider?.requires_model && !values.model.trim()) {
    return `${provider.name} 没有默认模型，请填模型名`;
  }
  if (!options.isEdit && !values.apiKey.trim()) return "请填 API Key";
  return null;
}

/**
 * 从表单拼「拉模型列表」的请求体。
 *
 * 地址留空落成 `null`（= 跟随供应商默认）。与 `buildCreateBody` 同口径 ——
 * 拉列表和正式调用必须打同一个地址，否则列表是一套、跑起来是另一套。
 */
export function buildModelListBody(values: CredentialFormValues): LlmModelListBody {
  return {
    provider: values.provider.trim(),
    api_key: values.apiKey.trim(),
    base_url: values.baseUrl.trim() || null,
  };
}

/**
 * 拉模型列表该走哪条路。
 *
 * `credential` = 用已保存凭据的 key（编辑态、且供应商没换）；`draft` = 用表单里刚填的
 * 连接参数；`blocked` = 条件还不齐，附带一句「为什么还不能拉」。
 *
 * 「编辑态换了供应商」这条分支是本函数存在的理由：库里那把 key 属于**原**供应商，
 * 拿它去新供应商拉列表只会得到一个 401，然后用户看到「API key 无效或已过期」——
 * 明明是还没填新 key，却被说成 key 坏了。
 */
export type ModelFetchPlan =
  | { kind: "credential" }
  | { kind: "draft" }
  | { kind: "blocked"; reason: string };

/** 决定这次拉模型列表走哪条路；见 `ModelFetchPlan`。 */
export function modelFetchPlan(input: {
  isEdit: boolean;
  /** 编辑态这条凭据原本的供应商；新增态传空串 */
  savedProvider: string;
  provider: string;
  hasKey: boolean;
}): ModelFetchPlan {
  const provider = input.provider.trim();
  if (!provider) return { kind: "blocked", reason: "先选供应商" };
  if (input.isEdit && input.savedProvider.trim() === provider) return { kind: "credential" };
  if (!input.hasKey) {
    return {
      kind: "blocked",
      reason: input.isEdit
        ? "换了供应商，填一把新的 API Key 才能拉取可用模型"
        : "填好 API Key 后自动拉取可用模型",
    };
  }
  return { kind: "draft" };
}

/**
 * 模型列表的四种状态。
 *
 * `blocked` 与 `failed` 分开：前者是流程中的正常一步（还没填 key），显示成错误会让人
 * 以为出了故障；后者是拉了但上游不给，必须显示原因并保留手填入口。
 */
export type ModelListPhase =
  | { kind: "blocked"; reason: string }
  | { kind: "loading" }
  | { kind: "failed"; reason: string }
  | { kind: "ready"; models: string[]; defaultModel: string | null; note: string | null };

/** 把服务端响应收成 `ready` / `failed` 两态；失败不抛异常，只换文案。 */
export function phaseFromResponse(response: LlmModelListResponse): ModelListPhase {
  if (!response.ok) {
    return { kind: "failed", reason: isString(response.message, "").trim() || "拉取可用模型失败" };
  }
  return {
    kind: "ready",
    models: response.models.filter((id) => isString(id, "").trim().length > 0),
    defaultModel: response.default_model,
    note: isString(response.message, "").trim() || null,
  };
}

/** 模型 id → 卡片上的说明文字；认不出就是 id 本身，不做任何推测。 */
export function describeModelId(model: string): string {
  const id = isString(model, "").trim();
  if (!id) return "";
  return KNOWN_MODEL_LABELS[id] ?? id;
}

/** 一张模型卡片。 */
export interface ModelOption {
  id: string;
  /** 人话标签；认不出的模型等于 `id`，卡片据此决定要不要多显示一行 */
  label: string;
  /** 目录里的默认模型 */
  isDefault: boolean;
  /** 表单当前选中的那个 */
  isSelected: boolean;
}

/**
 * 状态 → 卡片数据。
 *
 * 顺序**沿用上游给的**（`/models` 的排法就是供应商自己的主推顺序，自己再排一遍会把
 * 主推模型挤到后面），只在最前面补上「表单选中但不在列表里」的那个 —— 否则用户编辑
 * 一条老凭据时会看到一张都没选中。
 */
export function modelOptions(phase: ModelListPhase, selected: string): ModelOption[] {
  if (phase.kind !== "ready") return [];
  const current = isString(selected, "").trim();
  const ids = phase.models.slice();
  if (current && !ids.includes(current)) ids.unshift(current);
  return ids.map((id) => ({
    id,
    label: describeModelId(id),
    isDefault: phase.defaultModel === id && phase.defaultModel !== null,
    isSelected: id === current,
  }));
}

/** 状态 → 一行说明文字。永远给话，不留空 —— 空着看起来像加载失败。 */
export function modelListHint(phase: ModelListPhase): string {
  if (phase.kind === "blocked") return phase.reason;
  if (phase.kind === "loading") return "正在向上游拉取可用模型…";
  if (phase.kind === "failed") return `${phase.reason}。可以手动填写模型名`;
  if (phase.models.length > 0) return `共 ${phase.models.length} 个可用模型`;
  return phase.note ?? "上游没有返回模型列表，可以手动填写模型名";
}

/**
 * Unix 秒 → 相对时间。
 *
 * 与 `monitor-format.ts` 同口径（缺失给破折号、`now` 由调用方传），
 * 但本包不能引那个模块 —— 见文件头。
 */
function formatRelativeTime(timestamp: number, now: number): string {
  const diff = now - timestamp;
  const seconds = Math.abs(diff);
  if (seconds < 60) return diff < 0 ? "即将" : "刚刚";
  const suffix = diff < 0 ? "后" : "前";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟${suffix}`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} 小时${suffix}`;
  return `${Math.floor(seconds / 86_400)} 天${suffix}`;
}
