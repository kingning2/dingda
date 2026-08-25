/**
 * 账号管理页（共享 Hub）— 泛型渲染注入的 Tab 列表，不含任何平台分支。
 *
 * - `tabs.length > 1`：渲染页内 Tab 条
 * - `tabs.length === 1`：直接渲染单平台面板（不显示 Tab 条）
 *
 * @author Xiaoman
 * @created 2026-08-13
 */

import { useEffect, useState } from "react";
import { PageScaffold } from "@desk/ui";
import type { AccountPlatform } from "@desk/platform/ipc/account";
import type { AccountsTab } from "./types";
import { AccountsPanel } from "./accounts-panel";

/**
 * 账号管理页（页内 Tab 由调用方注入）。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @param tabs - 启用的平台 Tab（每个含注入的 deps）
 * @param initialTab - 初始 Tab（深链 `accounts-1688` 时用）
 */
export function AccountsHubPage({
  tabs,
  initialTab,
}: {
  tabs: AccountsTab[];
  initialTab?: AccountPlatform;
}) {
  const [tab, setTab] = useState<AccountPlatform | undefined>(initialTab ?? tabs[0]?.id);

  useEffect(() => {
    setTab(initialTab ?? tabs[0]?.id);
  }, [initialTab, tabs]);

  const active = tabs.find((item) => item.id === tab) ?? tabs[0];
  const subtitle =
    tabs.length > 1
      ? `${tabs.map((item) => item.deps.platformName).join(" 与 ")} 分站扫码登录，互不串绑`
      : `${tabs[0]?.deps.platformName ?? ""}账号扫码登录与管理`;

  return (
    <PageScaffold title="账号管理" subtitle={subtitle}>
      {tabs.length > 1 ? (
        <div className="mb-4 flex border-b border-border" role="tablist" aria-label="账号平台">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
              className={`border-b-2 px-4 py-2 text-[length:var(--text-sm)] font-medium transition-colors duration-150 ease-out ${
                tab === item.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
      {active ? <AccountsPanel key={active.id} deps={active.deps} /> : null}
    </PageScaffold>
  );
}
