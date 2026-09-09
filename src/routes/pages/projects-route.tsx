import { useNavigate } from "react-router-dom";

import { ProjectsPage } from "@/pages/projects-page";
import { workSummariesToProjects } from "@/lib/work-projects";
import { paths } from "@/routes/paths";
import { useDiscoveryStore } from "@/stores/discovery-store";

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
