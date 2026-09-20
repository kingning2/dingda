/**
 * 模型供应商图标。
 *
 * 职责：
 *     按供应商 id 渲染品牌图标；没有图标的供应商回落成首字母方块。
 */

const ICONS: Record<string, string> = {
  deepseek: "/agent-icons/deepseek.svg",
  doubao: "/model-icons/doubao.svg",
  "doubao-coding": "/model-icons/doubao.svg",
};

interface ProviderIconProps {
  id: string;
  className?: string;
}

/** 渲染供应商品牌图标；未知 id 也有稳定的视觉占位。 */
export function ProviderIcon({ id, className }: ProviderIconProps) {
  const src = ICONS[id];

  if (src) {
    return (
      <img
        src={src}
        alt=""
        width={28}
        height={28}
        className={`size-7 shrink-0 rounded-md object-contain ${className ?? ""}`}
        aria-hidden="true"
        draggable={false}
      />
    );
  }

  const initial = (id.match(/[a-z]/i)?.[0] ?? "?").toUpperCase();
  return (
    <span
      className="inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-muted font-mono text-xs font-semibold text-muted-foreground"
      aria-hidden="true"
    >
      {initial}
    </span>
  );
}
