/**
 * 平台账号列表面板（共享）— 不含任何平台分支，平台差异全部来自注入的 deps。
 *
 * 能力可见性：
 * - `deps.supportsConnection` — 是否有真实渠道 WS（闲鱼）；无则连接/断开为前端会话态
 * - `deps.autoConnect` — 启动自动连接开关与勾选（闲鱼连渠道，1688 勾选保留配置）
 *
 * @author Xiaoman
 * @created 2026-08-13
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  Checkbox,
  ConfirmModal,
  Input,
  Loading,
  PageCardGrid,
  PageGlowCard,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
  toast,
} from "@desk/ui";
import { QrCode, Trash2 } from "@desk/ui/icons";
import {
  accountDelete,
  accountList,
  accountProbeLogin,
  accountUpdate,
  type XianyuAccount,
} from "@desk/platform/ipc/account";
import { listenChannelStatus } from "@desk/platform/events";
import {
  accountSessionStatusView,
  CHANNEL_CONNECTION_STATUS_MAP,
  connectionStatusHint,
  loginSessionStatusHint,
  mergeChannelConnectionState,
  normalizeChannelConnectionState,
  type ChannelConnectionState,
} from "@desk/platform";
import type { AccountPanelDeps } from "./types";
import { AccountQrDialog } from "./account-qr-dialog";
import {
  invalidateProbeCache,
  loadConnectedAccountIds,
  probeAccountLoginSessions,
  probeConnectedAccounts,
  setAccountConnected,
} from "./use-connected-accounts";


/**
 * IPC / toast 错误是否为登录过期（连接失败时写入 auth_expired）。
 *
 * @author Xiaoman
 * @created 2026-08-21
 */
function isAuthExpiredText(text?: string | null): boolean {
  if (!text) {
    return false;
  }
  return (
    text.includes("FAIL_SYS_SESSION_EXPIRED") ||
    text.includes("Session过期") ||
    text.includes("SESSION_EXPIRED") ||
    text.includes("登录态已过期") ||
    text.includes("请重新扫码登录") ||
    text.includes("Cookie 无效") ||
    text.includes("cookie 缺少")
  );
}

/**
 * 解析账号所属平台（兼容旧数据无 `platform` 字段）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 *
 * @param account - 账号记录
 * @returns `xianyu` 或 `ali1688`
 */
export function resolveAccountPlatform(account: XianyuAccount): "xianyu" | "ali1688" {
  if (account.platform === "ali1688" || account.platform === "xianyu") {
    return account.platform;
  }
  if (account.account_id.startsWith("1688:")) {
    return "ali1688";
  }
  return "xianyu";
}

/**
 * 单平台账号列表面板（嵌入 Tab，不含外层 PageScaffold）。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @param deps - 平台注入的能力（见 [`AccountPanelDeps`]）
 */
