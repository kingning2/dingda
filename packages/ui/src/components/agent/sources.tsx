/**
 * Sources — 调研来源列表（对齐 web_sources 形状）。
 */

import { ExternalLink } from "../../icons";
import { cn } from "../../lib/cn";

export interface SourceItem {
  title: string;
  url: string;
  snippet?: string;
  image?: string;
}

export interface SourcesProps {
  title?: string;
  items: SourceItem[];
  emptyText?: string;
  className?: string;
}

export function Sources({
  title = "来源",
  items,
  emptyText = "暂无来源",
  className,
}: SourcesProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-xl)] border border-border/70 bg-card p-4 shadow-sm",
        className,
      )}
    >
      <h3 className="mb-3 font-medium text-foreground">{title}</h3>
      {items.length === 0 ? (
        <p className="text-[length:var(--text-sm)] text-muted-foreground">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li
              key={item.url || item.title}
              className="rounded-[var(--radius-md)] border border-border/50 bg-background/60 p-2.5"
            >
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="group flex items-start gap-2"
              >
                {item.image ? (
                  <img
                    src={item.image}
                    alt=""
                    className="mt-0.5 size-10 shrink-0 rounded object-cover"
                  />
                ) : null}
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-1 truncate text-[length:var(--text-sm)] font-medium text-foreground group-hover:underline">
                    <span className="truncate">{item.title || item.url}</span>
                    <ExternalLink className="size-3 shrink-0 opacity-50" aria-hidden />
                  </p>
                  {item.snippet ? (
                    <p className="mt-0.5 line-clamp-2 text-[length:var(--text-xs)] text-muted-foreground">
                      {item.snippet}
                    </p>
                  ) : null}
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
