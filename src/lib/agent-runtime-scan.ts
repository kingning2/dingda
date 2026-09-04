/**
 * Agent 运行时扫描入口（兼容旧 import）。
 * 实现已并入 discovery-scan：与账号探测一起写 Zustand。
 */

export {
  ensureDiscoveryScanned as ensureAgentRuntimesScanned,
  ensureDiscoveryScanned,
  refreshDiscoveryOnServerReady,
  refreshDiscoveryAccounts,
  refreshDefaultAgentPreference,
  rescanAgentRuntimes,
  probeSingleAgent,
  refreshAccountsForPlatform,
} from "@/lib/discovery-scan";
