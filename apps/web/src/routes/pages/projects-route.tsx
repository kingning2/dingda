import { useNavigate } from "react-router-dom";

import { ProjectsPage } from "@web/pages/projects-page";
import { workSummariesToProjects } from "@v2/ui-home/work-projects";
import { paths } from "@v2/routes/paths";
import { useDiscoveryStore } from "@v2/app-state";

export function ProjectsRoute() {
  const navigate = useNavigate();
  const recentWorks = useDiscoveryStore((state) => state.recentWorks);
  const projects = workSummariesToProjects(recentWorks);

  return (
    <ProjectsPage
      projects={projects}
      onOpenProject={(workId) => navigate(paths.work(workId))}
    />
  );
}
