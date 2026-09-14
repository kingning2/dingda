/**
 * 聊天块的类型词汇与渲染契约。
 *
 * 职责：
 *   定义块的数据形状（ChatBlock）、轮次（ChatTurn），以及块组件必须满足的 props 契约。
 *
 * 设计说明：
 *   - ChatBlock 是判别联合，kind 是唯一判别字段。新增块类型时，这里是唯一要扩展的联合。
 *   - 块组件只收「自己的块 + 上下文」两样东西，不认识别的块、也不认识 Chat ——
 *     这是注册表能成立的前提：块与 Chat 之间只有这一个约定。
 *   - 不在这里放 React 运行时逻辑，保持纯类型，任何模块都能安全 import。
 */

import type { ComponentType } from "react";
import type {
  AgentWorkMessageView,
  AgentWorkProductItem,
  AgentWorkStepView,
} from "@v2/contracts/ai-work";

/** 聊天记录里一个可渲染的块。 */
export type ChatBlock =
  | {
      kind: "user";
      id: string;
      messageId: string;
      content: string;
      attachments?: AgentWorkMessageView["attachments"];
    }
  | {
      kind: "thinking";
      id: string;
      text: string;
      streaming: boolean;
      startedAt?: string | null;
      durationSec?: number | null;
    }
  | {
      kind: "step";
      id: string;
      step: AgentWorkStepView;
      pageUrl: string | null;
      products: AgentWorkProductItem[];
    }
  | { kind: "text"; id: string; text: string; streaming: boolean };

/** 块类型判别值。注册表与分派都以此为准。 */
export type ChatBlockKind = ChatBlock["kind"];

/** 取某种 kind 对应的块数据。 */
export type ChatBlockOf<K extends ChatBlockKind> = Extract<ChatBlock, { kind: K }>;

/** 块渲染上下文：所有块共用的交互，与具体块无关。 */
export interface ChatRenderContext {
  /** 是否处于活回合。用户块据此决定能否编辑。 */
  busy: boolean;
  /** 当前选中的步骤 id，用于步骤块高亮。 */
  selectedStepId: string | null;
  onSelectStep?: (step: AgentWorkStepView) => void;
  /** 编辑某条用户消息：截断后从此处重新生成。 */
  onResubmitUser?: (messageId: string, content: string) => void;
}

/** 块组件的 props。所有块都收这一对。 */
export interface ChatBlockProps<K extends ChatBlockKind> {
  block: ChatBlockOf<K>;
  context: ChatRenderContext;
}

/** 块组件契约。注册表里存的就是它。 */
export type ChatBlockComponent<K extends ChatBlockKind = ChatBlockKind> = ComponentType<
  ChatBlockProps<K>
>;

/** 一轮：用户消息 + 其后全部助手块。虚拟滚动的最小单位，也是 sticky 分区的边界。 */
export interface ChatTurn {
  id: string;
  user: ChatBlockOf<"user"> | null;
  blocks: ChatBlock[];
}
