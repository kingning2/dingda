/** Agent 状态判断（无 UI 动画）。 */
export function isAgentRunningState(state: string): boolean {
  return state === "running" || state === "browsing";
}
