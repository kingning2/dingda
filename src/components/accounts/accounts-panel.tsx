import { useEffect, useMemo, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { Check, Loader2, QrCode, Trash2 } from "lucide-react";
import type { AccountListItem, AccountPanelConfig } from "./types";
import {
  accountFromQrLogin,
  filterAccountsByPlatform,
  mockAccountAfterConnect,
  mockAccountAfterDisconnect,
  mockAccountWhileConnecting,
} from "./mock-data";
import type { AccountQrCheckResponse } from "@/contracts/account";
import {
  connectStoredAccount,
  deleteStoredAccount,
  disconnectStoredAccount,
  listStoredAccounts,
  patchStoredAccount,
} from "@/lib/account-store";
import { useBackend } from "@/providers/backend-provider";
import { AccountQrDialog } from "./account-qr-dialog";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  const backend = useBackend();
  const useLiveApi = isTauri() && backend.ready && Boolean(backend.apiBaseUrl);
  const isLoginSession = !config.supportsConnection;
  const defaultQrHint = `请用 ${config.appName} App 扫码`;
  const sessionLabel = isLoginSession ? "登录状态" : "连接状态";

  const [accounts, setAccounts] = useState<AccountListItem[]>(() =>
    isTauri() ? [] : filterAccountsByPlatform(config.platform),
  );
  const [keyword, setKeyword] = useState("");
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [autoConnectOnStart, setAutoConnectOnStart] = useState(false);
  const [autoConnectIds, setAutoConnectIds] = useState<string[]>([]);

  const [qrOpen, setQrOpen] = useState(false);
  const [qrTitle, setQrTitle] = useState("扫码登录");
  const [qrHint, setQrHint] = useState(defaultQrHint);

  const [deleteTarget, setDeleteTarget] = useState<AccountListItem | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<AccountListItem | null>(null);
  const [editorDisplayName, setEditorDisplayName] = useState("");
  const [editorCookie, setEditorCookie] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!useLiveApi) {
      return;
    }

    let cancelled = false;
    void listStoredAccounts(backend.apiBaseUrl!, config.platform)
      .then(({ accounts: loaded, autoConnectIds: loadedAutoConnect }) => {
        if (cancelled) {
          return;
        }
        setAccounts(loaded);
        setAutoConnectIds(loadedAutoConnect);
        setLoadError(null);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setLoadError(error instanceof Error ? error.message : "加载账号失败");
      });

    const timer = window.setInterval(() => {
      void listStoredAccounts(backend.apiBaseUrl!, config.platform)
        .then(({ accounts: loaded, autoConnectIds: loadedAutoConnect }) => {
          if (cancelled) {
            return;
          }
          setAccounts(loaded);
          setAutoConnectIds(loadedAutoConnect);
        })
        .catch(() => {
          /* 轮询失败不打断当前列表 */
        });
    }, 30_000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [useLiveApi, backend.apiBaseUrl, config.platform]);

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
    setAccounts((current) => {
      const exists = current.some((item) => item.account_id === next.account_id);
      if (exists) {
        return current.map((item) => (item.account_id === next.account_id ? next : item));
      }
      return [next, ...current];
    });
  }

  function updateAccount(next: AccountListItem) {
    setAccounts((current) =>
      current.map((item) => (item.account_id === next.account_id ? next : item)),
    );
  }

  async function reloadAccounts() {
    if (!useLiveApi) {
      return;
    }
    const { accounts: loaded, autoConnectIds: loadedAutoConnect } =
      await listStoredAccounts(backend.apiBaseUrl!, config.platform);
    setAccounts(loaded);
    setAutoConnectIds(loadedAutoConnect);
    setLoadError(null);
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

  function openAccountEditor(account: AccountListItem) {
    setEditingAccount(account);
    setEditorDisplayName(account.display_name);
    setEditorCookie(account.cookie ?? "");
    setEditorOpen(true);
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
        const connected = await connectStoredAccount(
          backend.apiBaseUrl!,
          account.account_id,
        );
        updateAccount(connected);
      } catch (error) {
        updateAccount(account);
        if (error instanceof Error) {
          window.alert(error.message);
        }
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
        const disconnected = await disconnectStoredAccount(
          backend.apiBaseUrl!,
          account.account_id,
        );
        updateAccount(disconnected);
      } catch (error) {
        if (error instanceof Error) {
          window.alert(error.message);
        }
      }
    })();
  }

  function handleDelete() {
    if (!deleteTarget) {
      return;
    }
    const target = deleteTarget;
    setAccounts((current) => current.filter((item) => item.account_id !== target.account_id));
    setAutoConnectIds((current) => current.filter((id) => id !== target.account_id));
    setDeleteTarget(null);

    if (useLiveApi) {
      void deleteStoredAccount(backend.apiBaseUrl!, target.account_id);
    }
  }

  function handleSaveEditor() {
    if (!editingAccount) {
      return;
    }
    const previousDisplayName = editingAccount.display_name;
    const next = {
      ...editingAccount,
      display_name: editorDisplayName.trim() || editingAccount.display_name,
      cookie: editorCookie.trim() || editingAccount.cookie,
      has_cookie: Boolean((editorCookie.trim() || editingAccount.cookie)?.trim()),
    };
    setEditorOpen(false);
    setEditingAccount(null);

    if (!useLiveApi) {
      mergeAccount(next);
      return;
    }

    void (async () => {
      try {
        let account = next;
        if (account.display_name !== previousDisplayName) {
          account = await patchStoredAccount(backend.apiBaseUrl!, account.account_id, {
            display_name: account.display_name,
          });
        }
        mergeAccount(account);
      } catch (error) {
        if (error instanceof Error) {
          window.alert(error.message);
        }
        mergeAccount(next);
      }
    })();
  }

  function toggleAutoConnectAccount(accountId: string) {
    const enabling = !autoConnectIds.includes(accountId);
    setAutoConnectIds((current) =>
      enabling ? [...current, accountId] : current.filter((id) => id !== accountId),
    );

    if (!useLiveApi) {
      return;
    }

    void patchStoredAccount(backend.apiBaseUrl!, accountId, {
      auto_connect: enabling,
    });
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
                onClick={() => openAccountEditor(account)}
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

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingAccount ? `编辑账号 · ${editingAccount.account_id}` : "编辑账号"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block space-y-1">
              <span className="text-sm text-muted-foreground">显示名称</span>
              <Input
                value={editorDisplayName}
                onChange={(event) => setEditorDisplayName(event.target.value)}
                placeholder="账号展示名"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-sm text-muted-foreground">
                登录信息（风控验证或重新登录后更新）
              </span>
              <Textarea
                value={editorCookie}
                onChange={(event) => setEditorCookie(event.target.value)}
                placeholder={`在浏览器登录 ${config.platformName} 后，将登录信息粘贴到这里`}
                rows={5}
                className="font-mono text-xs"
              />
              <span className="block text-xs text-muted-foreground/80">
                一般通过扫码登录自动获取；仅在平台要求重新验证时手动更新。
              </span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditorOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSaveEditor}>保存</Button>
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
