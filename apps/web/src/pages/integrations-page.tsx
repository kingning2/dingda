/**
 * 旧「集成」入口的兼容跳转。
 *
 * 职责：
 *     把历史链接送到模型配置页。
 *
 * 设计说明：
 *     原来回落到 `/agents`，但 Agent 页已随外部 CLI 对接一并删除 —— 那条路径现在是 404。
 *     这一页原本要配的「AI 后端」现在落在 `/model-config`，所以送那儿，比丢回首页有用。
 */
import { Navigate } from "react-router-dom";
import { paths } from "@v2/routes/paths";

/** @deprecated 外部 Agent CLI 集成已移除，改用 /model-config。 */
export function IntegrationsPage() {
  return <Navigate to={paths.modelConfig} replace />;
}
