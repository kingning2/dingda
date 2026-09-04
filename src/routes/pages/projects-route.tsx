import { useNavigate } from "react-router-dom";

import { ProjectsPage } from "@/pages/projects-page";
import { MOCK_PROJECTS } from "@/lib/mock-data";
import { paths } from "@/routes/paths";

export function ProjectsRoute() {
  const navigate = useNavigate();

  return (
    <ProjectsPage
      projects={MOCK_PROJECTS}
      onOpenProject={(workId) => navigate(paths.work(workId))}
    />
  );
}
