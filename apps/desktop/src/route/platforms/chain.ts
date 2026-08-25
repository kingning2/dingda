/**
 * 平台路由链 — 合并插件生成的 `PLATFORM_ROUTE_STEPS`（仅含编译期启用平台）。
 */

import { PLATFORM_ROUTE_STEPS } from "virtual:dingda/platform-route-steps";

import type { PlatformRouteContribution, RouteSegment } from "./types";

function mergeRouteSegments(steps: PlatformRouteContribution[]): RouteSegment[] {
  const seen = new Set<string>();
  const merged: RouteSegment[] = [];
  for (const step of steps) {
    for (const segment of step.routeSegments) {
      if (seen.has(segment.path)) {
        continue;
      }
      seen.add(segment.path);
      merged.push(segment);
    }
  }
  return merged;
}

function mergePageLoaders(
  steps: PlatformRouteContribution[],
): PlatformRouteContribution["pageLoaders"] {
  return Object.assign({}, ...steps.map((step) => step.pageLoaders));
}

function mergeCapabilities(steps: PlatformRouteContribution[]): readonly string[] {
  const caps = new Set<string>();
  for (const step of steps) {
    for (const cap of step.platformCapabilities) {
      caps.add(cap);
    }
  }
  return [...caps];
}

function mergeNavGroups(
  steps: PlatformRouteContribution[],
): PlatformRouteContribution["manageNavGroups"] {
  return steps.flatMap((step) => step.manageNavGroups);
}

function mergeTitleResolver(
  steps: PlatformRouteContribution[],
): PlatformRouteContribution["manageTitleFromPath"] {
  return (pathname: string) => {
    for (const step of steps) {
      const title = step.manageTitleFromPath(pathname);
      if (title) {
        return title;
      }
    }
    return null;
  };
}

/** 合并后的平台路由 contribution。 */
export const mergedPlatformRoutes: PlatformRouteContribution = {
  routeSegments: mergeRouteSegments(PLATFORM_ROUTE_STEPS),
  pageLoaders: mergePageLoaders(PLATFORM_ROUTE_STEPS),
  manageNavGroups: mergeNavGroups(PLATFORM_ROUTE_STEPS),
  platformCapabilities: mergeCapabilities(PLATFORM_ROUTE_STEPS),
  manageTitleFromPath: mergeTitleResolver(PLATFORM_ROUTE_STEPS),
};

/** 所有标记了 `locked: true` 的路由路径（前缀匹配用）。 */
export const lockedRoutePaths: readonly string[] = mergedPlatformRoutes.routeSegments
  .filter((seg) => seg.locked)
  .map((seg) => `/${seg.path}`);
