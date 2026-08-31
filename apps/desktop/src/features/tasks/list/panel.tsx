/**
 * 左侧会话历史 — 固定栏，按日期分组。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Input } from "@desk/ui";
import { MessageSquarePlus, Search } from "@desk/ui/icons";
import { agentRunList, type AgentRunRecord } from "@desk/platform/ipc/agent-run";
import { useWorkspaceNav } from "../../../app/use-workspace-tabs";
import { formatRunTime, progressLabel, stateLabel } from "../price-compare";
import { historyStyles as s } from "./styles";

export interface HistoryPanelProps {
  activeTaskId?: string;
  onNewChat: () => void;
}

function startOfDay(ms: number): number {
  const date = new Date(ms);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function groupRuns(runs: AgentRunRecord[]): { label: string; items: AgentRunRecord[] }[] {
  const today = startOfDay(Date.now());
  const yesterday = today - 86_400_000;
  const buckets = new Map<string, AgentRunRecord[]>([
    ["今天", []],
    ["昨天", []],
    ["更早", []],
  ]);

  for (const run of runs) {
    const updated = run.updatedAt;
    if (updated >= today) {
      buckets.get("今天")!.push(run);
    } else if (updated >= yesterday) {
      buckets.get("昨天")!.push(run);
    } else {
      buckets.get("更早")!.push(run);
    }
  }

  return [...buckets.entries()]
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

export function HistoryPanel({ activeTaskId, onNewChat }: HistoryPanelProps) {
  const { selectTab } = useWorkspaceNav();
  const [filter, setFilter] = useState("");
  const [runs, setRuns] = useState<AgentRunRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const list = await agentRunList();
      setRuns([...list].sort((a, b) => b.updatedAt - a.updatedAt));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const filtered = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) {
      return runs;
    }
    return runs.filter((run) => run.user.toLowerCase().includes(query));
  }, [filter, runs]);

  const groups = useMemo(() => groupRuns(filtered), [filtered]);

  return (
    <aside style={s.aside}>
      <div style={s.header}>
        <p style={s.brand}>任务副驾</p>
        <Button type="button" size="sm" variant="outline" onClick={onNewChat}>
          <MessageSquarePlus className="size-3.5" aria-hidden />
          新对话
        </Button>
      </div>

      <div style={s.searchWrap}>
        <Search className="size-3.5" style={s.searchIcon} aria-hidden />
        <Input
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="搜索历史会话…"
          className="h-8 pl-8 text-[length:var(--text-xs)]"
        />
      </div>

      <div style={s.list}>
        {loading ? (
          <p style={s.empty}>加载中…</p>
        ) : groups.length === 0 ? (
          <p style={s.empty}>暂无历史会话</p>
        ) : (
          groups.map((group) => (
            <div key={group.label} style={s.group}>
              <p style={s.groupLabel}>{group.label}</p>
              <ul style={s.groupList}>
                {group.items.map((run) => {
                  const active = run.id === activeTaskId;
                  return (
                    <li key={run.id}>
                      <button
                        type="button"
                        style={s.item(active)}
                        onClick={() => selectTab(`/tasks/${run.id}`)}
                      >
                        <p style={s.itemTitle}>{run.user || "未命名任务"}</p>
                        <p style={s.itemMeta}>
                          {stateLabel(run.state)} · {progressLabel(run)}
                        </p>
                        <p style={s.itemTime}>{formatRunTime(run.updatedAt)}</p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
