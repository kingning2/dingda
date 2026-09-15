/**
 * 商品监控页装配：左列表 + 右详情。
 *
 * 职责：
 *     拉监控列表、维护选中项、把「加入/暂停/移除」转成 API 调用并刷新数据。
 *
 * 设计说明：
 *     - 不引入全局 store：监控页的数据是单页的。跨页共享的只有「加入监控」这一个动作，
 *       它由 `monitor-api` 直接暴露给 Agent 选品结果调用，不需要状态中转。
 *     - 页面**不做轮询**：后台调度器每 6 小时才写一次库，前端跟着轮询只是白打后端。
 *       数据只在挂载与操作后刷新。
 *     - 切换选中项时先清空 detail：留着上一条的数据会让右侧短暂显示「另一个商品的价格」，
 *       这种错配比空白更难发现。
 */

import type {
  MonitorDetailResponse,
  MonitorPatchRequest,
  MonitorTargetItem,
} from "@v2/contracts/monitor";
import { pushAppAlert } from "@v2/runtime/app-alert";
import { useCallback, useEffect, useState } from "react";

import { MonitorAddForm } from "./monitor-add-form";
import {
  getMonitorTarget,
  listMonitorTargets,
  patchMonitorTarget,
  removeMonitorTarget,
} from "./monitor-api";
import { MonitorDetail } from "./monitor-detail";
import { MonitorList } from "./monitor-list";

/** 商品监控页。 */
export function MonitorHub() {
  const [targets, setTargets] = useState<MonitorTargetItem[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MonitorDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const refresh = useCallback(async () => {
    setListLoading(true);
    try {
      const response = await listMonitorTargets();
      setTargets(response.targets);
      setError(null);
      // 选中的目标可能已被移除：回落到第一条，避免右侧停在一条不存在的目标上。
      setSelectedId((prev) => {
        if (prev && response.targets.some((item) => item.target_id === prev)) return prev;
        return response.targets[0]?.target_id ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取监控列表失败");
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setDetail(null);
    setDetailLoading(true);
    void (async () => {
      try {
        const response = await getMonitorTarget(selectedId, { signal: controller.signal });
        if (!controller.signal.aborted) setDetail(response);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "读取监控详情失败");
        }
      } finally {
        if (!controller.signal.aborted) setDetailLoading(false);
      }
    })();
    return () => controller.abort();
  }, [selectedId]);

  const handlePatch = useCallback(
    async (targetId: string, request: MonitorPatchRequest) => {
      try {
        const response = await patchMonitorTarget(targetId, request);
        setDetail(response);
        await refresh();
      } catch (err) {
        pushAppAlert({
          title: "调整监控失败",
          description: err instanceof Error ? err.message : "请稍后重试",
          variant: "destructive",
        });
      }
    },
    [refresh],
  );

  const handleRemove = useCallback(
    async (targetId: string) => {
      try {
        await removeMonitorTarget(targetId);
        pushAppAlert({ title: "已移除监控", description: "该商品的价格历史一并清掉了。" });
        setSelectedId(null);
        setDetail(null);
        await refresh();
      } catch (err) {
        pushAppAlert({
          title: "移除监控失败",
          description: err instanceof Error ? err.message : "请稍后重试",
          variant: "destructive",
        });
      }
    },
    [refresh],
  );

  // 一次渲染内固定基准时间：同屏几条「3 分钟前」才读得一致。
  // 除以 1000 转秒 —— 后端的 observed_at / last_poll_at 都是 Unix 秒。
  const now = Date.now() / 1000;

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          监控哪些商品由你自己挑：从 Agent 选品结果一键加入，或在这里填平台与商品 ID。
          后台每 6 小时轮询一次，降价、售出、下架会记进变更记录。
        </p>
        <MonitorAddForm onAdded={() => void refresh()} />
      </header>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <MonitorList
          targets={targets}
          selectedId={selectedId}
          loading={listLoading}
          onSelect={setSelectedId}
        />
        <MonitorDetail
          detail={detail}
          loading={detailLoading}
          now={now}
          onPatch={(targetId, request) => void handlePatch(targetId, request)}
          onRemove={(targetId) => void handleRemove(targetId)}
        />
      </div>
    </div>
  );
}
