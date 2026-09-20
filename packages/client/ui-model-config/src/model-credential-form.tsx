/**
 * 新增 / 编辑模型凭据的弹窗。
 *
 * 职责：
 *     收集供应商、备注名、模型、API Key、接口地址，提交给后端并给出成功 / 失败提示；
 *     模型字段的可用列表在填好 key 后自动拉取。
 *
 * 设计说明：
 *     - 新增与编辑**共用同一个组件**：字段完全一样，差异只有标题文案与
 *       「key 留空 = 不改」这一条
 *     - **编辑时不回填 key 原文**（后端只回掩码，前端也拿不到）。所以 key 输入框在编辑态
 *       留空即保持原值 —— 占位符必须写清楚，否则用户会以为 key 丢了
 *     - 切换供应商时把模型重置成该供应商的默认值：否则把 DeepSeek 的模型名
 *       带到豆包的凭据上，保存成功但一调用就 404
 *     - **拉模型的时机是显式的**，不是 `useEffect` 盯着 `values`：那样每敲一个字符
 *       就发一次请求。这里只有五个触发点 —— 打开弹窗、换供应商、key 失焦、地址失焦、
 *       点「重新获取」
 *     - 提示走 `pushAppAlert`：弹窗一关，行内提示就看不见了
 *     - 值交给 TanStack Form 托管（`useForm`）。但**不挂 `validators`**：`formProblem`
 *       才是校验的唯一出处，挂上去等于同一个判断存两处；且 `canSubmit` 在挂载时恒为
 *       true（form-core 的首个分支是 `submissionAttempts === 0 && !isTouched`），
 *       反而会放过空表单提交。所以保存按钮的可用性仍由 `formProblem` 现算
 *     - 这里不用 `form.Field` 而是整体一个 `form.Subscribe`：字段大多不是原生输入
 *       （Radix `Select`、`ModelPicker`），且接口地址的占位符、模型字段、提交按钮都
 *       要看**别的**字段的值。逐字段订阅要嵌三层 `Subscribe` 才能拿到 `provider`，
 *       而这个弹窗在改前就是「任一字段变 → 整块重渲染」，没有性能可退
 *     - 订阅同时取 `values` 与 `isSubmitting`：`form.state` 是普通 getter，
 *       渲染期读它不会随 store 变化重渲染；只订 `values` 会让按钮漏掉提交态
 */

import { useForm } from "@tanstack/react-form";
import type { LlmCredentialItem, LlmProviderItem } from "@v2/contracts/model";
import { pushAppAlert } from "@v2/runtime/app-alert";
import { Button } from "@v2/ui-primitives/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@v2/ui-primitives/dialog";
import { FormField } from "@v2/ui-primitives/form-field";
import { Input } from "@v2/ui-primitives/input";
import { cn } from "@v2/ui-primitives/utils";
import { Check, KeyRound } from "lucide-react";
import { useEffect } from "react";

import { createLlmCredential, updateLlmCredential } from "./model-config-api";
import { ModelField } from "./model-field";
import {
  buildCreateBody,
  buildUpdateBody,
  credentialTitle,
  emptyFormValues,
  formProblem,
  formValuesFromItem,
  type CredentialFormValues,
} from "./model-credential-view";
import { ProviderIcon } from "./provider-icon";
import { useModelList } from "./use-model-list";

interface ModelCredentialFormProps {
  open: boolean;
  providers: LlmProviderItem[];
  /** `null` 表示新增。 */
  item: LlmCredentialItem | null;
  onOpenChange: (open: boolean) => void;
  /** 保存成功后回调，由上层刷新列表。 */
  onSaved: () => void;
}

