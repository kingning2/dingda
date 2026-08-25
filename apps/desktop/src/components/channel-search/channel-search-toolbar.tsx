/**
 * 渠道商品搜索工具栏 — 1688 / 闲鱼（后续）共用，无 Aceternity 光晕。
 *
 * 筛选区走 {@link PageScaffold} 的 `toolbar`，不用 {@link PageGlowCard}，
 * 避免窄条表单出现错位紫色描边。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */

import { AsyncButton, Input, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@desk/ui";
import { Search } from "@desk/ui/icons";

export interface ChannelSearchAccountOption {
  id: string;
  label: string;
}

export interface ChannelSearchToolbarProps {
  /** 账号选择器标签，如「1688 账号」「闲鱼账号」。 */
  accountLabel: string;
  accounts: ChannelSearchAccountOption[];
  accountId: string;
  onAccountIdChange: (accountId: string) => void;
  keyword: string;
  onKeywordChange: (keyword: string) => void;
  onSearch: () => void;
  loading?: boolean;
  keywordPlaceholder?: string;
  searchLabel?: string;
  accountPlaceholder?: string;
}

/**
 * 渠道关键词搜索工具栏（账号 + 关键词 + 搜索按钮）。
 */
export function ChannelSearchToolbar({
  accountLabel,
  accounts,
  accountId,
  onAccountIdChange,
  keyword,
  onKeywordChange,
  onSearch,
  loading = false,
  keywordPlaceholder = "输入搜索关键词",
  searchLabel = "搜索",
  accountPlaceholder = "选择已登录账号",
}: ChannelSearchToolbarProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="flex-1 space-y-1.5 sm:max-w-xs">
        <label className="text-xs text-muted-foreground">{accountLabel}</label>
        <Select value={accountId} onValueChange={onAccountIdChange} disabled={loading}>
          <SelectTrigger>
            <SelectValue placeholder={accountPlaceholder} />
          </SelectTrigger>
          <SelectContent>
            {accounts.map((account) => (
              <SelectItem key={account.id} value={account.id}>
                {account.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex-[2] space-y-1.5">
        <label className="text-xs text-muted-foreground">关键词</label>
        <Input
          value={keyword}
          onChange={(event) => onKeywordChange(event.target.value)}
          placeholder={keywordPlaceholder}
          disabled={loading}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onSearch();
            }
          }}
        />
      </div>
      <AsyncButton loading={loading} onClick={onSearch} className="shrink-0">
        <Search className="mr-1.5 size-4" aria-hidden />
        {searchLabel}
      </AsyncButton>
    </div>
  );
}
