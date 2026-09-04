import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, QrCode, Trash2 } from "lucide-react";
import type { AccountListItem, AccountPanelConfig } from "./types";
import {
  accountFromQrLogin,
  filterAccountsByPlatform,
  mockAccountAfterConnect,
  mockAccountAfterDisconnect,
  mockAccountWhileConnecting,
} from "./mock-data";
import type { AccountProfileView, AccountQrCheckResponse } from "@/contracts/account";
import {
  connectStoredAccount,
  deleteStoredAccount,
  disconnectStoredAccount,
  fetchAccountProfile,
  patchStoredAccount,
} from "@/lib/account-store";
import { refreshAccountsForPlatform } from "@/lib/discovery-scan";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { useServer } from "@/providers/server-provider";
import { AccountQrDialog } from "./account-qr-dialog";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface AccountsPanelProps {
  config: AccountPanelConfig;
}

export function AccountsPanel({ config }: AccountsPanelProps) {
  const server = useServer();
  const useLiveApi = server.ready && Boolean(server.apiBaseUrl);
  const isLoginSession = !config.supportsConnection;
  const defaultQrHint = `请用 ${config.appName} App 扫码`;
  const sessionLabel = isLoginSession ? "登录状态" : "连接状态";

  const storeAccounts = useDiscoveryStore((state) => state.accounts);
  const storeAutoConnectIds = useDiscoveryStore((state) => state.autoConnectIds);
  const accountsError = useDiscoveryStore((state) => state.accountsError);
  const upsertAccount = useDiscoveryStore((state) => state.upsertAccount);
  const removeAccount = useDiscoveryStore((state) => state.removeAccount);
  const setAutoConnectIds = useDiscoveryStore((state) => state.setAutoConnectIds);

  const [mockAccounts, setMockAccounts] = useState(() =>
    filterAccountsByPlatform(config.platform),
  );
  const [mockAutoConnectIds, setMockAutoConnectIds] = useState<string[]>([]);
  const [keyword, setKeyword] = useState("");
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [autoConnectOnStart, setAutoConnectOnStart] = useState(false);

  const [qrOpen, setQrOpen] = useState(false);
  const [qrTitle, setQrTitle] = useState("扫码登录");
  const [qrHint, setQrHint] = useState(defaultQrHint);

  const [deleteTarget, setDeleteTarget] = useState<AccountListItem | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profile, setProfile] = useState<AccountProfileView | null>(null);

  const accounts = useMemo(() => {
    if (!useLiveApi) return mockAccounts;
    return storeAccounts.filter((item) => item.platform === config.platform);
  }, [useLiveApi, mockAccounts, storeAccounts, config.platform]);

  const autoConnectIds = useLiveApi ? storeAutoConnectIds : mockAutoConnectIds;
  const loadError = useLiveApi ? accountsError : null;

  useEffect(() => {
    if (!useLiveApi) return;

    const timer = window.setInterval(() => {
      void refreshAccountsForPlatform(config.platform).catch(() => {
        /* 轮询失败不打断当前列表 */
      });
    }, 30_000);

    return () => window.clearInterval(timer);
  }, [useLiveApi, config.platform]);

  const filtered = useMemo(() => {
    return accounts.filter((account) => {
      const matchKeyword =
        !keyword.trim() ||
        account.account_id.includes(keyword.trim()) ||
        account.display_name.includes(keyword.trim());
      return matchKeyword;
    });
  }, [accounts, keyword]);

  function mergeAccount(next: AccountListItem) {
    if (useLiveApi) {
      upsertAccount(next);
      return;
    }
    setMockAccounts((current) => {
      const exists = current.some((item) => item.account_id === next.account_id);
      if (exists) {
        return current.map((item) => (item.account_id === next.account_id ? next : item));
      }
      return [next, ...current];
    });
  }

  function updateAccount(next: AccountListItem) {
    mergeAccount(next);
  }

  async function reloadAccounts() {
    if (!useLiveApi) return;
    await refreshAccountsForPlatform(config.platform);
  }

  function openQrLogin() {
    setQrTitle("扫码登录");
    setQrHint(defaultQrHint);
    setQrOpen(true);
  }

  function openRescanQr(account: AccountListItem) {
    const name = account.display_name || account.account_id;
    setQrTitle("重新扫码登录");
    setQrHint(`请用 ${config.appName} App 扫码，刷新「${name}」的登录态`);
    setQrOpen(true);
  }

  function openAccountProfile(account: AccountListItem) {
    const stub: AccountProfileView = {
      account_id: account.account_id,
      platform: account.platform as AccountProfileView["platform"],
      display_name: account.display_name,
      avatar_url: account.avatar_url,
    };
    setProfile(stub);
    setProfileOpen(true);
    if (!useLiveApi) {
      setProfileLoading(false);
      return;
    }
    setProfileLoading(true);
    void (async () => {
      try {
        const next = await fetchAccountProfile(account.account_id);
        setProfile(next);
        updateAccount({
          ...account,
          display_name: next.display_name || account.display_name,
          avatar_url: next.avatar_url || account.avatar_url,
        });
      } catch {
        // http-client 已提示
      } finally {
        setProfileLoading(false);
      }
    })();
  }

  function handleQrSuccess(result: AccountQrCheckResponse) {
    if (!useLiveApi || !result.cookie?.trim()) {
      const created = accountFromQrLogin(config.platform, config.platformName, result);
      mergeAccount(created);
      return;
    }
    void (async () => {
      await reloadAccounts();
      window.setTimeout(() => void reloadAccounts(), 2_000);
      window.setTimeout(() => void reloadAccounts(), 5_000);
    })();
  }

  function handleConnect(account: AccountListItem) {
    if (!account.cookie?.trim()) {
      return;
    }
    if (!useLiveApi) {
      setConnectingId(account.account_id);
      updateAccount(mockAccountWhileConnecting(account));
      window.setTimeout(() => {
        updateAccount(mockAccountAfterConnect(account));
        setConnectingId(null);
      }, 800);
      return;
    }

    setConnectingId(account.account_id);
    updateAccount(mockAccountWhileConnecting(account));
    void (async () => {
      try {
        const connected = await connectStoredAccount(account.account_id);
        updateAccount(connected);
      } catch {
        updateAccount(account);
      } finally {
        setConnectingId(null);
      }
    })();
  }

  function handleDisconnect(account: AccountListItem) {
    if (!useLiveApi) {
      updateAccount(mockAccountAfterDisconnect(account));
      return;
    }

    void (async () => {
      try {
        const disconnected = await disconnectStoredAccount(account.account_id);
        updateAccount(disconnected);
      } catch {
        // http-client 已弹错
      }
    })();
  }

  function handleDelete() {
    if (!deleteTarget) {
      return;
    }
    const target = deleteTarget;
    setDeleteTarget(null);

    if (useLiveApi) {
      removeAccount(target.account_id);
      void deleteStoredAccount(target.account_id);
      return;
    }

    setMockAccounts((current) =>
      current.filter((item) => item.account_id !== target.account_id),
    );
    setMockAutoConnectIds((current) =>
      current.filter((id) => id !== target.account_id),
    );
  }

  function toggleAutoConnectAccount(accountId: string) {
    const enabling = !autoConnectIds.includes(accountId);
    const nextIds = enabling
      ? [...autoConnectIds, accountId]
      : autoConnectIds.filter((id) => id !== accountId);

    if (useLiveApi) {
      setAutoConnectIds(nextIds);
      void patchStoredAccount(accountId, { auto_connect: enabling });
      return;
    }

    setMockAutoConnectIds(nextIds);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="搜索账号 ID / 名称"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            className="w-56"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {config.supportsAutoConnect ? (
            <Button
              variant={autoConnectOnStart ? "default" : "outline"}
              onClick={() => setAutoConnectOnStart((value) => !value)}
            >
              {autoConnectOnStart
                ? `启动自动连接：开启（${autoConnectIds.length}）`
                : "启动自动连接：关"}
            </Button>
          ) : null}
          <Button variant="outline" onClick={openQrLogin}>
            <QrCode className="size-4" />
            扫码登录
          </Button>
        </div>
      </div>

      {loadError ? (
        <p className="text-sm text-destructive">账号加载失败：{loadError}</p>
      ) : null}

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-muted-foreground">暂无 {config.platformName} 账号，请先扫码登录添加</p>
          <Button variant="outline" onClick={openQrLogin}>
            <QrCode className="size-4" />
            扫码登录
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((account) => {
            const { session, actions } = account;
            const isConnecting = connectingId === account.account_id;

            return (
              <Card
                key={account.account_id}
                className="cursor-pointer transition hover:border-primary/40 hover:shadow-sm"
                onClick={() => openAccountProfile(account)}
              >
                <CardContent className="flex h-full flex-col p-4">
                  <div className="flex items-start gap-3">
                    <Avatar className="size-10 shrink-0">
                      {account.avatar_url ? (
                        <AvatarImage
                          src={account.avatar_url}
                          alt={account.display_name || account.account_id}
                        />
                      ) : null}
                      <AvatarFallback className="text-sm font-medium">
                        {(account.display_name || account.account_id).slice(0, 1)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 space-y-1">
                      <div className="truncate font-medium">
                        {account.display_name || account.account_id}
                      </div>
                      <div className="truncate font-mono text-xs text-muted-foreground">
                        {account.account_id}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 space-y-2 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">{sessionLabel}</span>
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-xs",
                          session.badge_class,
                        )}
                      >
                        {session.label}
                      </span>
                    </div>
                    <p
                      className={cn(
                        "min-h-5 text-xs text-muted-foreground",
                        session.hint ? "text-orange-700" : "invisible",
                      )}
                      aria-hidden={!session.hint}
                    >
                      {session.hint ?? "占位"}
                    </p>
                  </div>

                  <div
                    className="mt-4 flex flex-wrap items-center gap-2"
                    onClick={(event) => event.stopPropagation()}
                  >
                    {config.supportsAutoConnect ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="mr-auto h-8 gap-1.5 px-2 text-muted-foreground"
                        onClick={() => toggleAutoConnectAccount(account.account_id)}
                      >
                        <span
                          className={cn(
                            "flex size-4 items-center justify-center rounded border",
                            autoConnectIds.includes(account.account_id)
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border",
                          )}
                        >
                          {autoConnectIds.includes(account.account_id) ? (
                            <Check className="size-3" />
                          ) : null}
                        </span>
                        自动连接
                      </Button>
                    ) : null}

                    {actions.can_rescan ? (
                      <Button size="sm" variant="outline" onClick={() => openRescanQr(account)}>
                        <QrCode className="size-3.5" />
                        重新扫码
                      </Button>
                    ) : null}

                    {config.supportsConnection && actions.can_disconnect ? (
                      <Button size="sm" variant="outline" onClick={() => handleDisconnect(account)}>
                        断开
                      </Button>
                    ) : null}

                    {config.supportsConnection && actions.can_connect ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isConnecting}
                        onClick={() => handleConnect(account)}
                      >
                        {isConnecting ? (
                          <>
                            <Loader2 className="size-3.5 animate-spin" />
                            连接中…
                          </>
                        ) : (
                          "连接"
                        )}
                      </Button>
                    ) : null}

                    <Button
                      size="sm"
                      variant="outline"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(account)}
                    >
                      <Trash2 className="size-3.5" />
                      删除
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <AccountQrDialog
        open={qrOpen}
        config={config}
        title={qrTitle}
        hint={qrHint}
        onClose={() => setQrOpen(false)}
        onSuccess={handleQrSuccess}
      />

      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>个人主页</DialogTitle>
          </DialogHeader>
          {profile ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Avatar className="size-14 shrink-0">
                  {profile.avatar_url ? (
                    <AvatarImage src={profile.avatar_url} alt={profile.display_name} />
                  ) : null}
                  <AvatarFallback className="text-lg font-medium">
                    {(profile.display_name || profile.account_id).slice(0, 1)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <div className="truncate text-lg font-medium">
                    {profile.display_name || profile.account_id}
                  </div>
                  <div className="truncate font-mono text-xs text-muted-foreground">
                    {profile.account_id}
                  </div>
                  {profileLoading ? (
                    <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                      <Loader2 className="size-3 animate-spin" />
                      正在同步平台资料…
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {profile.followers != null ? (
                  <div className="rounded-md border px-3 py-2">
                    <div className="text-xs text-muted-foreground">粉丝</div>
                    <div className="font-medium">{profile.followers}</div>
                  </div>
                ) : null}
                {profile.following != null ? (
                  <div className="rounded-md border px-3 py-2">
                    <div className="text-xs text-muted-foreground">关注</div>
                    <div className="font-medium">{profile.following}</div>
                  </div>
                ) : null}
                {profile.sold_count != null ? (
                  <div className="rounded-md border px-3 py-2">
                    <div className="text-xs text-muted-foreground">卖出</div>
                    <div className="font-medium">{profile.sold_count}</div>
                  </div>
                ) : null}
                {profile.purchase_count != null ? (
                  <div className="rounded-md border px-3 py-2">
                    <div className="text-xs text-muted-foreground">买过</div>
                    <div className="font-medium">{profile.purchase_count}</div>
                  </div>
                ) : null}
                {profile.collection_count != null ? (
                  <div className="rounded-md border px-3 py-2">
                    <div className="text-xs text-muted-foreground">收藏</div>
                    <div className="font-medium">{profile.collection_count}</div>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setProfileOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>删除账号</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            确认删除账号「{deleteTarget?.account_id ?? ""}」？该操作不可撤销。
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
