import { useEffect, useState } from "react";
import { useMatches } from "react-router-dom";

import { EntryShell } from "@/components/layout/entry-shell";
import { ensureAgentRuntimesScanned } from "@/lib/agent-runtime-scan";
import { resolveRouteTitle, type EntryRouteHandle } from "@/routes/route-handle";

export function EntryLayout() {
  const [railOpen, setRailOpen] = useState(true);
  const matches = useMatches();
  const fullBleed = matches.some(
    (match) => (match.handle as EntryRouteHandle | undefined)?.fullBleed === true,
  );
  const pageTitle = resolveRouteTitle(matches);

  useEffect(() => {
    void ensureAgentRuntimesScanned();
  }, []);

  return (
    <EntryShell
      railOpen={railOpen}
      onToggleRail={() => setRailOpen((open) => !open)}
      fullBleed={fullBleed}
      pageTitle={pageTitle}
    />
  );
}
