const trimSlash = (value: string) => value.replace(/\/+$/, "");

export const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export const siteUrl = trimSlash(
  process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3200",
);

/** 静态资源路径，兼容本地开发与 GitHub Pages 子路径部署。 */
export const asset = (path: string) => {
  const normalized = path.replace(/^\/+/, "");
  return basePath ? `${basePath}/${normalized}` : `/${normalized}`;
};
