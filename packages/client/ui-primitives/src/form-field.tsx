/**
 * 表单字段容器：标签 / 控件 / 说明三段的统一排版。
 *
 * 职责：
 *     把「标签在上、控件居中、说明在下」这套重复了七八遍的排版收成一处，
 *     让各处的字号、间距与错误色只在一个地方定义。
 *
 * 设计说明：
 *     - 这是本包里**手写**的少数几个组件之一（其余都是 shadcn CLI 产物）：shadcn 没有
 *       对应物 —— 它的 `form` 要连带引入 react-hook-form 与 zod，为这点排版重复不值。
 *       但它仍守本包「无业务」这条线，不认识账号、监控、模型。
 *     - 标签与控件是**兄弟**节点，不是 `<label>` 包住控件：Radix 的 `Select` trigger 是个
 *       button，`<label>` 包住它关联不上，属于无效标记。所以要不要真 `<label>` 由
 *       `htmlFor` 决定 —— 传出控件的 id 才渲染 `<label>`，也才保留「点标签聚焦输入框」。
 *     - `hint` 收节点而非字符串：调用方有一行的也有两行的（`model-field` 是两行）。
 *       说明区自身是 `flex flex-col gap-1.5`，所以多行说明的行距与「控件↔说明」的
 *       间距一致；每行若要各自的语气（如「拉取失败」行单独走危险色），由调用方在行内
 *       自己挂色 —— 那也是 `tone` 只作用于整块的原因。
 */

import type { ReactNode } from "react";

import { cn } from "./utils";

interface FormFieldProps {
  label: string;
  /** 控件的 id。传出才渲染 `<label>`；`<Select>` 的 trigger 是按钮，不传。 */
  htmlFor?: string;
  /** 标签行右侧的动作区。 */
  actions?: ReactNode;
  /** 控件下方的说明。 */
  hint?: ReactNode;
  /** `hint` 的语气；`error` 走危险色。 */
  tone?: "muted" | "error";
  children: ReactNode;
}

/** 标签 + 控件 + 说明。 */
export function FormField({
  label,
  htmlFor,
  actions,
  hint,
  tone = "muted",
  children,
}: FormFieldProps) {
  const labelClass = "text-xs text-muted-foreground";

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        {htmlFor ? (
          <label htmlFor={htmlFor} className={labelClass}>
            {label}
          </label>
        ) : (
          <span className={labelClass}>{label}</span>
        )}
        {actions}
      </div>

      {children}

      {hint ? (
        <div
          className={cn(
            "flex flex-col gap-1.5 text-xs",
            tone === "error" ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {hint}
        </div>
      ) : null}
    </div>
  );
}
