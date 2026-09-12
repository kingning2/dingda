import { createHashRouter } from "react-router-dom";

import { AccountsPage } from "@web/pages/accounts-page";
import { AgentsPage } from "@web/pages/agents-page";
import { AssetsPage } from "@web/pages/assets-page";
import { CrawlerPage } from "@web/pages/crawler-page";
import { IntegrationsPage } from "@web/pages/integrations-page";
import { PluginsPage } from "@web/pages/plugins-page";
import { AppLayout } from "@web/routes/layouts/app-layout";
import { EntryLayout } from "@web/routes/layouts/entry-layout";
import { WorkspaceLayout } from "@web/routes/layouts/workspace-layout";
import { HomeRoute } from "@web/routes/pages/home-route";
import { ProjectsRoute } from "@web/routes/pages/projects-route";
import {
  ErrorTestRoute,
  NotFoundRoute,
  NotImplementedRoute,
} from "@web/routes/pages/status-routes";
import { WorkRoute } from "@web/routes/pages/work-route";
import { paths } from "@v2/routes/paths";
import type { EntryRouteHandle } from "@web/routes/route-handle";

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
