/**
 * 模型卡片网格。
 *
 * 职责：
 *     把一组可选模型渲染成可点选的卡片，标出「默认」与「已选」，把选中结果回给调用方。
 *
 * 设计说明：
 *     - 卡片主行是**模型 id 本身**（等宽字体）：用户要拿它去供应商控制台里对上号，
 *       人话标签只是辅助说明。认不出的 id 没有标签，卡片就只显示 id
 *     - 用原生 `button` 而不是 `Select`：这里是「一眼看全 + 一次点选」，下拉框会把
 *       列表藏起来，而用户恰恰需要横向对比几个模型
 *     - 选中态靠**边框 + 勾选图标 + 徽章**三重表达，不只换背景色 —— 深色主题下
 *       只换底色几乎看不出来
 *     - 未选中的卡片也占着勾选图标的位置（`text-transparent`），否则点选时整行会左右跳
 */

import { Badge } from "@v2/ui-primitives/badge";
import { cn } from "@v2/ui-primitives/utils";
import { Check } from "lucide-react";

import type { ModelOption } from "./model-credential-view";

interface ModelPickerProps {
  options: ModelOption[];
  disabled?: boolean;
  onSelect: (id: string) => void;
}

/** 模型卡片网格；高度封顶后自己滚，不把弹窗撑长。 */
export function ModelPicker({ options, disabled = false, onSelect }: ModelPickerProps) {
  return (
    <div className="grid max-h-60 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          disabled={disabled}
          aria-pressed={option.isSelected}
          onClick={() => onSelect(option.id)}
          className={cn(
            "flex cursor-pointer flex-col items-start gap-1 rounded-lg border px-3 py-2 text-left transition",
            option.isSelected
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/40 hover:bg-muted/50",
            disabled && "cursor-not-allowed opacity-60",
          )}
        >
          <span className="flex w-full min-w-0 items-center gap-1.5">
            <Check
              className={cn(
                "size-3.5 shrink-0",
                option.isSelected ? "text-primary" : "text-transparent",
              )}
            />
            <span className="truncate font-mono text-[13px]">{option.id}</span>
          </span>
          {option.label === option.id ? null : (
            <span className="pl-5 text-xs text-muted-foreground">{option.label}</span>
          )}
          {option.isSelected || option.isDefault ? (
            <span className="flex flex-wrap gap-1 pl-5">
              {option.isSelected ? <Badge variant="secondary">已选</Badge> : null}
              {option.isDefault ? <Badge variant="outline">默认</Badge> : null}
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
