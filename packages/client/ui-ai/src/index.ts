/**
 * AI 工作区：聊天面板 + 分栏 Layout + 块注册表。
 *
 * 加一个聊天块不需要改本文件 —— 见 `src/blocks/index.ts`（装配点）与
 * `src/chat/README.md`（四步说明）。
 */

export { Layout, View, AiWorkView } from "./layout";
export type { SideTab } from "./layout";

export { Chat } from "./chat/chat";
export type { ChatProps } from "./chat/chat";
export type {
  ChatBlock,
  ChatBlockComponent,
  ChatBlockProps,
  ChatRenderContext,
  ChatTurn,
} from "./chat/types";
export { ComposerFooter } from "./composer-footer";

export { send } from "./send";
export type { SendHandle, SendUpdate } from "./send";

export { Collapse } from "./Collapse";
export { CodexActivityIndicator, ThinkingOrb } from "./ThinkingOrb";

export { Products } from "./Products";
export { ComparisonResults } from "./ComparisonResults";
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
