import { useState } from "react";
import type { AccountPlatform } from "@v2/contracts/account";
import { ACCOUNT_TABS } from "./mock-data";
import { AccountsPanel } from "./accounts-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@v2/ui-primitives/tabs";

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
