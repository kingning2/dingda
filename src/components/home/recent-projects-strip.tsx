import { Layout, MoreHorizontal } from "lucide-react";
import type { Project } from "@/lib/mock-data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardFooter, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface RecentProjectsStripProps {
  projects: Project[];
  onOpenProject?: (id: string) => void;
  onViewAll?: () => void;
}

const KIND_COLORS: Record<Project["kind"], string> = {
  prototype: "from-blue-100 to-indigo-50",
  slides: "from-rose-100 to-pink-50",
  dashboard: "from-amber-100 to-orange-50",
  app: "from-emerald-100 to-teal-50",
};

export function RecentProjectsStrip({
  projects,
  onOpenProject,
  onViewAll,
}: RecentProjectsStripProps) {
  if (projects.length === 0) return null;

  return (
    <section className="mt-13 w-full">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-foreground">最近项目</h2>
        <Button variant="link" size="sm" className="h-auto p-0 text-[13px]" onClick={onViewAll}>
          查看全部
        </Button>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {projects.map((project) => (
          <Card
            key={project.id}
            size="sm"
            className="group cursor-pointer gap-0 py-0 transition-all hover:-translate-y-0.5 hover:shadow-md"
            onClick={() => onOpenProject?.(project.id)}
          >
            <CardHeader className="p-0">
              <div
                className={cn(
                  "relative flex aspect-[16/10] items-center justify-center rounded-t-xl bg-gradient-to-br",
                  KIND_COLORS[project.kind],
                )}
              >
                <Layout className="size-6 text-muted-foreground/60" />
                {project.status === "published" ? (
                  <Badge className="absolute top-2 left-2 bg-green-100 text-[11px] text-green-900 hover:bg-green-100">
                    已发布
                  </Badge>
                ) : null}
              </div>
            </CardHeader>
            <CardFooter className="items-start justify-between gap-2 border-t-0 bg-transparent p-3">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium text-foreground">{project.name}</p>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  {project.updatedAt || "刚刚"}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-xs"
                className="opacity-0 group-hover:opacity-100"
                aria-hidden
                tabIndex={-1}
                onClick={(event) => event.stopPropagation()}
              >
                <MoreHorizontal className="size-3.5" />
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </section>
  );
}
