/**
 * 旧「资产」入口的兼容跳转。
 *
 * 职责：
 *     把历史链接按 `tab` 参数分流到账号页，其余一律回首页。
 *
 * 设计说明：
 *     原来回落到 `/agents`，但 Agent 页已随外部 CLI 对接一并删除 —— 那条路径现在是 404。
 *     `/assets` 这条旧链接保留，只是为了让老书签不报错。
 */
import { Navigate, useSearchParams } from "react-router-dom";
import { paths } from "@v2/routes/paths";

/** @deprecated 资产页已拆成账号页与模型配置页。 */
export function AssetsPage() {
  const [searchParams] = useSearchParams();
  const tab = searchParams.get("tab");
  if (tab === "accounts") {
    return <Navigate to={paths.accounts} replace />;
  }
  return <Navigate to={paths.home} replace />;
}
