/**
 * 流式文本 — 仅在任务执行中随内容追加展示；展开/回看时直接显示全文。
 */

import { chatStyles as s } from "./styles";

export function ProgressiveText({
  text,
  streaming = false,
}: {
  text: string;
  streaming?: boolean;
}) {
  if (!text && streaming) {
    return <span style={s.thinking}>深入分析中…</span>;
  }

  return (
    <span style={{ whiteSpace: "pre-wrap" }}>
      {text}
      {streaming ? <span style={s.cursor} aria-hidden /> : null}
    </span>
  );
}
