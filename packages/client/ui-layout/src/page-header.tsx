interface PageHeaderProps {
  title: string;
}

export function PageHeader({ title }: PageHeaderProps) {
  return (
    <header className="space-y-1 pt-4 pb-4">
      <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
    </header>
  );
}
