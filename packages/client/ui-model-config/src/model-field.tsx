/**
 * 表单里的「模型」字段。
 *
 * 职责：
 *     把拉到的可用模型渲染成卡片供点选，拉不到时退回手填输入框，
 *     并给一行状态说明与「重新获取」按钮。
 *
 * 设计说明：
 *     - **永远留着手填出口**：`/models` 只回上游肯给的模型 —— 方舟只认推理接入点 ID
 *       （列表里根本没有）、有的中转只列一部分。只给卡片等于把这类账号锁死
 *     - 状态行**永远有字**：空着看起来像加载失败。四种状态的文案由 `modelListHint`
 *       统一给，组件里不做 `if` 拼字符串
 *     - 卡片与手填框互斥但**可切换**，且切过去之后不会被后台拉取结果切回来 ——
 *       用户刚做的选择不该被一次请求推翻
 *     - 排版走 `FormField`：标签行右侧的两个按钮是它的 `actions` 槽，两行状态说明是
 *       它的 `hint` 槽。状态行**逐行挂色**（拉取失败那行走危险色）而不是给整块
 *       `tone="error"`，所以失败时第二行仍是灰的
 */

import type { LlmProviderItem } from "@v2/contracts/model";
import { Button } from "@v2/ui-primitives/button";
import { FormField } from "@v2/ui-primitives/form-field";
import { Input } from "@v2/ui-primitives/input";
import { Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ModelPicker } from "./model-picker";
import { modelListHint, modelOptions, type ModelListPhase } from "./model-credential-view";

interface ModelFieldProps {
  phase: ModelListPhase;
  /** 表单当前选的模型；用来给对应卡片挂「已选」 */
  selected: string;
  /** 目录里这个供应商的一行；新增态还没选供应商时为 `undefined` */
  provider: LlmProviderItem | undefined;
  onModelChange: (model: string) => void;
  /** 点「重新获取」时调；由上层决定用哪条路拉 */
  onRefresh: () => void;
}

const MODEL_INPUT_ID = "credential-model";

/** 「模型」字段：卡片选择 + 手填兜底。 */
export function ModelField({ phase, selected, provider, onModelChange, onRefresh }: ModelFieldProps) {
  const [manual, setManual] = useState(false);
  const options = modelOptions(phase, selected);
  const hasCards = options.length > 0;
  const showCards = hasCards && !manual;
  const loading = phase.kind === "loading";

  return (
    <FormField
      label="模型"
      // 卡片态是 ModelPicker（一堆 button），没有可关联的输入框，不挂 <label>
      htmlFor={showCards ? undefined : MODEL_INPUT_ID}
      actions={
        <div className="flex items-center gap-1">
          {hasCards ? (
            <Button variant="link" size="xs" onClick={() => setManual((prev) => !prev)}>
              {showCards ? "手动填写" : "从列表选择"}
            </Button>
          ) : null}
          <Button variant="ghost" size="xs" onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            重新获取
          </Button>
        </div>
      }
      hint={
        <>
          <span className={phase.kind === "failed" ? "text-destructive" : undefined}>
            {modelListHint(phase)}
          </span>
          {provider?.requires_model ? (
            <span>
              {provider.name} 没有默认模型，必须填推理接入点 ID（形如 ep-xxxx）
            </span>
          ) : null}
        </>
      }
    >
      {showCards ? (
        <ModelPicker options={options} onSelect={onModelChange} disabled={loading} />
      ) : (
        <Input
          id={MODEL_INPUT_ID}
          value={selected}
          onChange={(event) => onModelChange(event.target.value)}
          placeholder={provider?.default_model ?? "必填"}
          className="font-mono"
        />
      )}
    </FormField>
  );
}
