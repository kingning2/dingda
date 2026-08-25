/**
 * 插件面板 — 设置弹窗内的内置插件（当前仅 OCR tessdata）。
 *
 * 应用启动时会检测插件是否已安装；下载需用户在设置-插件页手动触发。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */

import { useEffect, useState } from "react";
import { Button, Card, ConfirmModal, Loading, Progress } from "@desk/ui";
import { Download, Image, Trash2 } from "@desk/ui/icons";
import type { PluginEventProgress, PluginItem } from "@desk/contracts";
import { usePluginStore } from "./use-plugins";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusLabel(status: string): string {
  if (status === "installed") return "已安装";
  if (status === "downloading") return "下载中";
  if (status === "failed") return "失败";
  return "未安装";
}

/**
 * 插件设置面板入口。
 *
 * @author Xiaoman
 * @created 2026-08-19
 *
 * @returns 面板节点
 */
export function PluginsPanel() {
  const items = usePluginStore((state) => state.items);
  const loading = usePluginStore((state) => state.loading);
  const loaded = usePluginStore((state) => state.loaded);
  const loadError = usePluginStore((state) => state.error);
  const progress = usePluginStore((state) => state.progress);
  const load = usePluginStore((state) => state.load);
  const install = usePluginStore((state) => state.install);
  const uninstall = usePluginStore((state) => state.uninstall);

  const [pendingUninstall, setPendingUninstall] = useState<PluginItem | null>(null);
  const [uninstalling, setUninstalling] = useState(false);

  useEffect(() => {
    if (!loaded && !loading) {
      void load();
    }
  }, [loaded, loading, load]);

  async function confirmUninstall() {
    if (!pendingUninstall) return;
    setUninstalling(true);
    try {
      await uninstall(pendingUninstall.id);
      setPendingUninstall(null);
    } finally {
      setUninstalling(false);
    }
  }

  return (
    <div className="flex w-full flex-col gap-5">
      <p className="max-w-md text-[length:var(--text-sm)] leading-relaxed text-muted-foreground">
        应用启动时会检测插件是否已安装。文字识别语言包用于图片文字识别；浏览器辅助组件（约 500MB）用于闲鱼滑块验证。均按需下载，不随安装包分发。
      </p>

      {loadError ? (
        <p className="text-[length:var(--text-sm)] text-red-600 dark:text-red-400">{loadError}</p>
      ) : null}

      {loading && items.length === 0 ? <Loading size="sm" text="加载插件列表" /> : null}

      <div className="flex flex-col gap-3">
        {items.map((item) => (
          <PluginCard
            key={item.id}
            item={item}
            progress={progress?.plugin_id === item.id ? progress : null}
            onInstall={() => void install(item.id)}
            onRetry={() => void install(item.id)}
            onUninstall={() => setPendingUninstall(item)}
          />
        ))}
      </div>

      <ConfirmModal
        isOpen={pendingUninstall !== null}
        type="danger"
        title="卸载插件"
        message={`确定卸载「${pendingUninstall?.name ?? ""}」并删除本机已下载的插件文件吗？`}
        confirmText="卸载"
        loading={uninstalling}
        onConfirm={() => void confirmUninstall()}
        onCancel={() => setPendingUninstall(null)}
      />
    </div>
  );
}

/**
 * 单个内置插件卡片。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */
function PluginCard({
  item,
  progress,
  onInstall,
  onRetry,
  onUninstall,
}: {
  item: PluginItem;
  progress: PluginEventProgress | null;
  onInstall: () => void;
  onRetry: () => void;
  onUninstall: () => void;
}) {
  const downloading = item.status === "downloading";
  const installed = item.status === "installed";
  const failed = item.status === "failed";
  const percent =
    progress && progress.total_bytes > 0
      ? Math.min(100, Math.round((progress.received_bytes / progress.total_bytes) * 100))
      : null;

  return (
    <Card className="w-full">
      <div className="flex items-start gap-3 px-4 py-3">
        <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-[var(--radius-md)] border border-border/70 bg-muted/40">
          <Image className="size-4 text-muted-foreground" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate font-medium text-foreground">{item.name}</h3>
            <span className="shrink-0 rounded-full border border-border/70 px-2 py-0.5 text-[length:var(--text-xs)] text-muted-foreground">
              {statusLabel(item.status)}
            </span>
          </div>
          <p className="mt-1 text-[length:var(--text-sm)] leading-relaxed text-muted-foreground">
            {item.description}
          </p>
          {item.error ? (
            <p className="mt-2 text-[length:var(--text-sm)] text-red-600 dark:text-red-400">
              {item.error}
            </p>
          ) : null}
          {downloading && percent !== null ? (
            <div className="mt-3 flex flex-col gap-1.5">
              <Progress value={percent} aria-label={`${item.name} 下载进度`} />
              {progress ? (
                <p className="text-[length:var(--text-xs)] text-muted-foreground">
                  {progress.file_name}（{formatBytes(progress.received_bytes)} /{" "}
                  {formatBytes(progress.total_bytes)}）
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {installed ? (
            <Button size="sm" variant="ghost" onClick={onUninstall} disabled={downloading}>
              <Trash2 className="size-3.5" aria-hidden />
              卸载
            </Button>
          ) : downloading ? null : (
            <Button size="sm" onClick={failed ? onRetry : onInstall}>
              <Download className="size-3.5" aria-hidden />
              {failed ? "重试" : "下载"}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
