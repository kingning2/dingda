/**
 * 读取编译期渠道平台配置 — 供 Vite / Node 构建脚本复用。
 *
 * 优先级（与 Rust `tooling/build/channel_platform_cfg.rs` 对齐）：
 * 1. 环境变量 `DINGDA_CHANNEL_PLATFORMS`（逗号分隔，`1688` 视为 `ali1688`）
 * 2. 环境变量 `DINGDA_CHANNEL_PLATFORM`（单站，兼容旧用法）
 * 3. 缺省时使用 JSON 中的 `default`
 *
 * 注意：本文件为 `.mjs`（纯 JavaScript），类型仅用 JSDoc 描述，不可写 TS 语法。
 *
 * @author Xiaoman
 * @created 2026-08-18
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * @typedef {"xianyu" | "ali1688" | "xiaohongshu" | "douyin"} ChannelPlatformId
 */

/**
 * @typedef {object} ChannelPlatformEntry
 * @property {ChannelPlatformId} id
 * @property {string} name
 * @property {boolean} implemented
 */

/**
 * @typedef {object} ChannelPlatformsConfig
 * @property {string} appName
 * @property {ChannelPlatformId} default
 * @property {ChannelPlatformEntry[]} platforms
 */

const CONFIG_PATH = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../config/channel-platforms.json",
);

/** 展示顺序：闲鱼优先，其余按配置表顺序。 */
const DISPLAY_ORDER = ["xianyu", "ali1688", "xiaohongshu", "douyin"];

/**
 * 读取 `tooling/config/channel-platforms.json`。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @returns {ChannelPlatformsConfig} 解析后的配置
 */
export function readChannelPlatformsConfig() {
  const raw = fs.readFileSync(CONFIG_PATH, "utf8");
  return /** @type {ChannelPlatformsConfig} */ (JSON.parse(raw));
}

/**
 * 标准化平台标识（`1688` 视为 `ali1688`）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 *
 * @param {string} raw - 原始标识
 * @returns {string} 规范化后的标识
 */
function canonicalizeId(raw) {
  const value = raw.trim().toLowerCase();
  if (value === "1688") {
    return "ali1688";
  }
  return value;
}

/**
 * 解析逗号分隔的平台列表。
 *
 * @author Xiaoman
 * @created 2026-08-22
 *
 * @param {string} raw - 逗号分隔原始串
 * @returns {string[]} 规范化 id 列表（去空）
 */
function parseList(raw) {
  return raw
    .split(",")
    .map(canonicalizeId)
    .filter((item) => item.length > 0);
}

/**
 * 校验并去重平台列表，返回展示顺序（闲鱼优先）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 *
 * @param {string[]} ids - 待校验平台 id
 * @param {ChannelPlatformId[]} known - 全部已知平台 id
 * @returns {ChannelPlatformId[]} 去重后的平台列表
 */
function validate(ids, known) {
  const unique = new Set(ids);
  for (const id of unique) {
    if (!known.includes(/** @type {ChannelPlatformId} */ (id))) {
      throw new Error(`未知渠道平台 ${id}，可选: ${known.join(", ")}`);
    }
  }
  return DISPLAY_ORDER.filter((id) => unique.has(id));
}

/**
 * 将渠道平台环境变量写入 `env`（Vite 链 + Cargo features）。
 *
 * @param {NodeJS.ProcessEnv} env
 * @param {string} platformsArg 逗号分隔，如 `xianyu,ali1688` / `1688`
 * @returns {NodeJS.ProcessEnv}
 */
export function applyChannelPlatformEnv(env, platformsArg) {
  /** @type {import("./read-channel-platform.mjs").ChannelPlatformId[]} */
  const enabledPlatforms = resolveChannelPlatforms({
    ...env,
    DINGDA_CHANNEL_PLATFORMS: platformsArg,
  });

  /** 与 `apps/desktop/src-tauri/Cargo.toml` [features] 对齐。 */
  const cargoPlatformFeatures = new Set(["xianyu", "ali1688", "xiaohongshu"]);
  const canonicalPlatforms = enabledPlatforms.join(",");
  const cargoFeatures = enabledPlatforms
    .filter((id) => cargoPlatformFeatures.has(id))
    .join(",");

  env.DINGDA_CHANNEL_PLATFORMS = canonicalPlatforms;
  env.DINGDA_PLATFORM_CARGO_FEATURES = cargoFeatures;
  env.DINGDA_CHANNEL_PLATFORM = resolveChannelPlatform(env);
  return env;
}

