/**
 * 账号设置 — 统一设置壳 + 嵌入式账号 Hub（无第二套大标题）。
 */

import { SettingsLayoutPage } from "../settings-layout";
import { XianyuAccountsPage } from "@feature/platform/xianyu/accounts";

export function SettingsAccountsPage() {
  return (
    <SettingsLayoutPage>
      <XianyuAccountsPage embedded />
    </SettingsLayoutPage>
  );
}
