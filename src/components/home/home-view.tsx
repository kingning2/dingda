import { HomeHero } from "./home-hero";
import { RecentProjectsStrip } from "./recent-projects-strip";
import type { Project } from "@/lib/mock-data";
import type { HomeTypeChipId } from "@/lib/mock-data";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import { cn } from "@/lib/utils";

interface HomeViewProps {
  projects: Project[];
  onSubmit?: (payload: ComposerSubmitPayload, chipId: HomeTypeChipId) => void;
  onOpenProject?: (id: string) => void;
  onViewAllProjects?: () => void;
}

export function HomeView({
  projects,
  onSubmit,
  onOpenProject,
  onViewAllProjects,
}: HomeViewProps) {
  const centered = projects.length === 0;

  return (
    <div
      className={cn(
        "relative isolate flex flex-col gap-3",
        centered && "min-h-full justify-center",
      )}
    >
      <HomeHero onSubmit={onSubmit} />
      <RecentProjectsStrip
        projects={projects}
        onOpenProject={onOpenProject}
        onViewAll={onViewAllProjects}
      />
    </div>
  );
}
