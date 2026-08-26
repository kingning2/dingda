/**
 * AI 配置 store — 持有内置平台与账号,每次变更整体持久化到 Rust 端。
 *
 * 平台为内置(DeepSeek / 豆包 / Ollama),固定不可增删;仅默认模型与账号可配置。
 * `authless` 等前端展示标记不落入持久化,回读时合并回内置平台。
 *
 * 以 `use` 前缀命名,使 React Compiler 将其识别为 hook,
 * 避免被当作普通函数调用而缓存跳过(导致 hook 顺序错位)。
 *
 * @author coisini
 * @created 2026-08-11
 */

import type {
  AiAccount,
  AiGraphModels,
  AiIpcConfigRequest,
  AiProvider,
} from "@desk/contracts";
import { aiConfigGet, aiConfigSet } from "@desk/platform/ipc/ai";
import { createDeskStore } from "@desk/store";
import {
  BUILT_IN_PROVIDERS,
  BUILT_IN_PROVIDER_IDS,
  type BuiltInProvider,
} from "./builtin-providers";

export type AiAccountInput = Omit<AiAccount, "id">;

export const AI_GRAPH_NODES = [
  "web_research",
  "article_analyze",
  "planner",
  "analyze",
  "finalize",
] as const;

function toError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * AI 配置 store 状态。
 *
 * @author coisini
 * @created 2026-08-11
 */
export interface AiConfigState {
  /** 平台列表（内置，固定）。 */
  providers: BuiltInProvider[];
  /** 账号列表。 */
  accounts: AiAccount[];
  /** 比价图节点模型路由 / failover。 */
  graphModels: AiGraphModels;
  /** 是否加载中。 */
  loading: boolean;
  /** 是否已加载过。 */
  loaded: boolean;
  /** 最近一次错误信息。 */
  error: string | null;
  /** 从 Rust 端加载配置。 */
  load: () => Promise<void>;
  /** 设置内置平台默认模型（无账号平台用，如 Ollama）。 */
  setProviderDefaultModel: (id: string, defaultModel: string) => Promise<void>;
  /** 新增账号。 */
  addAccount: (input: AiAccountInput) => Promise<void>;
  /** 更新账号。 */
  updateAccount: (id: string, patch: Partial<AiAccountInput>) => Promise<void>;
  /** 删除账号。 */
  removeAccount: (id: string) => Promise<void>;
  /** 设置图节点使用的账号。 */
  setGraphNodeAccount: (node: string, accountId: string) => Promise<void>;
  /** 设置欠费 failover 顺序。 */
  setFailoverAccountIds: (ids: string[]) => Promise<void>;
  /** 开关 failover。 */
  setFailoverEnabled: (enabled: boolean) => Promise<void>;
}

/**
 * AI 配置 store。
 *
 * @author coisini
 * @created 2026-08-11
 */
export const useAiConfigStore = createDeskStore<AiConfigState>((set, get) => {
  /** 将持久化的默认模型合并回内置平台,保留前端展示标记。 */
  function mergeModels(persisted: AiProvider[]): BuiltInProvider[] {
    const models = new Map<string, string>();
    for (const provider of persisted) {
      if (provider.default_model && BUILT_IN_PROVIDER_IDS.has(provider.id)) {
        models.set(provider.id, provider.default_model);
      }
    }
    return BUILT_IN_PROVIDERS.map((provider) =>
      models.has(provider.id)
        ? { ...provider, default_model: models.get(provider.id) }
        : provider,
    );
  }

  /** 整体持久化;失败抛错、不改本地 state。 */
  async function persist(
    providers: BuiltInProvider[],
    accounts: AiAccount[],
    graphModels: AiGraphModels,
  ): Promise<void> {
    const payload: AiIpcConfigRequest = {
      providers: providers.map((provider) => ({
        id: provider.id,
        kind: provider.kind,
        name: provider.name,
        base_url: provider.base_url,
        default_model: provider.default_model,
      })),
      accounts,
      graph_models: graphModels,
    };
    const saved = await aiConfigSet(payload);
    set({
      providers: mergeModels(saved.providers),
      accounts: saved.accounts,
      graphModels: saved.graph_models ?? graphModels,
    });
  }

  return {
    providers: BUILT_IN_PROVIDERS,
    accounts: [],
    graphModels: {
      node_accounts: AI_GRAPH_NODES.map((node) => ({ node, account_id: "" })),
      failover_account_ids: [],
      failover_enabled: true,
    },
    loading: false,
    loaded: false,
    error: null,
    load: async () => {
      set({ loading: true, error: null });
      try {
        const config = await aiConfigGet();
        const graphModels = config.graph_models ?? {
          node_accounts: AI_GRAPH_NODES.map((node) => ({
            node,
            account_id: config.accounts[0]?.id ?? "",
          })),
          failover_account_ids: config.accounts.map((a) => a.id),
          failover_enabled: true,
        };
        set({
          providers: mergeModels(config.providers),
          accounts: config.accounts.filter((account) =>
            BUILT_IN_PROVIDER_IDS.has(account.provider_id),
          ),
          graphModels,
          loading: false,
          loaded: true,
        });
      } catch (error) {
        set({ error: toError(error), loading: false });
      }
    },
    setProviderDefaultModel: async (id, defaultModel) => {
      const { providers, accounts, graphModels } = get();
      await persist(
        providers.map((provider) =>
          provider.id === id
            ? { ...provider, default_model: defaultModel || undefined }
            : provider,
        ),
        accounts,
        graphModels,
      );
    },
    addAccount: async (input) => {
      const { providers, accounts, graphModels } = get();
      await persist(
        providers,
        [...accounts, { id: crypto.randomUUID(), ...input }],
        graphModels,
      );
    },
    updateAccount: async (id, patch) => {
      const { providers, accounts, graphModels } = get();
      await persist(
        providers,
        accounts.map((account) =>
          account.id === id ? { ...account, ...patch } : account,
        ),
        graphModels,
      );
    },
    removeAccount: async (id) => {
      const { providers, accounts, graphModels } = get();
      await persist(
        providers,
        accounts.filter((account) => account.id !== id),
        graphModels,
      );
    },
    setGraphNodeAccount: async (node, accountId) => {
      const { providers, accounts, graphModels } = get();
      const rows = [...(graphModels.node_accounts ?? [])];
      const idx = rows.findIndex((r) => r.node === node);
      if (idx >= 0) {
        rows[idx] = { node, account_id: accountId };
      } else {
        rows.push({ node, account_id: accountId });
      }
      await persist(providers, accounts, { ...graphModels, node_accounts: rows });
    },
    setFailoverAccountIds: async (ids) => {
      const { providers, accounts, graphModels } = get();
      await persist(providers, accounts, {
        ...graphModels,
        failover_account_ids: ids,
      });
    },
    setFailoverEnabled: async (enabled) => {
      const { providers, accounts, graphModels } = get();
      await persist(providers, accounts, {
        ...graphModels,
        failover_enabled: enabled,
      });
    },
  };
});
