import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { stashWorkDraft } from "@/components/ai-work/work-draft";
import { HomeView } from "@/components/home/home-view";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import { MOCK_PROJECTS } from "@/lib/mock-data";
import { createWorkId, paths } from "@/routes/paths";

export function HomeRoute() {
  const navigate = useNavigate();

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
      projects={MOCK_PROJECTS}
      onViewAllProjects={() => navigate(paths.projects)}
      onOpenProject={(workId) => navigate(paths.work(workId))}
      onSubmit={(draft) => handleStartWork(draft)}
    />
  );
}
