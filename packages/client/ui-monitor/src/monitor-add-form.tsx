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
 */

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

/** 「加入监控」按钮 + 弹窗表单。 */
export function MonitorAddForm({ onAdded }: MonitorAddFormProps) {
  const [open, setOpen] = useState(false);
  const [platform, setPlatform] = useState<string>(MONITOR_PLATFORMS[0].id);
  const [rawItemId, setRawItemId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const itemId = normalizeItemId(rawItemId);

  async function handleSubmit() {
    if (!itemId || submitting) return;
    setSubmitting(true);
    try {
      const response = await addMonitorTargets({ items: [{ platform, item_id: itemId }] });
      pushAppAlert({
        title: "已加入监控",
        description: describeAdded(response),
      });
      setRawItemId("");
      setOpen(false);
      onAdded();
    } catch (error) {
      pushAppAlert({
        title: "加入监控失败",
        description: error instanceof Error ? error.message : "请稍后重试",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  }

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
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted-foreground">平台</span>
              <Select value={platform} onValueChange={(value) => setPlatform(String(value))}>
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
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted-foreground">商品 ID</span>
              <Input
                value={rawItemId}
                onChange={(event) => setRawItemId(event.target.value)}
                placeholder="商品 ID，或直接粘贴商品链接"
                autoFocus
                onKeyDown={(event) => {
                  if (event.key === "Enter") void handleSubmit();
                }}
              />
              {rawItemId.trim() && itemId !== rawItemId.trim() ? (
                <span className="text-xs text-muted-foreground">将使用 ID：{itemId}</span>
              ) : null}
            </label>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleSubmit()} disabled={!itemId || submitting}>
              {submitting ? "正在加入…" : "加入"}
            </Button>
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
