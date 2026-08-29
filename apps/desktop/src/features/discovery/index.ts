/**
 * Discovery Feature — 选品发现（闲鱼 × 1688）。
 */

import { TrendingUp } from "@desk/ui/icons";
import { HAS_XIANYU, HAS_ALI1688 } from "@desk/platform/compile";

export { DiscoveryShell } from "./discovery-shell";
export {
  DiscoveryHighProfitPage,
  DiscoveryHotPage,
  DiscoveryBlueOceanPage,
  DiscoveryNewPage,
} from "./pages/list-pages";
export { DiscoveryStartPage } from "./pages/start-page";

/** 双站齐备时才暴露选品能力。 */
export const DISCOVERY_AVAILABLE: boolean = HAS_XIANYU && HAS_ALI1688;

/** 选品发现路由路径。 */
export const DISCOVERY_PATH = "/discovery" as const;

/** Discovery 功能路由与侧栏元信息。 */
export const discoveryFeature = {
  id: "discovery",
  path: DISCOVERY_PATH,
  navItem: {
    id: "discovery",
    path: DISCOVERY_PATH,
    label: "选品发现",
    icon: TrendingUp,
  },
};
