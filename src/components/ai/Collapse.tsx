/**
 * 折叠块（对齐 OpenDesign Foldable）：
 * - lifecycleOpen：跑着摊开、跑完收起
 * - 用户手点过的不再被重渲染拨回去
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type SyntheticEvent,
} from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CollapseProps {
  title: ReactNode;
  trailing?: ReactNode;
  /** 仅初次挂载。 */
  defaultOpen?: boolean;
  /**
   * 生命周期驱动的开合（流式中 true、结束后 false）。
   * 用户手动切换过后不再跟随。
   */
  lifecycleOpen?: boolean;
  /** @deprecated 使用 lifecycleOpen */
  forceOpen?: boolean;
  className?: string;
  children?: ReactNode;
  /** 正文区额外 class（可贴底滚动）。 */
  bodyClassName?: string;
  bodyRef?: React.Ref<HTMLDivElement>;
}

export function Collapse({
  title,
  trailing,
  defaultOpen = false,
  lifecycleOpen,
  forceOpen,
  className,
  children,
  bodyClassName,
  bodyRef,
}: CollapseProps) {
  const life = lifecycleOpen ?? (forceOpen ? true : undefined);
  const seed = life ?? defaultOpen;
  const [open, setOpen] = useState(Boolean(seed));
  const [userToggled, setUserToggled] = useState(false);
  const openRef = useRef(open);
  openRef.current = open;

  useEffect(() => {
    if (life == null || userToggled) return;
    setOpen(Boolean(life));
  }, [life, userToggled]);

  const hasBody = children != null && children !== false;

  const handleToggle = useCallback(
    (event: SyntheticEvent<HTMLDetailsElement>) => {
      const next = event.currentTarget.open;
      if (!hasBody) {
        if (next) event.currentTarget.open = false;
        return;
      }
      // 自动写回 open 也会派发 toggle；只有值翻转才算用户手点
      if (next !== openRef.current) setUserToggled(true);
      setOpen(next);
    },
    [hasBody],
  );

  return (
    <details
      className={cn("min-w-0", className)}
      open={hasBody ? open : false}
      onToggle={handleToggle}
    >
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-1.5 text-left text-[13px] text-muted-foreground",
          "transition-colors hover:text-foreground",
          "[&::-webkit-details-marker]:hidden",
        )}
      >
        <span className="min-w-0 flex-1 truncate">{title}</span>
        {trailing}
        {hasBody ? (
          <ChevronDown
            className={cn("size-3.5 shrink-0 transition-transform", open && "rotate-180")}
          />
        ) : null}
      </summary>
      {hasBody && open ? (
        <div ref={bodyRef} className={cn("mt-1.5 min-w-0", bodyClassName)}>
          {children}
        </div>
      ) : null}
    </details>
  );
}
