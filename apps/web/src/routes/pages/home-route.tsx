import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { stashWorkDraft } from "@v2/ui-ai/session";
import { HomeView } from "@v2/ui-home/home-view";
import type { ComposerSubmitPayload } from "@v2/contracts/composer";
import { workSummariesToProjects } from "@v2/ui-home/work-projects";
import { createWorkId, paths } from "@v2/routes/paths";
import { useDiscoveryStore } from "@v2/app-state";

export function HomeRoute() {
  const navigate = useNavigate();
  const recentWorks = useDiscoveryStore((state) => state.recentWorks);
  const projects = workSummariesToProjects(recentWorks.slice(0, 8));

  const handleStartWork = useCallback(
    (draft: ComposerSubmitPayload) => {
      const workId = createWorkId();
      stashWorkDraft(workId, draft);
      navigate(paths.work(workId));
    },
    [navigate],
  );

  return (
    <HomeView
      projects={projects}
      onViewAllProjects={() => navigate(paths.projects)}
      onOpenProject={(workId) => navigate(paths.work(workId))}
      onSubmit={(draft) => handleStartWork(draft)}
    />
  );
}
