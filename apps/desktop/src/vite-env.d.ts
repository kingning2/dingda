/// <reference types="vite/client" />

/** 渠道平台 id（与 Rust `ChannelKind` 对齐）。 */
type ChannelPlatformId = "xianyu" | "ali1688" | "xiaohongshu" | "douyin";

/** 编译期主渠道平台 id — 由 Vite `define` 注入（见 `DINGDA_CHANNEL_PLATFORM`）。 */
declare const __DINGDA_CHANNEL_PLATFORM__: ChannelPlatformId;

/** 编译期启用的全部渠道平台 id 数组 — 由 Vite `define` 注入。 */
declare const __DINGDA_CHANNEL_PLATFORMS__: readonly ChannelPlatformId[];

/** 闲鱼是否编入本次构建 — 由 Vite `define` 注入。 */
declare const __DINGDA_HAS_XIANYU__: boolean;

/** 1688 是否编入本次构建 — 由 Vite `define` 注入。 */
declare const __DINGDA_HAS_ALI1688__: boolean;

/** 小红书是否编入本次构建 — 由 Vite `define` 注入。 */
declare const __DINGDA_HAS_XIAOHONGSHU__: boolean;

/** 编译期标题栏品牌中文名 — 由 Vite `define` 注入。 */
declare const __DINGDA_APP_BRAND_TITLE__: string;

/// <reference path="../../../tooling/types/platform-chain.d.ts" />
