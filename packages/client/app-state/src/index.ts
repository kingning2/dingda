/**
 * @v2/app-state —— 跨域共享 UI 状态的唯一来源。
 *
 * 只依赖 @v2/contracts，是依赖图上的叶子节点，任何业务包都可以安全依赖它。
 */
export {
  ACCOUNT_PLATFORMS,
  getDiscoveryAccounts,
  getDiscoveryAgents,
  useDiscoveryStore,
} from "./discovery-store";
export type { DiscoveryState } from "./discovery-store";
