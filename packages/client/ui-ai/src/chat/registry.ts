/**
 * 聊天块注册表。
 *
 * 职责：
 *   维护「块类型 → 块组件」的映射，让 Chat 不必认识任何具体块。
 *
 * 设计说明：
 *   - 每个块文件在模块顶层调用一次 `registerBlock`。注册发生在**模块加载时**，
 *     所以必须有人在 `blocks/index.ts` 做副作用导入，否则块文件不被加载、注册语句不执行。
 *   - 重复注册直接抛错。静默覆盖会让「哪个块生效」变成模块加载顺序问题 ——
 *     这种 bug 只在打包顺序变化时才现形，极难定位。
 *   - `resolveBlock` 返回 null 而不抛错：由渲染方给**可见占位**。
 *     若在这里抛错，一个漏注册的块会炸掉整条聊天记录；若静默跳过，
 *     表现为「消息凭空少了一段」，同样难查。可见占位两头都避开了。
 */

import type { ChatBlockComponent, ChatBlockKind } from "./types";

/**
 * 注册表的内部存储类型。
 *
 * TS 无法表达「Map 的 key 与 value 泛型相关联」，所以这里把 kind 擦掉。
 * 安全性由使用方式保证：写入时的 kind 就是读回时用的 kind，
 * 且块组件的 props 只依赖自己的 kind（见 ChatBlockProps）。
 */
type StoredBlock = ChatBlockComponent;

const REGISTRY = new Map<ChatBlockKind, StoredBlock>();

/** 注册一个聊天块。每个块文件调用一次，传入自己的 kind 与组件。 */
export function registerBlock<K extends ChatBlockKind>(
  kind: K,
  component: ChatBlockComponent<K>,
): void {
  if (REGISTRY.has(kind)) {
    throw new Error(`聊天块 "${kind}" 已注册，不能重复注册`);
  }
  REGISTRY.set(kind, component as unknown as StoredBlock);
}

/** 取某个 kind 的块组件；未注册时返回 null。 */
export function resolveBlock(kind: ChatBlockKind): StoredBlock | null {
  return REGISTRY.get(kind) ?? null;
}
