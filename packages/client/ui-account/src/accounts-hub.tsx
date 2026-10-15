import { useState } from "react";
import type { AccountPlatform } from "@v2/contracts/account";
import type { AccountPanelConfig, AccountsTab } from "./types";
import { AccountsPanel } from "./accounts-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@v2/ui-primitives/tabs";

const xianyuConfig: AccountPanelConfig = {
  platform: "xianyu",
  platformName: "闲鱼",
  appName: "闲鱼",
  supportsConnection: true,
  supportsAutoConnect: true,
};

const ali1688Config: AccountPanelConfig = {
  platform: "ali1688",
  platformName: "1688",
  appName: "手机淘宝 / 1688",
  supportsConnection: false,
};

const xiaohongshuConfig: AccountPanelConfig = {
  platform: "xiaohongshu",
  platformName: "小红书",
  appName: "小红书",
  supportsConnection: false,
};

export const ACCOUNT_TABS: AccountsTab[] = [
  { id: "xianyu", label: "闲鱼账号", config: xianyuConfig },
  { id: "ali1688", label: "1688账号", config: ali1688Config },
  { id: "xiaohongshu", label: "小红书账号", config: xiaohongshuConfig },
];

interface AccountsHubProps {
  initialTab?: AccountPlatform;
}

export function AccountsHub({ initialTab = "xianyu" }: AccountsHubProps) {
  const [tab, setTab] = useState<AccountPlatform>(initialTab);

  return (
    <div className="flex min-h-0 flex-col gap-6">
      <Tabs value={tab} onValueChange={(value) => setTab(value as AccountPlatform)}>
        <TabsList aria-label="账号平台">
          {ACCOUNT_TABS.map((item) => (
            <TabsTrigger key={item.id} value={item.id}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {ACCOUNT_TABS.map((item) => (
          <TabsContent key={item.id} value={item.id}>
            <AccountsPanel config={item.config} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
