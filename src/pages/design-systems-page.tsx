import { Palette } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

export function DesignSystemsPage() {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center py-16">
      <Card className="max-w-md text-center">
        <CardHeader className="items-center">
          <span className="mb-2 flex size-14 items-center justify-center rounded-xl bg-muted">
            <Palette className="size-7 text-muted-foreground" />
          </span>
          <CardDescription>管理品牌设计系统与组件库，此页面为占位。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </section>
  );
}
