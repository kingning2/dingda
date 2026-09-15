/**
 * 商品监控 HTTP API。
 *
 * 职责：
 *     把 `/v1/watch` 的端点包成类型化函数；只发请求与解包，不管状态也不弹提示。
 *
 * 设计说明：
 *     - 统一走 `@v2/runtime/http-client`，不自建 fetch。
 *     - `skipErrorToast: true`：提示交给调用方。加入监控成功/失败由调用点统一弹一条
 *       alert，若这里也弹就会同一件事提示两次。
 *     - 加入监控走批量端点（后端 `POST /v1/watch/targets` 本身就是批量的，且
 *       同 platform + item_id 幂等），调用方即使只加一条也走同一个函数。
 */

import type {
  MonitorAddRequest,
  MonitorAddResponse,
  MonitorDeleteResponse,
  MonitorDetailResponse,
  MonitorListResponse,
  MonitorPatchRequest,
} from "@v2/contracts/monitor";
import { api } from "@v2/runtime/http-client";

/** 列出监控目标。`state` 不传则返回全部。 */
export async function listMonitorTargets(options?: {
  state?: string;
  signal?: AbortSignal;
}): Promise<MonitorListResponse> {
  const { data } = await api.get<MonitorListResponse>("/v1/watch/targets", {
    query: { state: options?.state },
    signal: options?.signal,
    fallbackError: "读取监控列表失败",
    skipErrorToast: true,
  });
  return data;
}

/** 加入监控；同 (platform, item_id) 已存在则复用原行，不重置已有价格历史。 */
export async function addMonitorTargets(
  request: MonitorAddRequest,
  options?: { signal?: AbortSignal },
): Promise<MonitorAddResponse> {
  const { data } = await api.post<MonitorAddResponse>("/v1/watch/targets", request, {
    signal: options?.signal,
    timeoutMs: 30_000,
    fallbackError: "加入监控失败",
    skipErrorToast: true,
  });
  return data;
}

/** 单条监控详情：当前快照 + 价格历史点 + 变更事件。 */
export async function getMonitorTarget(
  targetId: string,
  options?: { signal?: AbortSignal },
): Promise<MonitorDetailResponse> {
  const { data } = await api.get<MonitorDetailResponse>(
    `/v1/watch/targets/${encodeURIComponent(targetId)}`,
    {
      signal: options?.signal,
      fallbackError: "读取监控详情失败",
      skipErrorToast: true,
    },
  );
  return data;
}

/** 调整监控状态（暂停/恢复/归档）或轮询间隔。 */
export async function patchMonitorTarget(
  targetId: string,
  request: MonitorPatchRequest,
  options?: { signal?: AbortSignal },
): Promise<MonitorDetailResponse> {
  const { data } = await api.patch<MonitorDetailResponse>(
    `/v1/watch/targets/${encodeURIComponent(targetId)}`,
    request,
    {
      signal: options?.signal,
      fallbackError: "调整监控失败",
      skipErrorToast: true,
    },
  );
  return data;
}

/** 彻底移除监控（连带清掉价格历史）。想保留历史请改用 PATCH 归档。 */
export async function removeMonitorTarget(
  targetId: string,
  options?: { signal?: AbortSignal },
): Promise<MonitorDeleteResponse> {
  const { data } = await api.delete<MonitorDeleteResponse>(
    `/v1/watch/targets/${encodeURIComponent(targetId)}`,
    {
      signal: options?.signal,
      fallbackError: "移除监控失败",
      skipErrorToast: true,
    },
  );
  return data;
}
