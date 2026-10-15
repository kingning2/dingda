/**
 * 后端 API 路径（`/v1/**`）—— 前端唯一出处。
 *
 * 职责：
 *   把散在各域 api 文件里的路径字面量收成一份；改后端路由先改这里，
 *   再同步 `packages-py/api/src/api/routes` 的路由表。
 *
 * 设计说明：
 *   - 动态段一律 `encodeURIComponent`，调用方传原始 id 即可。
 *   - 只收路径，不收 query：列表过滤走 `api.get(url, { query })`。
 */

export const apiPaths = {
  bootstrap: "/v1/bootstrap",

  accounts: "/v1/accounts",
  account: (id: string) => `/v1/accounts/${encodeURIComponent(id)}`,
  accountConnect: (id: string) => `/v1/accounts/${encodeURIComponent(id)}/connect`,
  accountDisconnect: (id: string) => `/v1/accounts/${encodeURIComponent(id)}/disconnect`,
  accountProfile: (id: string) => `/v1/accounts/${encodeURIComponent(id)}/profile`,

  channelQrStart: "/v1/channel/qr/start",
  channelQrCheck: "/v1/channel/qr/check",
  channelQrCancel: "/v1/channel/qr/cancel",

  crawlerProduct: "/v1/crawler/product",

  agentWorks: "/v1/agent/works",
  agentWork: (workId: string) => `/v1/agent/works/${encodeURIComponent(workId)}`,
  agentWorkRun: (workId: string) =>
    `/v1/agent/works/${encodeURIComponent(workId)}/run`,

  watchTargets: "/v1/watch/targets",
  watchTarget: (targetId: string) =>
    `/v1/watch/targets/${encodeURIComponent(targetId)}`,
} as const;
