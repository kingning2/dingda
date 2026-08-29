"use client";

import Link from "next/link";
import type { FaqItem } from "@/content/faq";
import { useState } from "react";

type FaqAccordionProps = {
  items: FaqItem[];
  /** 是否显示 Q1 / Q2 编号（SpyX 风格） */
  numbered?: boolean;
};

export function FaqAccordion({ items, numbered = true }: FaqAccordionProps) {
  const [openId, setOpenId] = useState<string | null>(items[0]?.id ?? null);

  return (
    <div className="divide-y divide-[#ddcdab] border-y border-[#ddcdab]">
      {items.map((item, index) => {
        const open = openId === item.id;
        return (
          <div key={item.id} className="py-1">
            <button
              type="button"
              className="flex w-full cursor-pointer items-start justify-between gap-4 py-4 text-left"
              aria-expanded={open}
              onClick={() => setOpenId(open ? null : item.id)}
            >
              <span className="flex items-start gap-3">
                {numbered ? (
                  <span className="mt-0.5 shrink-0 text-sm font-semibold text-[#c8372a]">
                    Q{index + 1}
                  </span>
                ) : null}
                <span className="font-medium text-[#241d2b]">{item.title}</span>
              </span>
              <span
                className={`mt-1 shrink-0 text-[#c8372a] transition-transform ${open ? "rotate-45" : ""}`}
                aria-hidden
              >
                +
              </span>
            </button>
            {open ? (
              <div className="pb-4 pl-0 text-sm leading-7 text-[#6a6072] sm:pl-8">
                {item.paragraphs.map((paragraph) => (
                  <p key={paragraph} className="mb-3 last:mb-0">
                    {paragraph}
                  </p>
                ))}
                {item.links?.length ? (
                  <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
                    {item.links.map((link) =>
                      link.href.startsWith("http") ? (
                        <a
                          key={link.href}
                          href={link.href}
                          className="font-medium text-[#c8372a] hover:underline"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {link.label} →
                        </a>
                      ) : (
                        <Link
                          key={link.href}
                          href={link.href}
                          className="font-medium text-[#c8372a] hover:underline"
                        >
                          {link.label} →
                        </Link>
                      ),
                    )}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
