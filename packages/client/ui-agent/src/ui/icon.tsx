/**
 * Agent 图标。
 *
 * 职责：
 *   按 Agent id 渲染图标：优先取 /agent-icons/ 下的 svg / png；表里没有的 id 回落成首字母方块。
 *
 * 设计说明：
 *   - MONO_ICONS 里的单色图标走 CSS mask 跟随文字色，否则深色主题下会看不清
 *   - 内联宽高是为了盖过 Tailwind preflight 的 `img { height:auto; max-width:100% }`，
 *     不写会被裁切 / 挤压
 */

import type { CSSProperties } from "react";

interface AgentIconProps {
  id: string;
  size?: number;
  className?: string;
}

const ICON_EXT: Record<string, "svg" | "png"> = {
  claude: "svg",
  codex: "svg",
  opencode: "svg",
  "cursor-agent": "svg",
  qwen: "svg",
  qoder: "svg",
  deepseek: "svg",
  mimo: "svg",
  "grok-build": "svg",
  pi: "svg",
  "trae-cli": "png",
};

const ICON_ASSET_ID: Record<string, string> = {
  "deepseek-harness": "deepseek",
};

const MONO_ICONS = new Set([
  "cursor-agent",
  "opencode",
  "mimo",
  "grok-build",
]);

/**
 * 渲染一个 Agent 的图标。
 *
 * 三种回落：单色图标走 mask 跟随文字色 → 普通 svg/png 直接渲染 → 都没命中则出首字母方块。
 * 永远不抛错，未知 id 也有一张图，调用方不用做存在性判断。
 */
export function AgentIcon({ id, size = 36, className }: AgentIconProps) {
  const cls = ["agent-icon shrink-0 text-foreground", className].filter(Boolean).join(" ");
  const assetId = ICON_ASSET_ID[id] ?? id;
  const ext = ICON_EXT[assetId];
  // 内联宽高盖过 Tailwind preflight 的 `img { height:auto; max-width:100% }`，避免裁切/挤压
  const boxStyle: CSSProperties = { width: size, height: size };

  if (ext) {
    if (ext === "svg" && MONO_ICONS.has(assetId)) {
      const src = `/agent-icons/${assetId}.svg`;
      const style: CSSProperties = {
        ...boxStyle,
        WebkitMaskImage: `url("${src}")`,
        maskImage: `url("${src}")`,
        WebkitMaskSize: "contain",
        maskSize: "contain",
        WebkitMaskRepeat: "no-repeat",
        maskRepeat: "no-repeat",
        WebkitMaskPosition: "center",
        maskPosition: "center",
      };
      return <span className={`${cls} inline-block bg-current`} style={style} aria-hidden="true" />;
    }

    return (
      <img
        src={`/agent-icons/${assetId}.${ext}`}
        alt=""
        width={size}
        height={size}
        className={`${cls} max-w-none object-contain`}
        style={boxStyle}
        aria-hidden="true"
        draggable={false}
      />
    );
  }

  const initial = (id.match(/[a-z]/i)?.[0] ?? "?").toUpperCase();
  return (
    <span
      className={`${cls} inline-flex items-center justify-center rounded-md bg-muted font-mono font-semibold text-muted-foreground`}
      style={{
        ...boxStyle,
        fontSize: Math.round(size * 0.42),
        lineHeight: 1,
      }}
      aria-hidden="true"
    >
      {initial}
    </span>
  );
}