/**
 * 判断 CLI 参数是否为平台选择器（非 Tauri 标志）。
 *
 * @param {string | undefined} arg
 * @returns {boolean}
 */
export function isPlatformSelector(arg) {
  if (!arg || arg.startsWith("-")) {
    return false;
  }
  try {
    resolveChannelPlatforms({ DINGDA_CHANNEL_PLATFORMS: arg });
    return true;
  } catch {
    return false;
  }
}

/**
 * 解析当前构建启用的全部渠道平台 id。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @param {NodeJS.ProcessEnv} [env] 环境变量对象，默认 `process.env`
 * @returns {ChannelPlatformId[]} 校验后的平台 id 列表（展示顺序）
 */
export function resolveChannelPlatforms(env = process.env) {
  const config = readChannelPlatformsConfig();
  const known = config.platforms.map((item) => item.id);

  if (env.DINGDA_CHANNEL_PLATFORMS) {
    return validate(parseList(env.DINGDA_CHANNEL_PLATFORMS), known);
  }
  if (env.DINGDA_CHANNEL_PLATFORM) {
    return validate([canonicalizeId(env.DINGDA_CHANNEL_PLATFORM)], known);
  }
  return validate([canonicalizeId(config.default)], known);
}

/**
 * 解析当前构建使用的主平台 id（闲鱼优先；供路由 alias / 品牌标题等单站路径使用）。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @param {NodeJS.ProcessEnv} [env] 环境变量对象，默认 `process.env`
 * @returns {ChannelPlatformId} 主平台 id
 */
export function resolveChannelPlatform(env = process.env) {
  const platforms = resolveChannelPlatforms(env);
  if (platforms.includes("xianyu")) {
    return "xianyu";
  }
  return platforms[0];
}

/**
 * 解析标题栏展示用的应用中文名称。
 *
 * 单平台构建：`{appName}（{平台名}）`（如「叮答（闲鱼）」）。
 * 聚合构建（`DINGDA_APP_VARIANT=aggregate`）或多平台构建：仅 `{appName}`。
 *
 * @author Xiaoman
 * @created 2026-08-20
 *
 * @param {NodeJS.ProcessEnv} [env] 环境变量对象，默认 `process.env`
 * @returns {string} 编译期固定的品牌标题
 */
export function resolveAppBrandTitle(env = process.env) {
  const config = readChannelPlatformsConfig();
  const baseName = config.appName ?? "叮答";

  if (env.DINGDA_APP_VARIANT === "aggregate") {
    return baseName;
  }

  const platforms = resolveChannelPlatforms(env);
  if (platforms.length > 1) {
    return baseName;
  }
  const entry = config.platforms.find((item) => item.id === platforms[0]);
  if (!entry) {
    return baseName;
  }

  return `${baseName}（${entry.name}）`;
}

/**
 * 生成 Vite `define` 用的编译期常量对象。
 *
 * 注入：
 * - `__DINGDA_CHANNEL_PLATFORM__` — 主平台 id（兼容旧单站消费者）
 * - `__DINGDA_CHANNEL_PLATFORMS__` — 启用的全部平台 id 数组
 * - `__DINGDA_HAS_<ID>__` — 各平台是否启用（`xianyu` / `ali1688`）
 * - `__DINGDA_APP_BRAND_TITLE__` — 品牌标题
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @param {NodeJS.ProcessEnv} [env] 环境变量对象，默认 `process.env`
 * @returns {Record<string, string>} 供 `defineConfig` 合并的键值
 */
export function channelPlatformDefine(env = process.env) {
  const platforms = resolveChannelPlatforms(env);
  const enabledSet = new Set(platforms);
  return {
    __DINGDA_CHANNEL_PLATFORM__: JSON.stringify(resolveChannelPlatform(env)),
    __DINGDA_CHANNEL_PLATFORMS__: JSON.stringify(platforms),
    __DINGDA_HAS_XIANYU__: JSON.stringify(enabledSet.has("xianyu")),
    __DINGDA_HAS_ALI1688__: JSON.stringify(enabledSet.has("ali1688")),
    __DINGDA_HAS_XIAOHONGSHU__: JSON.stringify(enabledSet.has("xiaohongshu")),
    __DINGDA_APP_BRAND_TITLE__: JSON.stringify(resolveAppBrandTitle(env)),
  };
}
