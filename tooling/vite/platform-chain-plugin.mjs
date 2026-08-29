/**
 * Vite 平台链插件 — 按编译期启用的平台生成 virtual module，未启用平台代码不进 bundle。
 *
 * 与 Rust `platform_*` cfg / `read-channel-platform.mjs` 对齐。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */

import path from "node:path";
import { fileURLToPath } from "node:url";

import { resolveChannelPlatforms } from "../scripts/read-channel-platform.mjs";

/** virtual module id → 生成逻辑。 */
export const VIRTUAL = {
  ROUTE_STEPS: "virtual:dingda/platform-route-steps",
  IPC_CHAIN: "virtual:dingda/platform-ipc-chain",
  SETTINGS_STEPS: "virtual:dingda/platform-settings-steps",
  MANAGE_NAV: "virtual:dingda/platform-manage-nav",
  SHELL_LIFECYCLES: "virtual:dingda/platform-shell-lifecycles",
};

/** 链顺序（与 Rust / channel-platforms.json 一致）。 */
const CHAIN_ORDER = ["xianyu", "ali1688", "xiaohongshu", "douyin"];

/** 平台 id → 路由 contribution 文件（相对 repo 根）。 */
const ROUTE_CONTRIBUTION = {
  xianyu: "apps/desktop/src/route/platforms/xianyu/contribution.ts",
  ali1688: "apps/desktop/src/route/platforms/ali1688/contribution.ts",
  xiaohongshu: "apps/desktop/src/route/platforms/xiaohongshu/contribution.ts",
};

/** 平台 id → 设置分区链步骤文件。 */
const SETTINGS_STEP = {
  xianyu: "apps/desktop/src/app/settings/platform-sections/xianyu.ts",
  ali1688: "apps/desktop/src/app/settings/platform-sections/ali1688.ts",
  xiaohongshu: "apps/desktop/src/app/settings/platform-sections/xiaohongshu.ts",
};

/** 平台 id → IPC 平台 barrel。 */
const IPC_PLATFORM = {
  xianyu: "packages/platform/src/ipc/platforms/xianyu.ts",
  ali1688: "packages/platform/src/ipc/platforms/ali1688.ts",
  xiaohongshu: "packages/platform/src/ipc/platforms/xiaohongshu.ts",
};

/** 平台 id → manage-nav 模块（Vite alias 路径）。 */
const MANAGE_NAV_MODULE = {
  xianyu: "@feature/platform/xianyu/manage-nav",
  ali1688: "@feature/platform/ali1688/manage-nav",
  xiaohongshu: "@feature/platform/xiaohongshu/manage-nav",
};

/** contribution / settings 导出名前缀。 */
const EXPORT_PREFIX = {
  xianyu: "xianyu",
  ali1688: "ali1688",
  xiaohongshu: "xiaohongshu",
  douyin: "douyin",
};

/**
 * @param {string} repoRoot
 * @param {string} rel
 * @returns {string}
 */
function abs(repoRoot, rel) {
  return path.join(repoRoot, rel).replaceAll("\\", "/");
}

/**
 * 路由链：双站时 1688 路由由闲鱼 Hub 接管，不 import 1688 contribution。
 *
 * @param {string[]} enabled
 * @returns {string[]}
 */
function routePlatformIds(enabled) {
  const set = new Set(enabled);
  return CHAIN_ORDER.filter((id) => {
    if (!set.has(id) || !ROUTE_CONTRIBUTION[id]) {
      return false;
    }
    if (id === "ali1688" && set.has("xianyu")) {
      return false;
    }
    return true;
  });
}

/**
 * @param {string[]} enabled
 * @returns {string[]}
 */
function ipcPlatformIds(enabled) {
  const set = new Set(enabled);
  return CHAIN_ORDER.filter((id) => set.has(id) && IPC_PLATFORM[id]);
}

/**
 * @param {string[]} enabled
 * @returns {string[]}
 */
function settingsPlatformIds(enabled) {
  const set = new Set(enabled);
  return CHAIN_ORDER.filter((id) => set.has(id) && SETTINGS_STEP[id]);
}

/**
 * @param {string[]} platformIds
 * @param {Record<string, string>} map
 * @param {string} repoRoot
 * @param {string} exportSuffix
 * @param {string} constName
 * @returns {string}
 */
function generateStepImports(platformIds, map, repoRoot, exportSuffix, constName) {
  if (platformIds.length === 0) {
    throw new Error("[dingda-platform-chain] 至少启用一个平台（见 DINGDA_CHANNEL_PLATFORMS / Cargo features）");
  }

  const imports = platformIds.map((id) => {
    const prefix = EXPORT_PREFIX[id] ?? id;
    const exportName = `${prefix}${exportSuffix}`;
    const file = abs(repoRoot, map[id]);
    return `import { ${exportName} } from ${JSON.stringify(file)};`;
  });

  const steps = platformIds.map((id) => {
    const prefix = EXPORT_PREFIX[id] ?? id;
    return `${prefix}${exportSuffix}`;
  });

  return `${imports.join("\n")}\nexport const ${constName} = [${steps.join(", ")}];`;
}

