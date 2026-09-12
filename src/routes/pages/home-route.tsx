import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { stashWorkDraft } from "@/components/ai/session";
import { HomeView } from "@/components/home/home-view";
import type { ComposerSubmitPayload } from "@v2/contracts/composer";
import { workSummariesToProjects } from "@/lib/work-projects";
import { createWorkId, paths } from "@/routes/paths";
import { useDiscoveryStore } from "@/stores/discovery-store";

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
