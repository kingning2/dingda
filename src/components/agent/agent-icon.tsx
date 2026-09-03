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
  codebuddy: "svg",
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

export function AgentIcon({ id, size = 36, className }: AgentIconProps) {
  const cls = ["agent-icon shrink-0 text-foreground", className].filter(Boolean).join(" ");
  const assetId = ICON_ASSET_ID[id] ?? id;
  const ext = ICON_EXT[assetId];

  if (ext) {
    if (ext === "svg" && MONO_ICONS.has(assetId)) {
      const src = `/agent-icons/${assetId}.svg`;
      const style: CSSProperties = {
        width: size,
        height: size,
        WebkitMaskImage: `url("${src}")`,
        maskImage: `url("${src}")`,
      };
      return <span className={`${cls} inline-block bg-current`} style={style} aria-hidden="true" />;
    }

    return (
      <img
        src={`/agent-icons/${assetId}.${ext}`}
        alt=""
        width={size}
        height={size}
        className={cls}
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
        width: size,
        height: size,
        fontSize: Math.round(size * 0.42),
        lineHeight: 1,
      }}
      aria-hidden="true"
    >
      {initial}
    </span>
  );
}
