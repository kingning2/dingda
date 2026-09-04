import { Users } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

export function CommunityPage() {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center py-16">
      <Card className="max-w-md text-center">
        <CardHeader className="items-center">
          <span className="mb-2 flex size-14 items-center justify-center rounded-xl bg-muted">
            <Users className="size-7 text-muted-foreground" />
          </span>
          <CardDescription>
            浏览社区模板与分享作品，此页面为占位，后续可接入社区内容。
          </CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </section>
  );
}
