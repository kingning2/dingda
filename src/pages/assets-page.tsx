import { useSearchParams } from "react-router-dom";
import { AgentRuntimesPanel } from "@/components/agent";
import { AccountsHub } from "@/components/accounts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { supportsExternalAgents } from "@/lib/capabilities";

type AssetsTab = "agents" | "accounts";

function parseAssetsTab(value: string | null): AssetsTab {
  if (!supportsExternalAgents()) return "accounts";
  return value === "accounts" ? "accounts" : "agents";
}

export function AssetsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const showExternalAgents = supportsExternalAgents();
  const tab = parseAssetsTab(searchParams.get("tab"));

  function setTab(next: AssetsTab) {
    if (!showExternalAgents || next === "agents") {
      setSearchParams({}, { replace: true });
      return;
    }
    setSearchParams({ tab: next }, { replace: true });
  }

  if (!showExternalAgents) {
    return (
      <section>
        <AccountsHub />
      </section>
    );
  }

  return (
    <section>
      <Tabs value={tab} onValueChange={(value) => setTab(parseAssetsTab(value))}>
        <TabsList aria-label="资产">
          <TabsTrigger value="agents">Agent</TabsTrigger>
          <TabsTrigger value="accounts">账号</TabsTrigger>
        </TabsList>
        <TabsContent value="agents">
          <AgentRuntimesPanel />
        </TabsContent>
        <TabsContent value="accounts">
          <AccountsHub />
        </TabsContent>
      </Tabs>
    </section>
  );
}
