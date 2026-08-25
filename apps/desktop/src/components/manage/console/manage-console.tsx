/**
 * 管理子页出口 — 共享路由骨架：静态 URL → 业务页。
 *
 * 平台差异（VIEW_PAGES、回退 view、深链解析）由 `ManageConsoleConfig` 注入。
 */
import { type ComponentType, type ReactElement } from "react";
import { useLocation } from "react-router";
import { CHANNEL_MANAGE_ROOT } from "@desk/platform/compile";

/** 管理子页出口配置（`V` = 平台自己的 ManageView 并集）。 */
export interface ManageConsoleConfig<V extends string> {
  /** 根路径 / 非法片段时回退的 view。 */
  fallback: V;
  /** view → 页面组件映射。 */
  viewPages: Partial<Record<V, ComponentType>>;
  /** 校验 URL 片段是否为本平台合法 view。 */
  isView: (value: string) => value is V;
  /** 深链解析：命中则返回要直接渲染的元素，否则 `null`。 */
  deepLinks?: Array<(pathname: string) => ReactElement | null>;
}

/** 从静态路径解析管理子页 key。 */
export function viewFromPathname<V extends string>(
  pathname: string,
  config: ManageConsoleConfig<V>,
): V {
  if (pathname === CHANNEL_MANAGE_ROOT) {
    return config.fallback;
  }
  const prefix = `${CHANNEL_MANAGE_ROOT}/`;
  if (!pathname.startsWith(prefix)) {
    return config.fallback;
  }
  const segment = pathname.slice(prefix.length).split("/")[0] ?? "";
  return config.isView(segment) ? segment : config.fallback;
}

/** 管理子页出口（静态 URL → 业务页）。 */
export function ManageConsole<V extends string>({ config }: { config: ManageConsoleConfig<V> }) {
  const { pathname } = useLocation();

  for (const resolve of config.deepLinks ?? []) {
    const element = resolve(pathname);
    if (element) return element;
  }

  const view = viewFromPathname(pathname, config);
  const Page = (config.viewPages[view] ?? config.viewPages[config.fallback]) as
    | ComponentType
    | undefined;
  return Page ? <Page /> : null;
}
