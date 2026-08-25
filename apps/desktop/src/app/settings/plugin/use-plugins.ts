/**
 * 插件配置 store — 内置插件列表与 OCR 下载进度。
 *
 * 以 `use` 前缀命名，使 React Compiler 将其识别为 hook。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */

import type { PluginEventProgress, PluginItem } from "@desk/contracts";
import { pluginInstall, pluginList, pluginUninstall } from "@desk/platform/ipc/plugin";
import { createDeskStore } from "@desk/store";

/**
 * 插件面板状态。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */
export interface PluginState {
  /** 插件列表。 */
  items: PluginItem[];
  /** 是否正在拉取列表。 */
  loading: boolean;
  /** 是否已加载过。 */
  loaded: boolean;
  /** 最近一次错误。 */
  error: string | null;
  /** 正在安装的插件 id。 */
  installingId: string | null;
  /** 当前下载进度。 */
  progress: PluginEventProgress | null;
  /** 从 Rust 端加载插件列表。 */
  load: () => Promise<void>;
  /** 应用下载进度事件。 */
  applyProgress: (payload: PluginEventProgress) => void;
  /** 下载并安装插件。 */
  install: (pluginId: string) => Promise<void>;
  /** 卸载插件。 */
  uninstall: (pluginId: string) => Promise<void>;
}

function toError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function upsertItem(items: PluginItem[], next: PluginItem): PluginItem[] {
  const index = items.findIndex((item) => item.id === next.id);
  if (index < 0) {
    return [...items, next];
  }
  return items.map((item, current) => (current === index ? next : item));
}

/**
 * 插件配置 store。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */
export const usePluginStore = createDeskStore<PluginState>((set, get) => ({
  items: [],
  loading: false,
  loaded: false,
  error: null,
  installingId: null,
  progress: null,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const result = await pluginList();
      const installingId = get().installingId;
      set({
        items: result.items.map((item) =>
          item.id === installingId ? { ...item, status: "downloading" } : item,
        ),
        loading: false,
        loaded: true,
      });
    } catch (error) {
      set({ error: toError(error), loading: false });
    }
  },
  applyProgress: (payload) => {
    set((state) => ({
      installingId: payload.plugin_id,
      progress: payload,
      items: state.items.map((item) =>
        item.id === payload.plugin_id
          ? { ...item, status: "downloading", error: undefined }
          : item,
      ),
    }));
  },
  install: async (pluginId) => {
    set({
      installingId: pluginId,
      progress: null,
      error: null,
      items: get().items.map((item) =>
        item.id === pluginId ? { ...item, status: "downloading", error: undefined } : item,
      ),
    });
    try {
      const result = await pluginInstall(pluginId);
      set({
        items: upsertItem(get().items, result.item),
        installingId: null,
        progress: null,
      });
    } catch (error) {
      const message = toError(error);
      set({
        error: message,
        installingId: null,
        progress: null,
        items: get().items.map((item) =>
          item.id === pluginId ? { ...item, status: "failed", error: message } : item,
        ),
      });
    }
  },
  uninstall: async (pluginId) => {
    set({ error: null });
    try {
      const result = await pluginUninstall(pluginId);
      set({ items: upsertItem(get().items, result.item) });
    } catch (error) {
      set({ error: toError(error) });
    }
  },
}));
