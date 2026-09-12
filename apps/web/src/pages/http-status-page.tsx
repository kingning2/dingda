import { Button } from "@v2/ui-primitives/button";

type HttpStatusPageProps = {
  code: number;
  title: string;
  description: string;
  onBack: () => void;
};

export function HttpStatusPage({
  code,
  title,
  description,
  onBack,
}: HttpStatusPageProps) {
  return (
    <div className="flex min-h-full flex-col justify-center px-6 py-16">
      <p className="m-0 mb-2 text-6xl font-bold tracking-tight text-foreground">{code}</p>
      <h1 className="m-0 mb-3 text-2xl font-semibold text-foreground">{title}</h1>
      <p className="m-0 mb-6 max-w-md text-[15px] leading-relaxed text-muted-foreground">
        {description}
      </p>
      <Button variant="outline" onClick={onBack}>
        返回首页
      </Button>
    </div>
  );
}
