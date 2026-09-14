/**
 * Agent 鉴权视图与辅助判定。
 *
 * 职责：
 *   - `buildAuthView`：根据探针结果组装统一鉴权视图。
 *   - `getAgentGuideUrl`：取接入文档地址（回退安装地址）。
 *   - `supportsAgentLogin`：判断是否支持平台内登录。
 */

import type {
  AgentRuntimeAuthView,
  AgentRuntimeItem,
} from "@v2/contracts/agent-runtime";

/** 取该 Agent 的接入文档地址；没有文档时退回安装地址，都没有则返回 null。 */
export function getAgentGuideUrl(agent: AgentRuntimeItem): string | null {
  const docs = agent.docs_url?.trim();
  const install = agent.install_url?.trim();
  return docs || install || null;
}

/** 该 Agent 是否支持从平台内拉起登录；决定卡片是否显示「登录」按钮。 */
export function supportsAgentLogin(agent: AgentRuntimeItem): boolean {
  return Boolean(agent.can_login);
}

/** 根据探针鉴权结果组装统一鉴权视图（登录按钮 / 文档配置 API 共用）。 */
export function buildAuthView(
  agent: Pick<AgentRuntimeItem, "name" | "can_login">,
  authenticated: boolean | null,
): AgentRuntimeAuthView | null {
  const canLogin = Boolean(agent.can_login);
  if (authenticated === true) {
    return {
      state: "authenticated",
      label: "已登录",
      can_login: false,
    };
  }
  if (authenticated === false) {
    return {
      state: "unauthenticated",
      label: canLogin ? "未登录" : "未配置",
      can_login: canLogin,
      hint: canLogin
        ? `点击「登录」完成 ${agent.name} 授权`
        : "请在终端登录或配置 API Key，完成后点「扫描 Agent」",
    };
  }
  if (!canLogin) return null;
  return {
    state: "unknown",
    label: "未检测",
    can_login: canLogin,
    hint: "点击「扫描 Agent」查看登录状态",
  };
}
