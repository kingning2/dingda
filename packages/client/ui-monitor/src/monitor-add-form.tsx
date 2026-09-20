/**
 * 手动加入监控：填平台 + 商品 ID。
 *
 * 职责：
 *     弹窗收集平台与商品 ID，调批量端点加入监控，并给出成功/失败提示。
 *
 * 设计说明：
 *     - 只要两个字段。标题、价格、封面由后端在首次轮询时回填（`save_poll_snapshot`
 *       会在目标标题为空时补上），让用户填这些等于把负担转嫁给他。
 *     - 商品 ID 允许直接粘贴闲鱼链接：闲鱼商品链接末尾就是 item_id，后端不做解析，
 *       但用户复制时经常连链接一起复制，这里做一次宽松提取比让他自己截更友好。
 *     - 提示用 `pushAppAlert` 而不是行内文案：弹窗关闭后行内提示就看不见了。
 *     - 值交给 TanStack Form 托管，但**不挂 `validators`**：`normalizeItemId` 与
 *       `formProblem`（见 model-config）这类纯函数才是校验的唯一出处，挂上
 *       `validators.onChange` 会让同一个判断存在两处，且 `canSubmit` 在挂载时
 *       恒为 true（form-core 的 `canSubmit` 首个分支是 `submissionAttempts === 0
 *       && !isTouched`），反而放过空表单提交。按钮的可用性用 `form.Subscribe`
 *       现算。`form.Field` 只负责取值与改值。
 */

import { useForm } from "@tanstack/react-form";
import type { MonitorAddResponse } from "@v2/contracts/monitor";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@v2/ui-primitives/select";
import { Plus } from "lucide-react";
import { useState } from "react";

import { addMonitorTargets } from "./monitor-api";
import { normalizeItemId } from "./monitor-item-id";
import { MONITOR_PLATFORMS } from "./monitor-platforms";

interface MonitorAddFormProps {
  /** 加入成功后回调，由上层刷新列表。 */
  onAdded: () => void;
}

/**
 * 默认平台。显式标 `string` 而不是靠推断：`MONITOR_PLATFORMS` 是 `as const`，
 * 推断会把表单值的类型收成字面量 `"xianyu"`，之后 `handleChange` 就只认这一个值了。
 */
const DEFAULT_PLATFORM: string = MONITOR_PLATFORMS[0].id;

/** 「加入监控」按钮 + 弹窗表单。 */
export function MonitorAddForm({ onAdded }: MonitorAddFormProps) {
  const [open, setOpen] = useState(false);

  const form = useForm({
    defaultValues: {
      platform: DEFAULT_PLATFORM,
      rawItemId: "",
    },
    onSubmit: async ({ value, formApi }) => {
      const itemId = normalizeItemId(value.rawItemId);
      if (!itemId) return;
      try {
        const response = await addMonitorTargets({
          items: [{ platform: value.platform, item_id: itemId }],
        });
        pushAppAlert({
          title: "已加入监控",
          description: describeAdded(response),
        });
        // 只清商品 ID、保留平台：连着加同一平台的多个商品是常态。
        formApi.setFieldValue("rawItemId", "");
        setOpen(false);
        onAdded();
      } catch (error) {
        pushAppAlert({
          title: "加入监控失败",
          description: error instanceof Error ? error.message : "请稍后重试",
          variant: "destructive",
        });
      }
    },
  });

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus className="size-4" />
        加入监控
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>加入监控</DialogTitle>
            <DialogDescription>
              填平台与商品 ID 即可。标题、价格与封面会在首次轮询后自动补齐。
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-3">
            <form.Field name="platform">
              {(field) => (
                <FormField label="平台">
                  <Select
                    value={field.state.value}
                    onValueChange={(value) => field.handleChange(String(value))}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MONITOR_PLATFORMS.map((item) => (
                        <SelectItem key={item.id} value={item.id}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
              )}
            </form.Field>

            <form.Field name="rawItemId">
              {(field) => {
                const raw = field.state.value;
                const itemId = normalizeItemId(raw);
                const trimmed = raw.trim();
                return (
                  <FormField
                    label="商品 ID"
                    htmlFor="monitor-add-item-id"
                    hint={trimmed && itemId !== trimmed ? `将使用 ID：${itemId}` : undefined}
                  >
                    <Input
                      id="monitor-add-item-id"
                      value={raw}
                      onChange={(event) => field.handleChange(event.target.value)}
                      placeholder="商品 ID，或直接粘贴商品链接"
                      autoFocus
                      onKeyDown={(event) => {
                        if (event.key === "Enter") void form.handleSubmit();
                      }}
                    />
                  </FormField>
                );
              }}
            </form.Field>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <form.Subscribe
              selector={(state) => ({
                ready: Boolean(normalizeItemId(state.values.rawItemId)),
                isSubmitting: state.isSubmitting,
              })}
            >
              {({ ready, isSubmitting }) => (
                <Button
                  onClick={() => void form.handleSubmit()}
                  disabled={!ready || isSubmitting}
                >
                  {isSubmitting ? "正在加入…" : "加入"}
                </Button>
              )}
            </form.Subscribe>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** 加入结果 → 一句人话。复用已存在的目标时「added」仍是 1，要说清是复用。 */
function describeAdded(response: MonitorAddResponse): string {
  if (response.added === 0) return "没有新增（该商品可能已在监控中）。";
  return `已在监控列表里，共 ${response.added} 条。首次轮询完成后会显示价格。`;
}
