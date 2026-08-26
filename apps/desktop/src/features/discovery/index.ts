/**
 * Discovery Feature — 跨平台比价选品（闲鱼 × 1688）。
 *
 * 仅当双站同时编译启用时由 router / sidebar 门控渲染，
 * 单平台构建下本模块不进 bundle（配合 tree-shaking）。
 *
 * @author coisini
 * @created 2026-08-24
 */

import { TrendingUp } from "@desk/ui/icons";
import { HAS_XIANYU, HAS_ALI1688 } from "@desk/platform/compile";

export { DiscoveryPage } from "./discovery-page";
export { FailoverPanel } from "./failover-panel";
export { usePriceCompareRun } from "./use-price-compare-run";

/** 双站齐备时才暴露选品能力。 */
export const DISCOVERY_AVAILABLE: boolean = HAS_XIANYU && HAS_ALI1688;

/** 比价选品路由路径。 */
export const DISCOVERY_PATH = "/features/discovery" as const;

/** Discovery 功能路由与侧栏元信息。 */
export const discoveryFeature = {
  id: "discovery",
  path: DISCOVERY_PATH,
  navItem: {
    id: "discovery",
    path: DISCOVERY_PATH,
    label: "比价选品",
    icon: TrendingUp,
  },
};
