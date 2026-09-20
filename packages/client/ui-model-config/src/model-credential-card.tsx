/**
 * 单条模型凭据卡片。
 *
 * 职责：
 *     显示一条凭据的供应商、备注名、模型、地址、掩码 key 与最近检测状态，
 *     并提供「测试连接 / 设为使用中 / 编辑 / 删除」四个动作。
 *
 * 设计说明：
 *     - **删除的二次确认留在本组件内**：确认弹窗与卡片是同一件事（删这一条），
 *       提到 Hub 会让「删的是哪条」这个状态多绕一圈
 *     - 检测结果由上层传进来（`check`），卡片只负责显示：结果属于「刚点过的那一次」，
 *       不是凭据的持久属性；持久那份是 `last_check_*`
 *     - 使用中的那条用主色描边 + 徽标，不靠排序位置表达 —— 列表会因更新而重排
 */

import type { LlmCheckView, LlmCredentialItem } from "@v2/contracts/model";
import { pushAppAlert } from "@v2/runtime/app-alert";
import { Badge } from "@v2/ui-primitives/badge";
import { Button } from "@v2/ui-primitives/button";
import { Card, CardContent } from "@v2/ui-primitives/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@v2/ui-primitives/dialog";
import { cn } from "@v2/ui-primitives/utils";
import { Check, Loader2, Pencil, Trash2, Zap } from "lucide-react";
import { useState } from "react";

import { deleteLlmCredential } from "./model-config-api";
import {
  checkTone,
  credentialSummary,
  credentialTitle,
  describeCheckAge,
  describeCheckResult,
} from "./model-credential-view";

interface ModelCredentialCardProps {
  item: LlmCredentialItem;
  /** 本次会话里刚跑出来的检测结果；没测过为 `null`。 */
  check: LlmCheckView | null;
  /** 一次渲染内固定的基准时间（Unix 秒），同屏几条相对时间才读得一致。 */
  now: number;
  /** 该条正在测试或切换。 */
  busy: boolean;
  onTest: () => void;
  onActivate: () => void;
  onEdit: () => void;
  /** 删除成功后回调，由上层刷新列表。 */
  onDeleted: () => void;
}

/** 一条凭据的卡片。 */
export function ModelCredentialCard({
  item,
  check,
  now,
  busy,
  onTest,
  onActivate,
  onEdit,
  onDeleted,
}: ModelCredentialCardProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (deleting) return;
    setDeleting(true);
    try {
      await deleteLlmCredential(item.credential_id);
      setConfirmOpen(false);
      pushAppAlert({ title: "已删除", description: `${credentialTitle(item)} 已从列表移除` });
      onDeleted();
    } catch (error) {
      pushAppAlert({
        title: "删除失败",
        description: error instanceof Error ? error.message : "请稍后重试",
        variant: "destructive",
      });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Card
      className={cn("transition", item.is_active && "border-primary/40")}
      data-testid={`model-credential-card-${item.credential_id}`}
    >
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="truncate text-[13px] font-medium">{credentialTitle(item)}</span>
          <span className="text-xs text-muted-foreground">{item.provider_name}</span>
          {item.is_active ? <Badge>使用中</Badge> : null}
        </div>

        <div className="flex flex-col gap-1 text-xs text-muted-foreground">
          <span>{credentialSummary(item)}</span>
          <span className="font-mono">Key {item.api_key_masked || "—"}</span>
          <span>{describeCheckAge(item, now)}</span>
        </div>

        {check ? (
          <p
            className={cn(
              "rounded-md px-2.5 py-1.5 text-xs",
              checkTone(check) === "ok"
                ? "bg-muted text-muted-foreground"
                : "bg-destructive/10 text-destructive",
            )}
          >
            {describeCheckResult(check)}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={onTest} disabled={busy}>
            {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Zap className="size-3.5" />}
            测试连接
          </Button>
          {item.is_active ? null : (
            <Button variant="outline" size="sm" onClick={onActivate} disabled={busy}>
              <Check className="size-3.5" />
              设为使用中
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onEdit} disabled={busy}>
            <Pencil className="size-3.5" />
            编辑
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive"
            onClick={() => setConfirmOpen(true)}
            disabled={busy}
          >
            <Trash2 className="size-3.5" />
            删除
          </Button>
        </div>
      </CardContent>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>删除这条凭据？</DialogTitle>
            <DialogDescription>
              {item.is_active
                ? "它正在生效，删除后需要手动选一条新的，否则模型调用会退回环境变量配置。"
                : "删除后不可恢复。"}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={() => void handleDelete()} disabled={deleting}>
              {deleting ? "正在删除…" : "删除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