/**
 * @param {string[]} platformIds
 * @param {string} repoRoot
 * @returns {string}
 */
function generateRouteSteps(platformIds, repoRoot) {
  return generateStepImports(
    platformIds,
    ROUTE_CONTRIBUTION,
    repoRoot,
    "RouteContribution",
    "PLATFORM_ROUTE_STEPS",
  );
}

/**
 * @param {string[]} platformIds
 * @param {string} repoRoot
 * @returns {string}
 */
function generateSettingsSteps(platformIds, repoRoot) {
  return generateStepImports(
    platformIds,
    SETTINGS_STEP,
    repoRoot,
    "SettingsSections",
    "PLATFORM_SETTINGS_STEPS",
  );
}

/**
 * @param {string[]} platformIds
 * @param {string} repoRoot
 * @returns {string}
 */
function generateIpcChain(platformIds, repoRoot) {
  const shared = abs(repoRoot, "packages/platform/src/ipc/shared.ts");
  const lines = [`export * from ${JSON.stringify(shared)};`];
  for (const id of platformIds) {
    if (!IPC_PLATFORM[id]) {
      continue;
    }
    lines.push(`export * from ${JSON.stringify(abs(repoRoot, IPC_PLATFORM[id]))};`);
  }
  return lines.join("\n");
}

/**
 * @param {string[]} enabled
 * @returns {string}
 */
function generateManageNavReexport(enabled) {
  const primary =
    enabled.includes("xianyu") ? "xianyu" : enabled.find((id) => MANAGE_NAV_MODULE[id]);
  if (!primary) {
    throw new Error("[dingda-platform-chain] 无法解析 manage-nav：无已启用平台");
  }
  const moduleId = MANAGE_NAV_MODULE[primary];
  return `export { MANAGE_VIEW_TITLES, isManageView } from ${JSON.stringify(moduleId)};`;
}

/**
 * @param {string[]} enabled
 * @returns {string}
 */
function generateShellLifecyclesFixed(enabled) {
  const hasAccountPlatforms =
    enabled.includes("xianyu") ||
    enabled.includes("ali1688") ||
    enabled.includes("xiaohongshu");
  if (!hasAccountPlatforms) {
    return "export function PlatformShellLifecycles() { return null; }";
  }
  const lines = [
    'import { useAccountSessionProbeListener } from "@components/accounts/use-account-session-probe-listener";',
  ];
  if (enabled.includes("xianyu") || enabled.includes("ali1688")) {
    lines.push('import { useAccountAutoConnect } from "@components/accounts/use-auto-connect";');
  }
  lines.push("export function PlatformShellLifecycles() {");
  lines.push("  useAccountSessionProbeListener();");
  if (enabled.includes("xianyu") || enabled.includes("ali1688")) {
    lines.push("  useAccountAutoConnect();");
  }
  lines.push("  return null;");
  lines.push("}");
  return lines.join("\n");
}

/**
 * @param {{ repoRoot?: string }} [options]
 * @returns {import('vite').Plugin}
 */
export function platformChainPlugin(options = {}) {
  const repoRoot = options.repoRoot ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
  const virtualSet = new Set(Object.values(VIRTUAL));

  return {
    name: "dingda-platform-chain",
    enforce: "pre",
    resolveId(id) {
      if (virtualSet.has(id)) {
        return `\0${id}`;
      }
      return undefined;
    },
    load(id) {
      const enabled = resolveChannelPlatforms();
      const routeIds = routePlatformIds(enabled);
      const ipcIds = ipcPlatformIds(enabled);
      const settingsIds = settingsPlatformIds(enabled);

      if (id === `\0${VIRTUAL.ROUTE_STEPS}`) {
        return generateRouteSteps(routeIds, repoRoot);
      }
      if (id === `\0${VIRTUAL.IPC_CHAIN}`) {
        return generateIpcChain(ipcIds, repoRoot);
      }
      if (id === `\0${VIRTUAL.SETTINGS_STEPS}`) {
        return generateSettingsSteps(settingsIds, repoRoot);
      }
      if (id === `\0${VIRTUAL.MANAGE_NAV}`) {
        return generateManageNavReexport(enabled);
      }
      if (id === `\0${VIRTUAL.SHELL_LIFECYCLES}`) {
        return generateShellLifecyclesFixed(enabled);
      }
      return undefined;
    },
  };
}
