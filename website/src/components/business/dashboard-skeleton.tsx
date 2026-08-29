"use client";

import Link from "next/link";
import { buttonStyles } from "@/components/tailgrids/core/button";
import { DASHBOARD_SECTIONS } from "@/content/business";
import { PageHeader, PlaceholderCard } from "./shell";
import { StatCards } from "./stat-cards";

export function DashboardSkeleton() {
  return (
    <div className="mt-6 space-y-5">
      <PageHeader
        title="工作台"
        subtitle="今天有什么值得卖？Agent 探索的热门机会会汇总在这里。"
        action={
          <Link
            href="/console/discovery/start"
            className={buttonStyles({ size: "md", className: "bg-brand-500" })}
          >
            开始选品
          </Link>
        }
      />

      <div className="space-y-5 px-2 lg:px-5">
        <StatCards />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {DASHBOARD_SECTIONS.map((section, index) => (
            <PlaceholderCard
              key={section.title}
              title={section.title}
              description={section.description}
              className={index === 0 ? "md:col-span-2 md:row-span-2" : undefined}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
