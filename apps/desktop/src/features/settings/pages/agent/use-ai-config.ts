/**
 * AI 配置 store — 账号与已保存平台；目录由后端 catalog 提供。
 *
 * 以 `use` 前缀命名,使 React Compiler 将其识别为 hook。
 */

import type {
  AiAccount,
  AiGraphModels,
  AiIpcConfigRequest,
  AiProvider,
} from "@desk/contracts";
import {
  aiConfigGet,
  aiConfigSet,
  aiProvidersCatalog,
} from "@desk/platform/ipc/ai";
import { createDeskStore } from "@desk/store";

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

/** 本地 Ollama 等无需云端密钥。 */
export function providerRequiresApiKey(provider: AiProvider | undefined): boolean {
  if (!provider) return true;
  if (provider.id === "ollama") return false;
  const base = (provider.base_url ?? "").toLowerCase();
  return !base.includes("localhost:11434");
}

/** 是否支持余额查询（与 Python probe 对齐）。 */
export function providerSupportsBalance(provider: AiProvider | undefined): boolean {
  if (!provider) return false;
  if (provider.kind.toLowerCase() === "deepseek") return true;
  return (provider.base_url ?? "").toLowerCase().includes("deepseek.com");
}

export interface AiConfigState {
  /** 已持久化的平台（随账号写入）。 */
  providers: AiProvider[];
  /** 后端只读目录。 */
  catalog: AiProvider[];
  accounts: AiAccount[];
  graphModels: AiGraphModels;
  loading: boolean;
  loaded: boolean;
  error: string | null;
  load: () => Promise<void>;
  addAccount: (input: AiAccountInput) => Promise<void>;
  updateAccount: (id: string, patch: Partial<AiAccountInput>) => Promise<void>;
  removeAccount: (id: string) => Promise<void>;
  setGraphNodeAccount: (node: string, accountId: string) => Promise<void>;
  setFailoverAccountIds: (ids: string[]) => Promise<void>;
  setFailoverEnabled: (enabled: boolean) => Promise<void>;
  /** 按 id 解析平台：已保存优先，否则目录。 */
  resolveProvider: (providerId: string) => AiProvider | undefined;
}

export const useAiConfigStore = createDeskStore<AiConfigState>((set, get) => {
  async function persist(
    providers: AiProvider[],
    accounts: AiAccount[],
    graphModels: AiGraphModels,
  ): Promise<void> {
    const payload: AiIpcConfigRequest = {
      providers,
      accounts,
      graph_models: graphModels,
    };
    const saved = await aiConfigSet(payload);
    set({
      providers: saved.providers,
      accounts: saved.accounts,
      graphModels: saved.graph_models ?? graphModels,
    });
  }

  function withProvider(
    providers: AiProvider[],
    catalog: AiProvider[],
    providerId: string,
  ): AiProvider[] {
    if (providers.some((item) => item.id === providerId)) {
      return providers;
    }
    const fromCatalog = catalog.find((item) => item.id === providerId);
    if (!fromCatalog) {
      throw new Error(`未知 AI 平台：${providerId}`);
    }
    return [...providers, fromCatalog];
  }

  return {
    providers: [],
    catalog: [],
    accounts: [],
    graphModels: {
      node_accounts: AI_GRAPH_NODES.map((node) => ({ node, account_id: "" })),
      failover_account_ids: [],
      failover_enabled: true,
    },
    loading: false,
    loaded: false,
    error: null,
    resolveProvider: (providerId) => {
      const { providers, catalog } = get();
      return (
        providers.find((item) => item.id === providerId) ??
        catalog.find((item) => item.id === providerId)
      );
    },
    load: async () => {
      set({ loading: true, error: null });
      try {
        const [config, catalogRes] = await Promise.all([
          aiConfigGet(),
          aiProvidersCatalog(),
        ]);
        const graphModels = config.graph_models ?? {
          node_accounts: AI_GRAPH_NODES.map((node) => ({
            node,
            account_id: config.accounts[0]?.id ?? "",
          })),
          failover_account_ids: config.accounts.map((a) => a.id),
          failover_enabled: true,
        };
        set({
          providers: config.providers,
          catalog: catalogRes.providers,
          accounts: config.accounts,
          graphModels,
          loading: false,
          loaded: true,
        });
      } catch (error) {
        set({ error: toError(error), loading: false });
      }
    },
    addAccount: async (input) => {
      const { providers, accounts, graphModels, catalog } = get();
      const nextProviders = withProvider(providers, catalog, input.provider_id);
      await persist(
        nextProviders,
        [...accounts, { id: crypto.randomUUID(), ...input }],
        graphModels,
      );
    },
    updateAccount: async (id, patch) => {
      const { providers, accounts, graphModels, catalog } = get();
      const existing = accounts.find((account) => account.id === id);
      const providerId = patch.provider_id ?? existing?.provider_id;
      const nextProviders =
        providerId !== undefined
          ? withProvider(providers, catalog, providerId)
          : providers;
      await persist(
        nextProviders,
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
