/**
 * 设置弹窗 — map 驱动分区渲染。
 *
 * @author coisini
 * @created 2026-07-21
 */

import { useEffect, useState, type ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  IconButton,
  cn,
} from "@desk/ui";
import { X } from "@desk/ui/icons";
import {
  resolveSettingsSection,
  SETTINGS_SECTIONS,
  type SettingsSectionId,
} from "./settings-sections";

/**
 * `SettingsDialog` 属性。
 *
 * @author coisini
 * @created 2026-07-21
 */
export interface SettingsDialogProps {
  /** 是否打开。 */
  open: boolean;
  /** 打开状态变更。 */
  onOpenChange: (open: boolean) => void;
  /** 打开时默认聚焦的分区。 */
  initialSection?: SettingsSectionId;
}

/**
 * 应用设置弹窗。
 *
 * @author coisini
 * @created 2026-07-21
 *
 * @param props - 见 {@link SettingsDialogProps}
 * @returns 设置 Dialog 节点
 */
export function SettingsDialog({ open, onOpenChange, initialSection }: SettingsDialogProps) {
  const [section, setSection] = useState<SettingsSectionId>(
    initialSection ?? SETTINGS_SECTIONS[0].id,
  );

  useEffect(() => {
    if (open && initialSection) {
      setSection(initialSection);
    }
  }, [open, initialSection]);

  const activeSection = resolveSettingsSection(section);
  const ActivePanel = activeSection.Panel;
  const SectionIcon = activeSection.icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="h-[min(780px,92vh)] w-[min(1100px,96vw)] max-w-none gap-0 p-0"
        closeLabel="关闭"
        dismissOnOutsidePress={false}
        showClose={false}
      >
        <DialogTitle className="sr-only">设置</DialogTitle>
        <DialogDescription className="sr-only">应用设置</DialogDescription>

        <IconButton
          label="关闭"
          className="absolute right-3 top-3 z-20"
          onClick={() => onOpenChange(false)}
        >
          <X className="size-3.5" aria-hidden />
        </IconButton>

        <div className="relative flex h-full min-h-0">
          <nav
            className="flex w-48 shrink-0 flex-col gap-1 border-r border-border/70 px-3 py-5"
            aria-label="设置分类"
          >
            <p className="mb-2 px-2 text-[length:var(--text-xs)] font-medium uppercase tracking-wide text-muted-foreground">
              设置
            </p>
            {SETTINGS_SECTIONS.map((item) => {
              const Icon = item.icon;
              return (
                <SettingsNavButton
                  key={item.id}
                  active={section === item.id}
                  icon={<Icon className="size-4" aria-hidden />}
                  label={item.label}
                  onClick={() => setSection(item.id)}
                />
              );
            })}
          </nav>

          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex shrink-0 items-center gap-2 border-b border-border/70 px-8 py-5 pr-14">
              <SectionIcon className="size-5 text-muted-foreground" aria-hidden />
              <h2 className="font-display text-[length:var(--text-xl)] font-semibold tracking-tight text-foreground">
                {activeSection.label}
              </h2>
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto px-8 py-7">
              <ActivePanel />
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * 设置侧栏导航按钮。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */
function SettingsNavButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-9 items-center gap-2 rounded-[var(--radius-md)] px-2 text-left text-[length:var(--text-sm)] transition-[color,background-color,transform] duration-150 ease-[cubic-bezier(0.23,1,0.32,1)] active:scale-[0.97]",
        active
          ? "bg-muted font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      {icon}
      {label}
    </button>
  );
}
