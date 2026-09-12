import { useEffect, useState } from "react";
import { useMatches } from "react-router-dom";

import { EntryShell } from "@v2/ui-layout/entry-shell";
import { ensureDiscoveryScanned } from "@v2/ui-crawler/discovery-scan";
import { resolveRouteTitle, type EntryRouteHandle } from "@web/routes/route-handle";

export function EntryLayout() {
  const [railOpen, setRailOpen] = useState(true);
  const matches = useMatches();
  const fullBleed = matches.some(
    (match) => (match.handle as EntryRouteHandle | undefined)?.fullBleed === true,
  );
  const pageTitle = resolveRouteTitle(matches);

  useEffect(() => {
    void ensureDiscoveryScanned();
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
