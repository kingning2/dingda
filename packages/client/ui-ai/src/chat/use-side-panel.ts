/**
 * 侧边栏与分栏 resize 状态。
 *
 * 职责：
 *   - 右侧面板标签切换（results / settings）。
 *   - 聊天面板宽度拖拽调整。
 *   - 设置变更时更新 detail（换 Agent / 模型）。
 */

import { useCallback, useRef, useState } from "react";

export type SideTab = "results" | "settings";

const MIN_CHAT_WIDTH = 360;
const MAX_CHAT_WIDTH = 720;
const DEFAULT_CHAT_WIDTH = 520;

export interface SidePanelState {
  sideTab: SideTab | null;
  setSideTab: (tab: SideTab | null) => void;
  chatWidth: number;
  resizing: boolean;
  sideOpen: boolean;
  handleSideTabChange: (tab: SideTab) => void;
  handlePointerDown: (event: React.PointerEvent<HTMLDivElement>) => void;
}

export function useSidePanel(): SidePanelState {
  const [sideTab, setSideTab] = useState<SideTab | null>("results");
  const [chatWidth, setChatWidth] = useState(DEFAULT_CHAT_WIDTH);
  const [resizing, setResizing] = useState(false);
  const splitRef = useRef<HTMLDivElement>(null);
  const sideOpen = sideTab != null;

  const handleSideTabChange = useCallback((tab: SideTab) => {
    setSideTab((current) => (current === tab ? null : tab));
  }, []);

  const clampWidth = useCallback((width: number) => {
    const splitWidth = splitRef.current?.clientWidth ?? window.innerWidth;
    const max = Math.min(MAX_CHAT_WIDTH, splitWidth - 8 - 320);
    return Math.max(MIN_CHAT_WIDTH, Math.min(width, max));
  }, []);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = chatWidth;
      setResizing(true);
      const onMove = (moveEvent: globalThis.PointerEvent) => {
        setChatWidth(clampWidth(startWidth + (moveEvent.clientX - startX)));
      };
      const onUp = () => {
        setResizing(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [chatWidth, clampWidth],
  );

  return {
    sideTab,
    setSideTab,
    chatWidth,
    resizing,
    sideOpen,
    handleSideTabChange,
    handlePointerDown,
  };
}
