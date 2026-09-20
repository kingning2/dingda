/**
 * 模型列表的获取状态机。
 *
 * 职责：
 *     按「供应商 + key + 地址」拉一次可用模型列表，把响应收成 `ModelListPhase`，
 *     并保证只有最后一次请求的结果会写进状态。
 *
 * 设计说明：
 *     - **触发点显式，不写成依赖 `values` 的 effect**：拉取的时机有五个（打开弹窗、
 *       换供应商、key 失焦、地址失焦、点「重新获取」），全部由调用方显式调
 *       `load(values)`。写成 effect 的话用户每敲一个字符 key 就发一次请求 ——
 *       既打爆上游，也让 key 原文在多个请求里反复出现
 *     - **用序号而不是 `AbortController` 防竞态**：请求已经发出去了，取消只省一次解析；
 *       真正要防的是「先发的后到」把新列表覆盖成旧的
 *     - **拉不到不是异常**：`phaseFromResponse` 把 `ok=false` 收成 `failed` 状态，
 *       文案直接用后端给的那句（`llm.auth_failed` → 「API key 无效或已过期」）。
 *       只有网络层真的断了才走 `catch`
 */

import { useCallback, useRef, useState } from "react";

import { listLlmCredentialModels, listLlmModelsForDraft } from "./model-config-api";
import {
  buildModelListBody,
  modelFetchPlan,
  phaseFromResponse,
  type CredentialFormValues,
  type ModelListPhase,
} from "./model-credential-view";

interface UseModelListInput {
  /** 编辑态传已保存凭据 id；新增态传 `null`。 */
  credentialId: string | null;
  /**
   * 编辑态这条凭据**原本**的供应商；新增态传空串。
   *
   * 用来判断「是不是换了供应商」：换了就得用新 key 拉，不能拿库里那把旧供应商的 key。
   */
  savedProvider: string;
}

/** 模型列表的获取状态机；返回当前状态与一个显式的拉取函数。 */
export function useModelList({ credentialId, savedProvider }: UseModelListInput) {
  // 初值给 loading：表单每次打开都会立刻 `load()`，真跑起来时这个值几乎看不到
  const [phase, setPhase] = useState<ModelListPhase>({ kind: "loading" });
  /** 已发出的请求序号；只有序号最大的那次能写状态。 */
  const latest = useRef(0);

  const load = useCallback(
    (values: CredentialFormValues) => {
      const plan = modelFetchPlan({
        isEdit: credentialId !== null,
        savedProvider,
        provider: values.provider,
        hasKey: Boolean(values.apiKey.trim()),
      });

      // 先占号再判断：条件变了要让在途请求的结果作废，否则它回来会盖掉 blocked
      latest.current += 1;
      const seq = latest.current;

      if (plan.kind === "blocked") {
        setPhase({ kind: "blocked", reason: plan.reason });
        return;
      }

      setPhase({ kind: "loading" });
      const request =
        plan.kind === "credential" && credentialId
          ? listLlmCredentialModels(credentialId)
          : listLlmModelsForDraft(buildModelListBody(values));

      void request
        .then((response) => {
          if (seq !== latest.current) return;
          setPhase(phaseFromResponse(response));
        })
        .catch((error: unknown) => {
          if (seq !== latest.current) return;
          setPhase({
            kind: "failed",
            reason: error instanceof Error ? error.message : "拉取可用模型失败",
          });
        });
    },
    [credentialId, savedProvider],
  );

  return { phase, load };
}
