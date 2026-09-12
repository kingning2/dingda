import { FolderOpen } from "lucide-react";
import type { Project } from "@v2/ui-home/mock-data";
import { Card, CardContent } from "@v2/ui-primitives/card";

interface ProjectsPageProps {
  projects: Project[];
  onOpenProject?: (id: string) => void;
}

export function ProjectsPage({ projects, onOpenProject }: ProjectsPageProps) {
  return (
    <section className="pb-8">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Card
            key={project.id}
            className="cursor-pointer transition-all hover:shadow-md"
            onClick={() => onOpenProject?.(project.id)}
          >
            <CardContent className="flex items-center gap-3">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                <FolderOpen className="size-[18px] text-muted-foreground" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{project.name}</p>
                <p className="text-xs text-muted-foreground">{project.updatedAt}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
