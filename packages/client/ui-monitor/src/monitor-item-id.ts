/**
 * 从任意用户输入里取出商品 ID。
 *
 * 职责：
 *     把「粘贴进来的东西」归一成纯商品 ID；纯函数，可单测。
 *
 * 设计说明：
 *     单独成文件而不是塞进 `monitor-add-form.tsx`：放进 `.tsx` 就得连同 React 与
 *     base-ui 一起 import，而测试跑在 node 环境（`vitest.config.ts` 的
 *     `environment: "node"`），加载组件依赖会失败 —— 纯逻辑分出来才测得了。
 *
 *     识别 `?id=` 与 `/item/` 两种形态；都匹配不上就原样返回，让后端去判错。
 *     前端不猜平台 URL 规则：猜错会静默取到另一个商品的 ID，比报错难查得多。
 */

/** 输入 → 商品 ID。空输入返回空串。 */
export function normalizeItemId(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  const byQuery = /[?&]id=([^&#\s]+)/.exec(trimmed);
  if (byQuery?.[1]) return byQuery[1];
  const byPath = /\/item\/([^/?#\s]+)/.exec(trimmed);
  if (byPath?.[1]) return byPath[1];
  return trimmed;
}
