import type {
  AccountActionsView,
  AccountListItem,
  AccountPlatform,
  AccountProfileResponse,
  AccountProfileView,
  AccountSessionView,
} from "@/contracts/account";
import { accountFromStorage } from "@/components/accounts/mock-data";
import { api } from "@/lib/http-client";

interface StoredAccountRecord {
  account_id: string;
  platform: AccountPlatform;
  display_name: string;
  avatar_url?: string | null;
  cookie: string;
  status: string;
  status_label: string;
  has_cookie: boolean;
  auto_connect: boolean;
  auth_valid: boolean;
  session: AccountSessionView;
  actions: AccountActionsView;
}

interface AccountListResponse {
  ok: boolean;
  items: StoredAccountRecord[];
}

interface AccountPatchResponse {
  ok: boolean;
  item: StoredAccountRecord;
}

export async function listStoredAccounts(
  platform: AccountPlatform,
): Promise<{ accounts: AccountListItem[]; autoConnectIds: string[] }> {
  const { data } = await api.get<AccountListResponse>("/v1/accounts", {
    query: { platform },
    fallbackError: "加载账号失败",
  });
  const autoConnectIds = data.items
    .filter((item) => item.auto_connect)
    .map((item) => item.account_id);
  return {
    accounts: data.items.map((item) => accountFromStorage(item.platform, item)),
    autoConnectIds,
  };
}

export async function patchStoredAccount(
  accountId: string,
  patch: { display_name?: string; auto_connect?: boolean },
): Promise<AccountListItem> {
  const { data } = await api.patch<AccountPatchResponse>(
    `/v1/accounts/${encodeURIComponent(accountId)}`,
    patch,
    { fallbackError: "更新账号失败" },
  );
  return accountFromStorage(data.item.platform, data.item);
}

export async function connectStoredAccount(accountId: string): Promise<AccountListItem> {
  const { data } = await api.post<AccountPatchResponse>(
    `/v1/accounts/${encodeURIComponent(accountId)}/connect`,
    undefined,
    { fallbackError: "连接账号失败" },
  );
  return accountFromStorage(data.item.platform, data.item);
}

export async function disconnectStoredAccount(accountId: string): Promise<AccountListItem> {
  const { data } = await api.post<AccountPatchResponse>(
    `/v1/accounts/${encodeURIComponent(accountId)}/disconnect`,
    undefined,
    { fallbackError: "断开账号失败" },
  );
  return accountFromStorage(data.item.platform, data.item);
}

export async function fetchAccountProfile(accountId: string): Promise<AccountProfileView> {
  const { data } = await api.get<AccountProfileResponse>(
    `/v1/accounts/${encodeURIComponent(accountId)}/profile`,
    { fallbackError: "加载个人主页失败" },
  );
  return data.profile;
}

export async function deleteStoredAccount(accountId: string): Promise<void> {
  await api.delete(`/v1/accounts/${encodeURIComponent(accountId)}`, {
    fallbackError: "删除账号失败",
  });
}
