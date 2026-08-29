/**
 * 工作区内容出口 — 按当前路由懒加载选品产品页。
 */

import { type ComponentType, useEffect, useState } from "react";
import { DISCOVERY_AVAILABLE } from "@feature/discovery";
import { isLicensedRoute, UnlockPage, useLicenseGateContext } from "@license";
import { logFirstScreenRender } from "./first-screen-metric";

type PageLoader = () => Promise<ComponentType>;

const PAGE_LOADERS: Record<string, PageLoader> = {
  "/dashboard": async () => {
    const { DashboardPage } = await import("@feature/dashboard/dashboard-page");
    return DashboardPage;
  },
  "/products": async () => {
    const { ProductsPage } = await import("@feature/products/products-page");
    return ProductsPage;
  },
  "/tasks": async () => {
    const { TasksPage } = await import("@feature/tasks/tasks-page");
    return TasksPage;
  },
  "/profit/calculator": async () => {
    const { ProfitCalculatorPage } = await import("@feature/profit/calculator-page");
    return ProfitCalculatorPage;
  },
  "/profit/templates": async () => {
    const { ProfitTemplatesPage } = await import("@feature/profit/templates-page");
    return ProfitTemplatesPage;
  },
  "/profit": async () => {
    const { ProfitCalculatorPage } = await import("@feature/profit/calculator-page");
    return ProfitCalculatorPage;
  },
  "/monitoring/subscriptions": async () => {
    const { MonitoringSubscriptionsPage } = await import(
      "@feature/monitoring/subscriptions-page"
    );
    return MonitoringSubscriptionsPage;
  },
  "/monitoring/alerts": async () => {
    const { MonitoringAlertsPage } = await import("@feature/monitoring/alerts-page");
    return MonitoringAlertsPage;
  },
  "/monitoring/rules": async () => {
    const { MonitoringRulesPage } = await import("@feature/monitoring/rules-page");
    return MonitoringRulesPage;
  },
  "/monitoring": async () => {
    const { MonitoringSubscriptionsPage } = await import(
      "@feature/monitoring/subscriptions-page"
    );
    return MonitoringSubscriptionsPage;
  },
  "/settings/general": async () => {
    const { SettingsGeneralPage } = await import("@feature/settings/pages/general-page");
    return SettingsGeneralPage;
  },
  "/settings/accounts": async () => {
    const { SettingsAccountsPage } = await import("@feature/settings/pages/accounts-page");
    return SettingsAccountsPage;
  },
  "/settings/collection": async () => {
    const { SettingsCollectionPage } = await import("@feature/settings/pages/collection-page");
    return SettingsCollectionPage;
  },
  "/settings/profit": async () => {
    const { SettingsProfitPage } = await import("@feature/settings/pages/profit-page");
    return SettingsProfitPage;
  },
  "/settings/ai": async () => {
    const { SettingsAiPage } = await import("@feature/settings/pages/agent");
    return SettingsAiPage;
  },
  "/settings/subscription": async () => {
    const { SettingsSubscriptionPage } = await import(
      "@feature/settings/pages/subscription-page"
    );
    return SettingsSubscriptionPage;
  },
  "/settings": async () => {
    const { SettingsGeneralPage } = await import("@feature/settings/pages/general-page");
    return SettingsGeneralPage;
  },
  ...(DISCOVERY_AVAILABLE
    ? ({
        "/discovery/high-profit": async () => {
          const { DiscoveryHighProfitPage } = await import(
            "@feature/discovery/pages/list-pages"
          );
          return DiscoveryHighProfitPage;
        },
        "/discovery/hot": async () => {
          const { DiscoveryHotPage } = await import("@feature/discovery/pages/list-pages");
          return DiscoveryHotPage;
        },
        "/discovery/blue-ocean": async () => {
          const { DiscoveryBlueOceanPage } = await import(
            "@feature/discovery/pages/list-pages"
          );
          return DiscoveryBlueOceanPage;
        },
        "/discovery/new": async () => {
          const { DiscoveryNewPage } = await import("@feature/discovery/pages/list-pages");
          return DiscoveryNewPage;
        },
        "/discovery/start": async () => {
          const { DiscoveryStartPage } = await import("@feature/discovery/pages/start-page");
          return DiscoveryStartPage;
        },
        "/discovery": async () => {
          const { DiscoveryHighProfitPage } = await import(
            "@feature/discovery/pages/list-pages"
          );
          return DiscoveryHighProfitPage;
        },
      } satisfies Record<string, PageLoader>)
    : {}),
};

const pageCache = new Map<string, ComponentType>();

function resolveLoader(path: string): PageLoader | undefined {
  const exact = PAGE_LOADERS[path];
  if (exact) {
    return exact;
  }

  if (/^\/products\/[^/]+(?:\/(supply|demand|matches|profit|history))?$/.test(path)) {
    return async () => {
      const { ProductDetailPage } = await import("@feature/products/product-detail-page");
      return ProductDetailPage;
    };
  }

  if (/^\/tasks\/[^/]+$/.test(path)) {
    return async () => {
      const { TaskDetailPage } = await import("@feature/tasks/task-detail-page");
      return TaskDetailPage;
    };
  }

  return undefined;
}

async function loadWorkspacePage(path: string): Promise<ComponentType | null> {
  const cached = pageCache.get(path);
  if (cached) {
    return cached;
  }
  const loader = resolveLoader(path);
  if (!loader) {
    return null;
  }
  const Page = await loader();
  pageCache.set(path, Page);
  return Page;
}

export interface WorkspaceOutletProps {
  activePath: string;
}

export function WorkspaceOutlet({ activePath }: WorkspaceOutletProps) {
  const { gateBlocks } = useLicenseGateContext();
  const [Page, setPage] = useState<ComponentType | null>(() => pageCache.get(activePath) ?? null);

  useEffect(() => {
    if (!Page) {
      return;
    }

    let nestedFrame = 0;
    const frame = window.requestAnimationFrame(() => {
      nestedFrame = window.requestAnimationFrame(() => {
        logFirstScreenRender(activePath);
      });
    });

    return () => {
      window.cancelAnimationFrame(frame);
      if (nestedFrame) {
        window.cancelAnimationFrame(nestedFrame);
      }
    };
  }, [Page, activePath]);

  useEffect(() => {
    let cancelled = false;
    const cached = pageCache.get(activePath);
    if (cached) {
      setPage(() => cached);
      return;
    }

    setPage(null);
    void loadWorkspacePage(activePath).then((loaded) => {
      if (!cancelled && loaded) {
        setPage(() => loaded);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [activePath]);

  if (gateBlocks && isLicensedRoute(activePath)) {
    return <UnlockPage inline />;
  }

  if (!Page) {
    return (
      <div
        className="flex min-h-0 flex-1 items-center justify-center text-muted-foreground"
        aria-busy="true"
        role="status"
      />
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <Page />
    </div>
  );
}