export function AccountsPanel({ deps }: { deps: AccountPanelDeps }) {
  const { platform, platformName, appName, supportsConnection, autoConnect } = deps;
  /** 无渠道 WS：展示登录态探针，不提供连接/断开。 */
  const isLoginSession = !supportsConnection;
  const defaultQrHint = `请用 ${appName} App 扫码`;

  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [deleteTarget, setDeleteTarget] = useState<XianyuAccount | null>(null);
  const [qrOpen, setQrOpen] = useState(false);
  const [qrSeq, setQrSeq] = useState(0);
  /** 重新扫码时的弹窗文案；普通添加账号时用默认。 */
  const [qrTitle, setQrTitle] = useState("扫码登录");
  const [qrHint, setQrHint] = useState(defaultQrHint);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<XianyuAccount | null>(null);
  const [editorDisplayName, setEditorDisplayName] = useState("");
  const [editorCookie, setEditorCookie] = useState("");
  const [editorSaving, setEditorSaving] = useState(false);
  /** account_id → 渠道连接状态（与 `channel/status.state` / map 对齐）。仅支持连接的平台使用。 */
  const [connectionStates, setConnectionStates] = useState<
    Record<string, ChannelConnectionState>
  >({});
  /** account_id → 后端短文案 hint（禁止原始 JSON）。 */
  const [connectionDetails, setConnectionDetails] = useState<Record<string, string>>({});
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [autoConnectOnStart, setAutoConnectOnStart] = useState(false);
  const [autoConnectIds, setAutoConnectIds] = useState<string[]>([]);
  const [autoConnecting, setAutoConnecting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await accountList(OWNER_ID);
      setAccounts(list.filter((account) => resolveAccountPlatform(account) === platform));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }, [platform]);

  useEffect(() => {
    let cancelled = false;
    void accountList(OWNER_ID)
      .then((list) => {
        if (!cancelled) {
          setAccounts(list.filter((account) => resolveAccountPlatform(account) === platform));
        }
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [platform]);

  useEffect(() => {
    if (!autoConnect) {
      return;
    }
    let cancelled = false;
    void autoConnect
      .load()
      .then((config) => {
        if (!cancelled) {
          setAutoConnectOnStart(config.enabled);
          setAutoConnectIds(config.accountIds);
        }
      })
      .catch(() => {
        // 读取失败时保持默认关闭，不阻断账号列表。
      });
    return () => {
      cancelled = true;
    };
  }, [autoConnect]);

  /** 一次性拉取连接状态快照（进页 / 扫码成功后）；运行中靠事件推送。 */
  const refreshConnectionStates = useCallback(async (accountIds: string[]) => {
    const connectionState = deps.connectionState;
    if (!connectionState || accountIds.length === 0) {
      return;
    }
    const updates: Record<string, ChannelConnectionState> = {};
    await Promise.all(
      accountIds.map(async (accountId) => {
        try {
          updates[accountId] = normalizeChannelConnectionState(
            await connectionState(OWNER_ID, accountId),
          );
        } catch {
          // 单账号状态查询失败不阻断其余。
        }
      }),
    );
    if (Object.keys(updates).length === 0) {
      return;
    }
    // 登录过期 / 过滑块中会伴随 disconnect，快照不得冲掉合成态。
    setConnectionStates((current) => {
      const merged = { ...current };
      for (const [accountId, incoming] of Object.entries(updates)) {
        if (
          (current[accountId] === "auth_expired" ||
            current[accountId] === "renewing" ||
            current[accountId] === "queued") &&
          incoming !== "connected"
        ) {
          continue;
        }
        merged[accountId] = incoming;
      }
      return merged;
    });
  }, [deps.connectionState]);

  // 订阅 Rust 侧 channel/status：只信 canonical `state`，用 map 渲染。
  useEffect(() => {
    if (!supportsConnection) {
      return;
    }
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    void listenChannelStatus((payload) => {
      if (cancelled || !payload.account_id) {
        return;
      }
      if (payload.state !== "connected") {
        invalidateProbeCache(payload.account_id);
      }
      setConnectionStates((current) => ({
        ...current,
        [payload.account_id]: mergeChannelConnectionState(
          current[payload.account_id],
          payload.state,
        ),
      }));
      setConnectionDetails((current) => {
        if (payload.state === "connected") {
          const next = { ...current };
          delete next[payload.account_id];
          return next;
        }
        const hint = connectionStatusHint(
          normalizeChannelConnectionState(payload.state),
          payload.detail,
        );
        if (hint) {
          return { ...current, [payload.account_id]: hint };
        }
        return current;
      });
      if (payload.state === "connected") {
        void load();
      }
    })
      .then((fn) => {
        if (cancelled) {
          fn();
          return;
        }
        unlisten = fn;
      })
      .catch(() => {
        // 事件订阅失败时仍依赖进页 IPC 快照。
      });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [supportsConnection, load]);

  // 进页 / 账号列表变化时拉一次快照；运行中只信 channel/status 推送，不再定时轮询。
  useEffect(() => {
    if (!supportsConnection || accounts.length === 0) {
      return;
    }
    void refreshConnectionStates(accounts.map((account) => account.account_id));
  }, [accounts, supportsConnection, refreshConnectionStates]);

  /** 恢复「已连接」标记并探针校验登录是否过期（闲鱼等已连渠道账号）。 */
  const refreshConnectedSessionProbe = useCallback(async (list: XianyuAccount[]) => {
    const connectedIds = await loadConnectedAccountIds();
    const platformConnected = connectedIds.filter((accountId) =>
      list.some((account) => account.account_id === accountId),
    );
    if (platformConnected.length === 0) {
      return;
    }

    setConnectionStates((current) => {
      const next = { ...current };
      for (const accountId of platformConnected) {
        if (next[accountId] !== "auth_expired") {
          next[accountId] = "connecting";
        }
      }
      return next;
    });

    // 已有渠道 WS 快照为 connected 的账号直接视为在线，不发 Playwright 探针。
    const results: Record<string, boolean> = {};
    const needProbe: XianyuAccount[] = [];
    await Promise.all(
      list
        .filter((account) => platformConnected.includes(account.account_id))
        .map(async (account) => {
          if (deps.connectionState && Boolean(account.cookie?.trim())) {
            try {
              const state = normalizeChannelConnectionState(
                await deps.connectionState(OWNER_ID, account.account_id),
              );
              if (state === "connected") {
                results[account.account_id] = true;
                return;
              }
            } catch {
              // 状态查询失败则退回探针。
            }
          }
          needProbe.push(account);
        }),
    );

    Object.assign(results, await probeConnectedAccounts(needProbe));
    setConnectionStates((current) => {
      const next = { ...current };
      for (const [accountId, ok] of Object.entries(results)) {
        next[accountId] = ok ? "connected" : "auth_expired";
      }
      return next;
    });
    const expiredIds = Object.entries(results)
      .filter(([, ok]) => !ok)
      .map(([accountId]) => accountId);
    if (expiredIds.length === 0) {
      setConnectionDetails((current) => {
        const next = { ...current };
        for (const accountId of Object.keys(results)) {
          delete next[accountId];
        }
        return next;
      });
      return;
    }

    setConnectionDetails((current) => {
      const next = { ...current };
      for (const accountId of expiredIds) {
        next[accountId] = "登录态已过期，请重新扫码";
      }
      return next;
    });
  }, []);

  /** 1688 等：对有 Cookie 的账号批量探针，先展示「检测中」。 */
  const refreshLoginSessionProbe = useCallback(async (list: XianyuAccount[]) => {
    const targets = list.filter((account) => Boolean(account.cookie?.trim()));
    if (targets.length === 0) {
      return;
    }

    setConnectionStates((current) => {
      const next = { ...current };
      for (const account of targets) {
        if (next[account.account_id] !== "auth_expired") {
          next[account.account_id] = "connecting";
        }
      }
      return next;
    });

    const results = await probeAccountLoginSessions(targets);
    setConnectionStates((current) => {
      const next = { ...current };
      for (const account of targets) {
        const online = results[account.account_id];
        if (online === undefined) {
          continue;
        }
        next[account.account_id] = online ? "connected" : "auth_expired";
      }
      return next;
    });
    setConnectionDetails((current) => {
      const next = { ...current };
      for (const account of targets) {
        if (results[account.account_id] === false) {
          next[account.account_id] = "登录态已过期，请重新扫码";
        } else if (results[account.account_id] === true) {
          delete next[account.account_id];
        }
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (accounts.length === 0) {
      return;
    }
    if (isLoginSession) {
      void refreshLoginSessionProbe(accounts);
      return;
    }
    void refreshConnectedSessionProbe(accounts);
  }, [accounts, isLoginSession, refreshConnectedSessionProbe, refreshLoginSessionProbe]);

  const filtered = useMemo(() => {
    return accounts.filter((account) => {
      const matchKeyword =
        !keyword.trim() ||
        account.account_id.includes(keyword.trim()) ||
        account.display_name.includes(keyword.trim());
      const matchStatus =
        statusFilter === "all" || (statusFilter === "active" ? account.status === "active" : account.status === "disabled");
      return matchKeyword && matchStatus;
    });
  }, [accounts, keyword, statusFilter]);

  function openAccountEditor(account: XianyuAccount) {
    setEditingAccount(account);
    setEditorDisplayName(account.display_name);
    setEditorCookie(account.cookie ?? "");
    setEditorOpen(true);
  }

  async function handleSaveAccountProfile() {
    if (!editingAccount) {
      return;
    }
    try {
      setEditorSaving(true);
      const cookieChanged = editorCookie.trim() !== (editingAccount.cookie ?? "");
      await accountUpdate(OWNER_ID, editingAccount.account_id, {
        display_name: editorDisplayName.trim(),
        cookie: editorCookie.trim() || undefined,
      });
      toast.success(cookieChanged ? "登录信息已更新，请先断开再连接以生效" : "账号配置已更新");
      setEditorOpen(false);
      setEditingAccount(null);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setEditorSaving(false);
    }
  }

  async function handleConnect(account: XianyuAccount) {
    if (!account.cookie?.trim()) {
      toast.error("账号尚未登录，请先扫码登录");
      return;
    }
    setConnectingId(account.account_id);
    setConnectionStates((current) => ({ ...current, [account.account_id]: "connecting" }));

    if (!deps.connect) {
      try {
        const online = await accountProbeLogin(OWNER_ID, account.account_id);
        if (!online) {
          setConnectionStates((current) => ({
            ...current,
            [account.account_id]: "auth_expired",
          }));
          setConnectionDetails((current) => ({
            ...current,
            [account.account_id]: "登录态已过期，请重新扫码",
          }));
          toast.error("登录态已过期，请重新扫码", {
            action: {
              label: "重新扫码",
              onClick: () => openRescanQr(account),
            },
          });
          return;
        }
        setConnectionStates((current) => ({
          ...current,
          [account.account_id]: "connected",
        }));
        setConnectionDetails((current) => {
          const next = { ...current };
          delete next[account.account_id];
          return next;
        });
        toast.success("登录态有效");
      } finally {
        setConnectingId(null);
      }
      return;
    }

    try {
      const state = normalizeChannelConnectionState(
        await deps.connect(OWNER_ID, account.account_id),
      );
      setConnectionStates((current) => ({ ...current, [account.account_id]: state }));
      setConnectionDetails((current) => {
        const next = { ...current };
        delete next[account.account_id];
        return next;
      });
      await load();
      await setAccountConnected(account.account_id, true);
      toast.success(
        state === "connected" ? "连接成功，已同步用户资料并开始监听消息" : `连接状态：${CHANNEL_CONNECTION_STATUS_MAP[state].label}`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (isAuthExpiredText(message)) {
        setConnectionStates((current) => ({
          ...current,
          [account.account_id]: "auth_expired",
        }));
        setConnectionDetails((current) => ({
          ...current,
          [account.account_id]: "登录态已过期，请重新扫码后再连接",
        }));
        toast.error("登录态已过期，请重新扫码后再连接", {
          action: {
            label: "重新扫码",
            onClick: () => openRescanQr(account),
          },
        });
      } else {
        toast.error(message);
      }
    } finally {
      setConnectingId(null);
    }
  }

  async function handleDisconnect(account: XianyuAccount) {
    invalidateProbeCache(account.account_id);
    if (deps.disconnect) {
      try {
        await deps.disconnect(OWNER_ID, account.account_id);
        await setAccountConnected(account.account_id, false);
        setConnectionStates((current) => ({ ...current, [account.account_id]: "disconnected" }));
        toast.success("已断开连接");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : String(error));
      }
      return;
    }
    await setAccountConnected(account.account_id, false);
    setConnectionStates((current) => ({ ...current, [account.account_id]: "disconnected" }));
    toast.success("已断开连接");
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await accountDelete(OWNER_ID, deleteTarget.account_id);
      if (autoConnect) {
        setAutoConnectIds(await autoConnect.setAccount(deleteTarget.account_id, false));
      }
      await setAccountConnected(deleteTarget.account_id, false);
      toast.success("账号已删除");
      setDeleteTarget(null);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleToggleAutoConnect() {
    if (!autoConnect) {
      return;
    }
    const next = !autoConnectOnStart;
    try {
      await autoConnect.setEnabled(next);
      setAutoConnectOnStart(next);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
      return;
    }
    if (!next) {
      toast.success("已关闭启动自动连接");
      return;
    }
    if (autoConnectIds.length === 0) {
      toast.success("已开启启动自动连接：请在账号卡片上勾选要自动连接的账号");
      return;
    }
    toast.success("已开启：启动时连接勾选的闲鱼账号；1688 勾选仅保留在配置中");
    setAutoConnecting(true);
    try {
      const count = await autoConnect.runNow();
      toast.success(
        count > 0
          ? `已开始连接 ${count} 个闲鱼账号`
          : "勾选账号中暂无可连接的闲鱼账号（1688 账号无需渠道连接）",
      );
      await refreshConnectionStates(accounts.map((account) => account.account_id));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setAutoConnecting(false);
    }
  }

  async function handleToggleAccountAutoConnect(accountId: string, selected: boolean) {
    if (!autoConnect) {
      return;
    }
    try {
      const next = await autoConnect.setAccount(accountId, selected);
      setAutoConnectIds(next);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  function openQrLogin() {
    setQrTitle("扫码登录");
    setQrHint(defaultQrHint);
    setQrSeq((seq) => seq + 1);
    setQrOpen(true);
  }

  /**
   * 打开重新扫码弹窗（同 unb 账号会更新 Cookie，无需新建）。
   *
   * @author Xiaoman
   * @created 2026-08-21
   *
   * @param account - 需要刷新登录态的账号
   */
  function openRescanQr(account: XianyuAccount) {
    const name = account.display_name || account.account_id;
    setQrTitle("重新扫码登录");
    setQrHint(`请用 ${appName} App 扫码，刷新「${name}」的登录态`);
    setQrSeq((seq) => seq + 1);
    setQrOpen(true);
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
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-32">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="active">已启用</SelectItem>
              <SelectItem value="disabled">已停用</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {autoConnect ? (
            <Button
              variant={autoConnectOnStart ? "default" : "outline"}
              disabled={autoConnecting}
              onClick={() => void handleToggleAutoConnect()}
              title="开启后启动应用只连接勾选的闲鱼账号；1688 账号可勾选但不走渠道连接；风控未过滑块约 10 分钟后重试"
            >
              {autoConnecting
                ? "连接中…"
                : autoConnectOnStart
                  ? `启动自动连接：开（${autoConnectIds.length}）`
                  : "启动自动连接：关"}
            </Button>
          ) : null}
          <Button variant="outline" onClick={openQrLogin}>
            <QrCode className="size-4" aria-hidden />
            扫码登录
          </Button>
        </div>
      </div>

      {loading ? (
        <Loading size="lg" text="加载中..." className="py-16" />
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-muted-foreground">
            暂无 {platformName} 账号，请先扫码登录添加
          </p>
          <Button variant="outline" onClick={openQrLogin}>
            <QrCode className="size-4" aria-hidden />
            扫码登录
          </Button>
        </div>
      ) : (
        <PageCardGrid>
            {filtered.map((account) => {
              const displayState = normalizeChannelConnectionState(
                connectionStates[account.account_id],
              );
              const conn = accountSessionStatusView(displayState, supportsConnection);
              const hint = isLoginSession
                ? loginSessionStatusHint(displayState, connectionDetails[account.account_id])
                : connectionStatusHint(displayState, connectionDetails[account.account_id]);
              const authExpired = displayState === "auth_expired";
              const renewing = displayState === "renewing";
              const queued = displayState === "queued";
              const sliderBusy = renewing || queued;
              const isConnecting = connectingId === account.account_id;
              const hasCookie = Boolean(account.cookie?.trim());
              return (
                <PageGlowCard
                  key={account.account_id}
                  role="button"
                  tabIndex={0}
                  className="flex h-full flex-col text-left transition hover:bg-muted/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => openAccountEditor(account)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openAccountEditor(account);
                    }
                  }}
                >
                  <div className="relative flex h-full min-h-0 flex-col rounded-[inherit] border border-border bg-card p-4 transition hover:border-primary/40">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      {account.avatar_url ? (
                        <img
                          src={account.avatar_url}
                          alt=""
                          className="size-10 shrink-0 rounded-full border border-border object-cover"
                        />
                      ) : (
                        <div
                          className="flex size-10 shrink-0 items-center justify-center rounded-full border border-border bg-muted text-[length:var(--text-sm)] font-medium text-muted-foreground"
                          aria-hidden
                        >
                          {(account.display_name || account.account_id).slice(0, 1)}
                        </div>
                      )}
                      <div className="min-w-0 space-y-1">
                        <div className="truncate text-[length:var(--text-base)] font-medium">
                          {account.display_name || account.account_id}
                        </div>
                        <div className="truncate font-mono text-[length:var(--text-xs)] text-muted-foreground">
                          {account.account_id}
                        </div>
                      </div>
                    </div>
                    <span
                      className={
                        account.status === "active"
                          ? "rounded-full bg-emerald-500/15 px-2 py-0.5 text-[length:var(--text-xs)] text-emerald-500"
                          : "rounded-full bg-muted px-2 py-0.5 text-[length:var(--text-xs)] text-muted-foreground"
                      }
                    >
                      {account.status === "active" ? "启用" : "停用"}
                    </span>
                  </div>

                  <div className="mt-4 min-h-0 flex-1 space-y-2 text-[length:var(--text-sm)]">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">
                        {isLoginSession ? "登录状态" : "连接状态"}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[length:var(--text-xs)] ${conn.badgeClass}`}
                        title={hint ?? undefined}
                      >
                        {conn.label}
                      </span>
                    </div>
                    {/* 固定占位，避免有无提示文案时同行高度视觉跳动 */}
                    <p
                      className={`min-h-[1.25rem] text-[length:var(--text-xs)] ${
                        authExpired
                          ? "text-orange-700"
                          : renewing
                            ? "text-sky-700"
                            : queued
                              ? "text-violet-700"
                              : displayState === "error"
                                ? "text-red-600"
                                : "invisible"
                      }`}
                      aria-hidden={!hint}
                    >
                      {hint ?? "占位"}
                    </p>
                  </div>

                  <div
                    className="mt-4 flex flex-wrap items-center gap-2"
                    onClick={(event) => event.stopPropagation()}
                  >
                    {autoConnect ? (
                      <label className="mr-auto flex items-center gap-2 text-[length:var(--text-sm)] text-muted-foreground">
                        <Checkbox
                          checked={autoConnectIds.includes(account.account_id)}
                          onCheckedChange={(checked) =>
                            void handleToggleAccountAutoConnect(account.account_id, checked === true)
                          }
                          aria-label={`自动连接 ${account.display_name || account.account_id}`}
                        />
                        自动连接
                      </label>
                    ) : null}
                    {authExpired || !hasCookie ? (
                      <Button
                        size="sm"
                        variant={authExpired ? undefined : "outline"}
                        onClick={() => openRescanQr(account)}
                      >
                        <QrCode className="size-3.5" aria-hidden />
                        重新扫码
                      </Button>
                    ) : null}
                    {!isLoginSession ? (
                      displayState === "connected" ? (
                        <Button size="sm" variant="outline" onClick={() => void handleDisconnect(account)}>
                          断开
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isConnecting || !hasCookie || authExpired || sliderBusy}
                          onClick={() => void handleConnect(account)}
                          title={
                            !hasCookie
                              ? "请先扫码登录"
                              : authExpired
                                ? "请先重新扫码刷新登录态"
                                : renewing
                                  ? "正在过滑块，请稍候"
                                  : queued
                                    ? "排队等待过滑块，请稍候"
                                    : undefined
                          }
                        >
                          {isConnecting ? "连接中…" : "连接"}
                        </Button>
                      )
                    ) : null}
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(account)}
                    >
                      <Trash2 className="size-3.5" aria-hidden />
                      删除
                    </Button>
                  </div>
                  </div>
                </PageGlowCard>
              );
            })}
          </PageCardGrid>
      )}

      {/* 扫码登录弹窗 */}
      <AccountQrDialog
        key={qrSeq}
        open={qrOpen}
        platform={platform}
        title={qrTitle}
        hint={qrHint}
        onClose={() => setQrOpen(false)}
        onSuccess={() => {
          void (async () => {
            await load();
            if (supportsConnection) {
              const list = await accountList(OWNER_ID);
              await refreshConnectionStates(
                list
                  .filter((account) => resolveAccountPlatform(account) === platform)
                  .map((account) => account.account_id),
              );
            } else {
              const list = await accountList(OWNER_ID);
              await refreshLoginSessionProbe(
                list.filter((account) => resolveAccountPlatform(account) === platform),
              );
            }
            toast.success(`${platformName} 扫码成功`);
          })().catch((error) => {
            toast.error(error instanceof Error ? error.message : String(error));
          });
        }}
      />

      <ConfirmModal
        isOpen={editorOpen}
        title={editingAccount ? `编辑账号 · ${editingAccount.account_id}` : "编辑账号"}
        message={
          <div className="space-y-3 text-left">
            <label className="block space-y-1">
              <span className="text-[length:var(--text-sm)] text-muted-foreground">显示名称</span>
              <Input
                value={editorDisplayName}
                onChange={(event) => setEditorDisplayName(event.target.value)}
                placeholder="账号展示名"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[length:var(--text-sm)] text-muted-foreground">
                登录信息（风控验证或重新登录后更新）
              </span>
              <Textarea
                value={editorCookie}
                onChange={(event) => setEditorCookie(event.target.value)}
                placeholder={`在浏览器登录 ${platformName} 后，将登录信息粘贴到这里`}
                rows={5}
                className="font-mono text-xs"
              />
              <span className="block text-[length:var(--text-xs)] text-muted-foreground/80">
                一般通过扫码登录自动获取；仅在平台要求重新验证时手动更新。留空则不修改。
              </span>
            </label>
          </div>
        }
        confirmText={editorSaving ? "保存中…" : "保存"}
        loading={editorSaving}
        onConfirm={() => void handleSaveAccountProfile()}
        onCancel={() => {
          if (editorSaving) {
            return;
          }
          setEditorOpen(false);
          setEditingAccount(null);
        }}
      />

      {/* 删除确认 */}
      <ConfirmModal
        isOpen={deleteTarget !== null}
        type="danger"
        title="删除账号"
        message={`确认删除账号「${deleteTarget?.account_id ?? ""}」？该操作不可撤销。`}
        confirmText="删除"
        onConfirm={() => void handleDelete()}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
