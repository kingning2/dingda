import { Card, CardContent } from "@/components/tailgrids/core/card";
import { cn } from "@/utils/cn";
import { MOCK_STATS } from "@/content/business";

export function StatCards() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {MOCK_STATS.map((stat) => (
        <Card key={stat.label}>
          <CardContent className="p-5">
            <p className="text-sm text-text-tertiary">{stat.label}</p>
            <p className="mt-2 text-2xl font-semibold text-text-primary">{stat.value}</p>
            <p
              className={cn(
                "mt-1 text-xs",
                stat.trend === "up" ? "text-green-600" : "text-text-tertiary",
              )}
            >
              {stat.hint}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