/** 「新增凭据」/「编辑凭据」弹窗。 */
export function ModelCredentialForm({
  open,
  providers,
  item,
  onOpenChange,
  onSaved,
}: ModelCredentialFormProps) {
  const isEdit = item !== null;

  const { phase, load } = useModelList({
    credentialId: item?.credential_id ?? null,
    savedProvider: item?.provider ?? "",
  });

  const form = useForm({
    defaultValues: emptyFormValues(providers[0]),
    onSubmit: async ({ value }) => {
      try {
        if (isEdit && item) {
          await updateLlmCredential(item.credential_id, buildUpdateBody(value));
          pushAppAlert({ title: "已保存", description: `${credentialTitle(item)} 已更新` });
        } else {
          const created = await createLlmCredential(buildCreateBody(value));
          pushAppAlert({
            title: "已新增",
            description: created.is_active
              ? `${credentialTitle(created)} 已生效`
              : `${credentialTitle(created)} 已保存，尚未生效`,
          });
        }
        onOpenChange(false);
        onSaved();
      } catch (error) {
        pushAppAlert({
          title: isEdit ? "保存失败" : "新增失败",
          description: error instanceof Error ? error.message : "请稍后重试",
          variant: "destructive",
        });
      }
    },
  });

  useEffect(() => {
    if (!open) return;
    const next = item ? formValuesFromItem(item) : emptyFormValues(providers[0]);
    form.reset(next);
    form.setFieldValue("provider", next.provider);
    form.setFieldValue("label", next.label);
    form.setFieldValue("model", next.model);
    form.setFieldValue("apiKey", next.apiKey);
    form.setFieldValue("baseUrl", next.baseUrl);
    load(next);
    // providers 是目录，进程内是常量：上层重拉它只会在弹窗关着的时候发生，
    // 所以「目录变了就重置表单」不会打断用户正在填的内容
  }, [open, item, providers, load, form]);

  function handleProviderChange(nextId: string) {
    const nextProvider = providers.find((provider) => provider.id === nextId);
    const nextValues: CredentialFormValues = {
      ...form.state.values,
      provider: nextId,
      model: nextProvider?.default_model ?? "",
    };
    form.setFieldValue("provider", nextValues.provider);
    form.setFieldValue("model", nextValues.model);
    load(nextValues);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑模型凭据" : "新增模型凭据"}</DialogTitle>
          <DialogDescription>
            同一时间只有一条凭据生效，其余作为备用留在列表里。
          </DialogDescription>
        </DialogHeader>

        <form.Subscribe selector={(state) => ({ values: state.values, isSubmitting: state.isSubmitting })}>
          {({ values, isSubmitting }) => {
            const selected = providers.find((provider) => provider.id === values.provider);
            const problem = formProblem(values, selected, { isEdit });

            return (
              <>
                <div className="flex flex-col gap-3">
                  <FormField label="供应商">
                    <div
                      role="radiogroup"
                      aria-label="选择模型供应商"
                      className="grid gap-2 sm:grid-cols-2"
                    >
                      {providers.map((provider) => {
                        const selectedProvider = provider.id === values.provider;

                        return (
                          <button
                            key={provider.id}
                            type="button"
                            role="radio"
                            aria-checked={selectedProvider}
                            className={cn(
                              "flex min-w-0 items-center gap-3 rounded-xl border p-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                              selectedProvider && "border-ring bg-muted/50 ring-2 ring-ring/25",
                            )}
                            onClick={() => handleProviderChange(provider.id)}
                          >
                            <ProviderIcon id={provider.id} />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium">{provider.name}</span>
                              <span className="block truncate text-xs text-muted-foreground">
                                {provider.default_model
                                  ? `默认 ${provider.default_model}`
                                  : provider.id === "doubao"
                                    ? "填写接入点 ID"
                                    : "填写模型 / 接入点 ID"}
                              </span>
                            </span>
                            <Check
                              className={cn(
                                "size-4 shrink-0 text-primary",
                                !selectedProvider && "opacity-0",
                              )}
                            />
                          </button>
                        );
                      })}
                    </div>
                  </FormField>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="备注名" htmlFor="credential-label">
                      <Input
                        id="credential-label"
                        value={values.label}
                        onChange={(event) => form.setFieldValue("label", event.target.value)}
                        placeholder="主号 / 备用"
                      />
                    </FormField>

                    <FormField
                      label="API Key"
                      htmlFor="credential-api-key"
                      hint={
                        isEdit && item ? (
                          <>
                            <span className="font-mono">当前 Key：{item.api_key_masked || "—"}</span>
                            <span>留空表示继续使用这把 Key。</span>
                          </>
                        ) : (
                          "离开本框自动拉取可用模型。"
                        )
                      }
                    >
                      <div className="relative">
                        <KeyRound className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          id="credential-api-key"
                          type="password"
                          value={values.apiKey}
                          onChange={(event) => form.setFieldValue("apiKey", event.target.value)}
                          onBlur={() => load(form.state.values)}
                          placeholder={isEdit ? "留空表示不修改" : "粘贴 Key"}
                          className="px-8"
                          autoComplete="off"
                        />
                      </div>
                    </FormField>
                  </div>

                  <ModelField
                    phase={phase}
                    selected={values.model}
                    provider={selected}
                    onModelChange={(model) => form.setFieldValue("model", model)}
                    onRefresh={() => load(form.state.values)}
                  />

                  <FormField
                    label="接口地址"
                    htmlFor="credential-base-url"
                    hint="走代理或换区域时才需要填；清空即恢复默认。换地址后离开本框会重新拉模型。"
                  >
                    <Input
                      id="credential-base-url"
                      value={values.baseUrl}
                      onChange={(event) => form.setFieldValue("baseUrl", event.target.value)}
                      onBlur={() => load(form.state.values)}
                      placeholder={selected ? `留空用默认：${selected.base_url}` : "留空用供应商默认地址"}
                    />
                  </FormField>
                </div>

                <DialogFooter>
                  <Button variant="outline" onClick={() => onOpenChange(false)}>
                    取消
                  </Button>
                  <Button
                    onClick={() => void form.handleSubmit()}
                    disabled={Boolean(problem) || isSubmitting}
                  >
                    {isSubmitting ? "正在保存…" : "保存"}
                  </Button>
                </DialogFooter>
              </>
            );
          }}
        </form.Subscribe>
      </DialogContent>
    </Dialog>
  );
}
