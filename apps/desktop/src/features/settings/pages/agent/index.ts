/**
 * AI 模型设置子模块（仅经 /settings/ai 进入）。
 */

export { SettingsAiPage } from "./ai-page";
export { AiAccountCard } from "./ai-account-card";
export type { AiAccountCardProps } from "./ai-account-card";
export { AiAccountDialog } from "./ai-account-dialog";
export {
  useAiConfigStore,
  providerRequiresApiKey,
  providerSupportsBalance,
} from "./use-ai-config";
export type { AiConfigState, AiAccountInput } from "./use-ai-config";
