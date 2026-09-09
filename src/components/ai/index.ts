/**
 * AI 工作区：Layout + 调度器 + Collapse 块（对齐 OpenDesign 流式观感）。
 */

export { Layout, View, AiWorkView } from "./layout";
export type { SideTab } from "./layout";

export { ChatPane, send, scheduleDetail, scheduleMessage } from "./scheduler";
export type { SendHandle, ScheduledBlock, ChatPaneProps } from "./scheduler";

export { Collapse } from "./Collapse";
export { ThinkingOrb } from "./ThinkingOrb";
export { UserBlock, ThinkingBlock, TextBlock, StepBlock } from "./blocks";

export { Products } from "./Products";
export { Settings } from "./Settings";

export {
  stashWorkDraft,
  stashWorkPrompt,
  stashWorkSnapshot,
  clearWorkDraft,
  loadAgentWorkDetail,
  buildEmptyWorkDetail,
} from "./session";

export { MarkdownRenderer, MarkdownCode, MarkdownLink } from "./markdown";

export {
  MOCK_XHS_PRODUCTS,
  MOCK_XIANYU_PRODUCTS,
  buildMockWorkDetail,
} from "./mockData";
