/**
 * 设置 Feature — 路由化二级设置（产品深链入口）。
 */

export { SettingsLayoutPage } from "./settings-layout";
export { SETTINGS_TABS } from "./settings-tabs";
export { SettingsGeneralPage } from "./pages/general-page";
export { SettingsAccountsPage } from "./pages/accounts-page";
export { SettingsCollectionPage } from "./pages/collection-page";
export { SettingsProfitPage } from "./pages/profit-page";
export { SettingsAiPage } from "./pages/agent";
export { SettingsSubscriptionPage } from "./pages/subscription-page";

export const SETTINGS_PATH = "/settings" as const;
