import { createHashRouter } from "react-router-dom";

import { AccountsPage } from "@/pages/accounts-page";
import { AgentsPage } from "@/pages/agents-page";
import { AssetsPage } from "@/pages/assets-page";
import { CrawlerPage } from "@/pages/crawler-page";
import { IntegrationsPage } from "@/pages/integrations-page";
import { PluginsPage } from "@/pages/plugins-page";
import { AppLayout } from "@/routes/layouts/app-layout";
import { EntryLayout } from "@/routes/layouts/entry-layout";
import { WorkspaceLayout } from "@/routes/layouts/workspace-layout";
import { HomeRoute } from "@/routes/pages/home-route";
import { ProjectsRoute } from "@/routes/pages/projects-route";
import {
  ErrorTestRoute,
  NotFoundRoute,
  NotImplementedRoute,
} from "@/routes/pages/status-routes";
import { WorkRoute } from "@/routes/pages/work-route";
import { paths } from "@/routes/paths";
import type { EntryRouteHandle } from "@/routes/route-handle";

const entry = (title: string): EntryRouteHandle => ({ title });

export const router = createHashRouter([
  {
    element: <AppLayout />,
    children: [
      {
        path: paths.errorTest,
        element: <ErrorTestRoute />,
      },
      {
        path: paths.notImplemented,
        element: <NotImplementedRoute />,
      },
      {
        element: <WorkspaceLayout />,
        children: [
          {
            element: <EntryLayout />,
            children: [
              { index: true, element: <HomeRoute /> },
              {
                path: "projects",
                element: <ProjectsRoute />,
                handle: entry("全部项目"),
              },
              {
                path: "plugins",
                element: <PluginsPage />,
                handle: entry("扩展"),
              },
              {
                path: "agents",
                element: <AgentsPage />,
                handle: entry("Agent"),
              },
              {
                path: "accounts",
                element: <AccountsPage />,
                handle: entry("账号"),
              },
              {
                path: "assets",
                element: <AssetsPage />,
              },
              { path: "integrations", element: <IntegrationsPage /> },
              {
                path: "crawler",
                element: <CrawlerPage />,
                handle: entry("自主爬虫"),
              },
              {
                path: "work/:workId",
                element: <WorkRoute />,
                handle: { fullBleed: true },
              },
            ],
          },
        ],
      },
      { path: "404", element: <NotFoundRoute /> },
      { path: "*", element: <NotFoundRoute /> },
    ],
  },
]);
