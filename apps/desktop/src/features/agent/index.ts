/**
 * AI 配置 — 内置平台与账号管理。
 */

export { AiPage } from "./ai-page";
export { AiAccountCard } from "./ai-account-card";
export type { AiAccountCardProps } from "./ai-account-card";
export { AiAccountDialog } from "./ai-account-dialog";
export { useAiConfigStore } from "./use-ai-config";
export type { AiConfigState, AiAccountInput } from "./use-ai-config";
export {
  BUILT_IN_PROVIDERS,
  BUILT_IN_PROVIDER_IDS,
  ACCOUNT_PROVIDERS,
  type BuiltInProvider,
} from "./builtin-providers";

import { Bot } from "@desk/ui/icons";

/** AI 配置（侧栏入口）。 */
export const aiFeature = {
  id: "ai",
  path: "/features/ai",
  navItem: {
    id: "ai",
    path: "/features/ai",
    label: "AI 配置",
    icon: Bot,
  },
};
