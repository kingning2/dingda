/**
 * AI 工作区：聊天面板 + 分栏 Layout + 块注册表。
 *
 * 加一个聊天块不需要改本文件 —— 见 `src/blocks/index.ts`（装配点）与
 * `src/chat/README.md`（四步说明）。
 */

export { Layout, View, AiWorkView } from "./layout";
export type { SideTab } from "./chat/use-side-panel";

export { Chat } from "./chat/chat";
export type { ChatProps } from "./chat/chat";
export type {
  ChatBlock,
  ChatBlockComponent,
  ChatBlockProps,
  ChatRenderContext,
  ChatTurn,
} from "./chat/types";
export { ComposerFooter } from "./chat/composer-footer";

export { send } from "./work/send";
export type { SendHandle, SendUpdate } from "./work/send";

export { Collapse } from "./blocks/collapse";
export { CodexActivityIndicator, ThinkingOrb } from "./blocks/thinking-orb";

export { Products } from "./panel/products";
export { ComparisonResults } from "./panel/comparison-results";
export { SelectionResults } from "./panel/selection-results";
export { Settings } from "./panel/settings";

export {
  stashWorkDraft,
  stashWorkSnapshot,
  clearWorkDraft,
  loadAgentWorkDetail,
  buildEmptyWorkDetail,
} from "./work/session";

export { MarkdownRenderer, MarkdownCode, MarkdownLink } from "./markdown";
