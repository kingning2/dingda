/**
 * 模型配置页装配。
 *
 * 职责：
 *     拉供应商目录与凭据列表，渲染加载 / 空态 / 列表 / 错误，串起卡片动作与表单弹窗。
 *
 * 设计说明：
 *     - **不建全局 store**：这一页的数据是单页的，`useState` + `useCallback` 的 `refresh`
 *       就够（与 `ui-monitor` 同一个判断），跨域状态才归 `app-state`
 *     - **不做 mock 兜底**：账号页在浏览器里会展示演示账号，但这一页展示的是凭据 ——
 *       编造出来的 key 与「使用中」标记会让人以为真配好了。服务未就绪就明说
 *     - 检测结果只活在本次会话（`checks`）：它是「刚点过的那一次」，不是凭据属性。
 *       持久那份由后端的 `last_check_*` 承担，点完顺手静默重拉一次列表即可看到
 *     - 检测与切换之后**只静默重拉凭据**，不整页 `loading`：列表整块闪一下比不刷新更烦
 */

import type { LlmCheckView, LlmCredentialItem, LlmProviderItem } from "@v2/contracts/model";
import { pushAppAlert } from "@v2/runtime/app-alert";
import { useServer } from "@v2/runtime/server-provider";
import { Button } from "@v2/ui-primitives/button";
import { Download, Loader2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  activateLlmCredential,
  importLlmCredentialFromEnv,
  listLlmCredentials,
  listLlmProviders,
  testLlmCredential,
} from "./model-config-api";
import { ModelCredentialCard } from "./model-credential-card";
import { ModelCredentialForm } from "./model-credential-form";
import { credentialTitle } from "./model-credential-view";

/** 模型配置页。 */
export function ModelConfigHub() {
  const server = useServer();
  const serverReady = server.ready && Boolean(server.apiBaseUrl);

  const [providers, setProviders] = useState<LlmProviderItem[]>([]);
  const [items, setItems] = useState<LlmCredentialItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checks, setChecks] = useState<Record<string, LlmCheckView>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<LlmCredentialItem | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [providerItems, list] = await Promise.all([listLlmProviders(), listLlmCredentials()]);
      setProviders(providerItems);
      setItems(list.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载模型配置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  /** 只重拉凭据，不整页转圈 —— 检测 / 切换之后用。 */
  const reloadCredentials = useCallback(async () => {
    try {
      const list = await listLlmCredentials();
      setItems(list.items);
    } catch {
      // 静默：刚才那次动作已经给过反馈，这里再弹一次是重复报错
    }
  }, []);

  useEffect(() => {
    if (serverReady) {
      void refresh();
    } else {
      setLoading(false);
    }
  }, [serverReady, refresh]);

  async function handleTest(item: LlmCredentialItem) {
    setBusyId(item.credential_id);
    try {
      const check = await testLlmCredential(item.credential_id);
      setChecks((prev) => ({ ...prev, [item.credential_id]: check }));
      await reloadCredentials();
    } catch (err) {
      pushAppAlert({
        title: "检测失败",
        description: err instanceof Error ? err.message : "请稍后重试",
        variant: "destructive",
      });
    } finally {
      setBusyId(null);
    }
  }

  async function handleActivate(item: LlmCredentialItem) {
    setBusyId(item.credential_id);
    try {
      await activateLlmCredential(item.credential_id);
      pushAppAlert({ title: "已切换", description: `${credentialTitle(item)} 已生效` });
      await reloadCredentials();
    } catch (err) {
      pushAppAlert({
        title: "切换失败",
        description: err instanceof Error ? err.message : "请稍后重试",
        variant: "destructive",
      });
    } finally {
      setBusyId(null);
    }
  }

  async function handleImport() {
    if (importing) return;
    setImporting(true);
    try {
      const result = await importLlmCredentialFromEnv();
      pushAppAlert({
        title: result.imported ? "已导入" : "没有可导入的配置",
        description: result.message,
        variant: result.imported ? "default" : "destructive",
      });
      if (result.imported) await refresh();
    } catch (err) {
      pushAppAlert({
        title: "导入失败",
        description: err instanceof Error ? err.message : "请稍后重试",
        variant: "destructive",
      });
    } finally {
      setImporting(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(item: LlmCredentialItem) {
    setEditing(item);
    setFormOpen(true);
  }

  const activeItem = items.find((item) => item.is_active) ?? null;
  // 一次渲染内固定基准时间：同屏几条「3 分钟前」才读得一致
  const now = Date.now() / 1000;

  if (!serverReady) {
    return (
      <p className="text-sm text-muted-foreground">
        本地服务未就绪，暂时读不到模型配置。启动服务后回到本页即可。
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-xl text-sm text-muted-foreground">
          AI 选品与对话都用这里的凭据。同一时间只有一条生效，其余作为备用留在列表里。
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void handleImport()} disabled={importing}>
            {importing ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
            从环境变量导入
          </Button>
          <Button onClick={openCreate}>
            <Plus className="size-4" />
            新增凭据
          </Button>
        </div>
      </div>

      {activeItem ? (
        <p className="text-xs text-muted-foreground">
          当前生效：{credentialTitle(activeItem)}（{activeItem.provider_name} · {activeItem.model}）
        </p>
      ) : items.length > 0 ? (
        <p className="text-xs text-destructive">
          没有生效的凭据。选一条点「设为使用中」，否则会退回环境变量里的配置。
        </p>
      ) : null}

      {loading ? <p className="text-sm text-muted-foreground">正在加载…</p> : null}

      {error ? (
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm text-destructive">模型配置加载失败：{error}</p>
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            重试
          </Button>
        </div>
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-muted-foreground">还没有模型凭据。加一条，AI 才能跑起来。</p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void handleImport()} disabled={importing}>
              <Download className="size-4" />
              从环境变量导入
            </Button>
            <Button onClick={openCreate}>
              <Plus className="size-4" />
              新增凭据
            </Button>
          </div>
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <ModelCredentialCard
              key={item.credential_id}
              item={item}
              check={checks[item.credential_id] ?? null}
              now={now}
              busy={busyId === item.credential_id}
              onTest={() => void handleTest(item)}
              onActivate={() => void handleActivate(item)}
              onEdit={() => openEdit(item)}
              onDeleted={() => void reloadCredentials()}
            />
          ))}
        </div>
      ) : null}

      <ModelCredentialForm
        open={formOpen}
        providers={providers}
        item={editing}
        onOpenChange={setFormOpen}
        onSaved={() => void refresh()}
      />
    </div>
  );
}
