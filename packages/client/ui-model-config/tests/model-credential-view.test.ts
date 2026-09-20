/**
 * 模型凭据展示口径测试。
 *
 * 这里测的全是**容易静默出错的判断**：请求体里该不该出现某个字段、编辑时会不会
 * 把 key 写坏、相对时间的边界、拉模型列表该走哪条路。这些问题 `tsc` 看不见 ——
 * 字段多传一个、少传一个都是合法类型，但行为完全不同。
 */
import { describe, expect, it } from "vitest";

import type { LlmCredentialItem, LlmModelListResponse, LlmProviderItem } from "@v2/contracts/model";
import {
  baseUrlHost,
  buildCreateBody,
  buildModelListBody,
  buildUpdateBody,
  credentialSummary,
  credentialTitle,
  describeCheckAge,
  describeCheckResult,
  describeModelId,
  emptyFormValues,
  formProblem,
  formValuesFromItem,
  modelFetchPlan,
  modelListHint,
  modelOptions,
  phaseFromResponse,
  type CredentialFormValues,
  type ModelListPhase,
} from "@v2/ui-model-config/model-credential-view";

const NOW = 1_800_000_000;

function _item(overrides: Partial<LlmCredentialItem> = {}): LlmCredentialItem {
  return {
    credential_id: "cred-1",
    provider: "deepseek",
    provider_name: "DeepSeek",
    label: "",
    model: "deepseek-flash",
    base_url: null,
    effective_base_url: "https://api.deepseek.com",
    api_key_masked: "sk-abc****3456",
    has_api_key: true,
    is_active: true,
    last_check_at: null,
    last_check_ok: null,
    last_check_message: null,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

function _provider(overrides: Partial<LlmProviderItem> = {}): LlmProviderItem {
  return {
    id: "deepseek",
    name: "DeepSeek",
    base_url: "https://api.deepseek.com",
    default_model: "deepseek-flash",
    api_key_envs: ["DEEPSEEK_API_KEY"],
    requires_model: false,
    ...overrides,
  };
}

function _values(overrides: Partial<CredentialFormValues> = {}): CredentialFormValues {
  return {
    provider: "deepseek",
    label: "",
    model: "deepseek-flash",
    apiKey: "",
    baseUrl: "",
    ...overrides,
  };
}

describe("credentialTitle", () => {
  it("有备注名时用备注名", () => {
    expect(credentialTitle(_item({ label: "主号" }))).toBe("主号");
  });

  it("没备注名时退回供应商名，不留空", () => {
    expect(credentialTitle(_item({ label: "   " }))).toBe("DeepSeek");
  });

  it("供应商名也空时退回 id，仍然不留空", () => {
    expect(credentialTitle(_item({ label: "", provider_name: "" }))).toBe("deepseek");
  });
});

describe("baseUrlHost", () => {
  it("取主机名而不是整条地址", () => {
    expect(baseUrlHost("https://ark.cn-beijing.volces.com/api/v3")).toBe("ark.cn-beijing.volces.com");
  });

  it("空值给破折号，不给空串", () => {
    expect(baseUrlHost("")).toBe("—");
  });

  it("解析不了的地址原样回显，不吞成破折号", () => {
    expect(baseUrlHost("not a url")).toBe("not a url");
  });
});

describe("credentialSummary", () => {
  it("模型 + 实际生效地址", () => {
    expect(credentialSummary(_item())).toBe("deepseek-flash · api.deepseek.com");
  });

  it("模型为空时明说未填，不显示成一个空槽", () => {
    expect(credentialSummary(_item({ model: "" }))).toContain("未填模型");
  });
});

describe("describeCheckAge", () => {
  it("从未检测过也给一句话", () => {
    expect(describeCheckAge(_item(), NOW)).toBe("尚未检测");
  });

  it("通过时带相对时间", () => {
    expect(describeCheckAge(_item({ last_check_at: NOW - 180, last_check_ok: true }), NOW)).toBe(
      "3 分钟前检测通过",
    );
  });

  it("失败时说的是失败，不是「检测过」", () => {
    expect(describeCheckAge(_item({ last_check_at: NOW - 7200, last_check_ok: false }), NOW)).toBe(
      "2 小时前检测失败",
    );
  });

  it("时间戳是 0 时按未检测处理，不显示成 1970 年", () => {
    expect(describeCheckAge(_item({ last_check_at: 0, last_check_ok: true }), NOW)).toBe("尚未检测");
  });
});

describe("describeCheckResult", () => {
  it("用后端拼好的文案（带耗时）", () => {
    expect(
      describeCheckResult({ ok: true, message: "连通，耗时 320 ms", provider: "deepseek", model: "m" }),
    ).toBe("连通，耗时 320 ms");
  });

  it("文案为空时按成败兜底，不显示空白气泡", () => {
    expect(describeCheckResult({ ok: false, message: "  ", provider: "x", model: "m" })).toBe("检测失败");
  });
});

describe("buildCreateBody", () => {
  it("地址留空落成 null（= 跟随供应商默认），不是空串", () => {
    const body = buildCreateBody(_values({ baseUrl: "   " }));
    expect(body.base_url).toBeNull();
  });

  it("默认新建即生效", () => {
    expect(buildCreateBody(_values()).activate).toBe(true);
    expect(buildCreateBody(_values(), { activate: false }).activate).toBe(false);
  });

  it("字段两侧空白被去掉", () => {
    const body = buildCreateBody(_values({ label: " 主号 ", apiKey: " sk-x ", model: " m " }));
    expect(body.label).toBe("主号");
    expect(body.api_key).toBe("sk-x");
    expect(body.model).toBe("m");
  });
});

describe("buildUpdateBody", () => {
  it("key 留空时**不带**该字段 —— 带了空串会把 key 写坏", () => {
    const body = buildUpdateBody(_values({ apiKey: "" }));
    expect("api_key" in body).toBe(false);
  });

  it("填了 key 才带上", () => {
    expect(buildUpdateBody(_values({ apiKey: " sk-new " })).api_key).toBe("sk-new");
  });

  it("地址留空落成 null（= 恢复供应商默认地址）", () => {
    expect(buildUpdateBody(_values({ baseUrl: "" })).base_url).toBeNull();
    expect(buildUpdateBody(_values({ baseUrl: "https://proxy.example.com" })).base_url).toBe(
      "https://proxy.example.com",
    );
  });

  it("模型留空时不带该字段（= 保持原值）", () => {
    expect("model" in buildUpdateBody(_values({ model: "  " }))).toBe(false);
    expect(buildUpdateBody(_values({ model: "ep-2026" })).model).toBe("ep-2026");
  });
});

describe("formValuesFromItem", () => {
  it("编辑时 key 留空：前端拿不到原文，留空即不改", () => {
    expect(formValuesFromItem(_item({ label: "主号" })).apiKey).toBe("");
  });

  it("地址回填自定义值；为 null 时留空", () => {
    expect(formValuesFromItem(_item({ base_url: "https://proxy.example.com" })).baseUrl).toBe(
      "https://proxy.example.com",
    );
    expect(formValuesFromItem(_item({ base_url: null })).baseUrl).toBe("");
  });
});

describe("emptyFormValues", () => {
  it("模型预填供应商默认值", () => {
    expect(emptyFormValues(_provider()).model).toBe("deepseek-flash");
  });

  it("豆包没有默认模型就留空，交给用户手填", () => {
    expect(emptyFormValues(_provider({ id: "doubao", default_model: null })).model).toBe("");
  });
});

describe("formProblem", () => {
  it("没选供应商", () => {
    expect(formProblem(_values({ provider: "" }), _provider(), { isEdit: false })).toBe("请选择供应商");
  });

  it("目录标了必填模型却没填", () => {
    const doubao = _provider({ id: "doubao", name: "豆包", default_model: null, requires_model: true });
    expect(formProblem(_values({ provider: "doubao", model: "" }), doubao, { isEdit: false })).toContain(
      "豆包",
    );
  });

  it("新建必须有 key", () => {
    expect(formProblem(_values({ apiKey: "" }), _provider(), { isEdit: false })).toBe("请填 API Key");
  });

  it("编辑时 key 留空是合法的（不改）", () => {
    expect(formProblem(_values({ apiKey: "" }), _provider(), { isEdit: true })).toBeNull();
  });
});

// --------------------------------------------------------------------------- 模型列表

function _response(overrides: Partial<LlmModelListResponse> = {}): LlmModelListResponse {
  return {
    ok: true,
    provider: "deepseek",
    models: ["deepseek-flash"],
    default_model: "deepseek-flash",
    current_model: null,
    message: null,
    ...overrides,
  };
}

function _ready(overrides: Partial<Extract<ModelListPhase, { kind: "ready" }>> = {}): ModelListPhase {
  return {
    kind: "ready",
    models: ["deepseek-flash"],
    defaultModel: "deepseek-flash",
    note: null,
    ...overrides,
  };
}

describe("buildModelListBody", () => {
  it("字段两侧空白去掉；地址留空落成 null（= 跟随供应商默认）", () => {
    const body = buildModelListBody(_values({ provider: " deepseek ", apiKey: " sk-x ", baseUrl: "  " }));
    expect(body).toEqual({ provider: "deepseek", api_key: "sk-x", base_url: null });
  });

  it("填了地址就原样带上（拉列表与正式调用必须打同一个地址）", () => {
    expect(buildModelListBody(_values({ baseUrl: "https://proxy.example.com/v1" })).base_url).toBe(
      "https://proxy.example.com/v1",
    );
  });
});

describe("modelFetchPlan", () => {
  it("没选供应商时先挡住", () => {
    const plan = modelFetchPlan({ isEdit: false, savedProvider: "", provider: "", hasKey: true });
    expect(plan).toEqual({ kind: "blocked", reason: "先选供应商" });
  });

  it("新建态没填 key 就等着，不说成错误", () => {
    const plan = modelFetchPlan({ isEdit: false, savedProvider: "", provider: "deepseek", hasKey: false });
    expect(plan.kind).toBe("blocked");
    expect(plan.kind === "blocked" && plan.reason).toContain("填好 API Key");
  });

  it("新建态填了 key 就用表单里的参数拉", () => {
    expect(modelFetchPlan({ isEdit: false, savedProvider: "", provider: "deepseek", hasKey: true })).toEqual({
      kind: "draft",
    });
  });

  it("编辑态且供应商没换：用库里那把 key 拉（浏览器里没有原文）", () => {
    expect(
      modelFetchPlan({ isEdit: true, savedProvider: "deepseek", provider: "deepseek", hasKey: false }),
    ).toEqual({ kind: "credential" });
  });

  it("编辑态换了供应商：不能拿旧供应商的 key 去新家拉 —— 那会报成「key 无效」", () => {
    const plan = modelFetchPlan({
      isEdit: true,
      savedProvider: "deepseek",
      provider: "doubao",
      hasKey: false,
    });
    expect(plan.kind).toBe("blocked");
    expect(plan.kind === "blocked" && plan.reason).toContain("新的 API Key");
  });

  it("编辑态换了供应商并填了新 key：用表单参数拉", () => {
    expect(
      modelFetchPlan({ isEdit: true, savedProvider: "deepseek", provider: "doubao", hasKey: true }),
    ).toEqual({ kind: "draft" });
  });
});

describe("phaseFromResponse", () => {
  it("ok=false 收成 failed，文案就是后端那句", () => {
    const phase = phaseFromResponse(_response({ ok: false, models: [], message: "API key 无效或已过期" }));
    expect(phase).toEqual({ kind: "failed", reason: "API key 无效或已过期" });
  });

  it("ok=false 但后端没给原因时也要有话说", () => {
    const phase = phaseFromResponse(_response({ ok: false, models: [], message: null }));
    expect(phase.kind === "failed" && phase.reason.length > 0).toBe(true);
  });

  it("ok=true 时过滤掉空 id —— 否则会多出一张点不动的空白卡片", () => {
    const phase = phaseFromResponse(_response({ models: ["a", "", "  ", "b"] }));
    expect(phase.kind === "ready" && phase.models).toEqual(["a", "b"]);
  });

  it("空列表提示原样收进 note", () => {
    const phase = phaseFromResponse(
      _response({ models: [], message: "上游没有返回任何模型，可以手动填写模型名" }),
    );
    expect(phase.kind === "ready" && phase.note).toBe("上游没有返回任何模型，可以手动填写模型名");
  });
});

describe("describeModelId", () => {
  it("认得的人话标签", () => {
    expect(describeModelId("deepseek-flash")).toContain("快速");
  });

  it("认不出的原样回显 id，不猜一个中文名", () => {
    expect(describeModelId("ep-20260917-abcdef")).toBe("ep-20260917-abcdef");
  });

  it("空白给空串，不给一个空格", () => {
    expect(describeModelId("   ")).toBe("");
  });
});

describe("modelOptions", () => {
  it("顺序沿用上游给的，不自己重排", () => {
    const phase = _ready({ models: ["b", "a"], defaultModel: null });
    expect(modelOptions(phase, "").map((option) => option.id)).toEqual(["b", "a"]);
  });

  it("「默认」只挂在目录默认模型那一个上", () => {
    const phase = _ready({ models: ["a", "deepseek-flash"], defaultModel: "deepseek-flash" });
    expect(modelOptions(phase, "").map((option) => option.isDefault)).toEqual([false, true]);
  });

  it("默认模型为 null 时谁都不挂「默认」", () => {
    const phase = _ready({ models: ["a"], defaultModel: null });
    expect(modelOptions(phase, "").some((option) => option.isDefault)).toBe(false);
  });

  it("选中但不在列表里的模型补到最前面并标「已选」—— 编辑老凭据时不能一张都不选中", () => {
    const phase = _ready({ models: ["a", "b"] });
    const options = modelOptions(phase, "ep-2026");
    expect(options[0]).toEqual({ id: "ep-2026", label: "ep-2026", isDefault: false, isSelected: true });
    expect(options).toHaveLength(3);
  });

  it("选中项在列表里就不重复补一条", () => {
    const phase = _ready({ models: ["a", "b"] });
    const options = modelOptions(phase, "b");
    expect(options.map((option) => option.id)).toEqual(["a", "b"]);
    expect(options[1]?.isSelected).toBe(true);
  });

  it("还没拉到（blocked / loading / failed）时没有卡片", () => {
    expect(modelOptions({ kind: "loading" }, "a")).toEqual([]);
    expect(modelOptions({ kind: "blocked", reason: "x" }, "a")).toEqual([]);
    expect(modelOptions({ kind: "failed", reason: "x" }, "a")).toEqual([]);
  });
});

describe("modelListHint", () => {
  it("blocked 直接说为什么还不能拉", () => {
    expect(modelListHint({ kind: "blocked", reason: "填好 API Key 后自动拉取可用模型" })).toBe(
      "填好 API Key 后自动拉取可用模型",
    );
  });

  it("loading 说正在拉", () => {
    expect(modelListHint({ kind: "loading" })).toContain("正在");
  });

  it("failed 除了原因还要给出路（可以手填）", () => {
    expect(modelListHint({ kind: "failed", reason: "API key 无效或已过期" })).toBe(
      "API key 无效或已过期。可以手动填写模型名",
    );
  });

  it("拉到多个时报个数", () => {
    expect(modelListHint(_ready({ models: ["a", "b", "c"] }))).toBe("共 3 个可用模型");
  });

  it("空列表用后端那句提示（方舟这类只认接入点 ID 的账号就靠它）", () => {
    expect(modelListHint(_ready({ models: [], note: "上游没有返回任何模型，可以手动填写模型名" }))).toBe(
      "上游没有返回任何模型，可以手动填写模型名",
    );
  });

  it("空列表且后端没给提示时也要有话说，不能留空", () => {
    expect(modelListHint(_ready({ models: [], note: null }))).toContain("手动填写");
  });
});
