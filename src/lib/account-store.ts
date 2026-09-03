import type {
  AccountActionsView,
  AccountListItem,
  AccountPlatform,
  AccountSessionView,
} from "@/contracts/account";
import { accountFromStorage } from "@/components/accounts/mock-data";
import { handleApiResponseError } from "@/lib/api-error";

export interface StoredAccountRecord {
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
  apiBaseUrl: string,
  platform: AccountPlatform,
): Promise<{ accounts: AccountListItem[]; autoConnectIds: string[] }> {
  const url = new URL(`${apiBaseUrl}/v1/accounts`);
  url.searchParams.set("platform", platform);

  const response = await fetch(url.toString());
  if (!response.ok) {
    await handleApiResponseError(response, "加载账号失败");
  }

  const payload = (await response.json()) as AccountListResponse;
  const autoConnectIds = payload.items
    .filter((item) => item.auto_connect)
    .map((item) => item.account_id);
  return {
    accounts: payload.items.map((item) => accountFromStorage(item.platform, item)),
    autoConnectIds,
  };
}

export async function patchStoredAccount(
  apiBaseUrl: string,
  accountId: string,
  patch: { display_name?: string; auto_connect?: boolean },
): Promise<AccountListItem> {
  const response = await fetch(
    `${apiBaseUrl}/v1/accounts/${encodeURIComponent(accountId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    },
  );

  if (!response.ok) {
    await handleApiResponseError(response, "更新账号失败");
  }
  const payload = (await response.json()) as AccountPatchResponse;
  return accountFromStorage(payload.item.platform, payload.item);
}

export async function connectStoredAccount(
  apiBaseUrl: string,
  accountId: string,
): Promise<AccountListItem> {
  const response = await fetch(
    `${apiBaseUrl}/v1/accounts/${encodeURIComponent(accountId)}/connect`,
    { method: "POST" },
  );

  if (!response.ok) {
    await handleApiResponseError(response, "连接账号失败");
  }
  const payload = (await response.json()) as AccountPatchResponse;
  return accountFromStorage(payload.item.platform, payload.item);
}

export async function disconnectStoredAccount(
  apiBaseUrl: string,
  accountId: string,
): Promise<AccountListItem> {
  const response = await fetch(
    `${apiBaseUrl}/v1/accounts/${encodeURIComponent(accountId)}/disconnect`,
    { method: "POST" },
  );

  if (!response.ok) {
    await handleApiResponseError(response, "断开账号失败");
  }
  const payload = (await response.json()) as AccountPatchResponse;
  return accountFromStorage(payload.item.platform, payload.item);
}

export async function deleteStoredAccount(
  apiBaseUrl: string,
  accountId: string,
): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/v1/accounts/${encodeURIComponent(accountId)}`,
    { method: "DELETE" },
  );

  if (!response.ok) {
    await handleApiResponseError(response, "删除账号失败");
  }
}
