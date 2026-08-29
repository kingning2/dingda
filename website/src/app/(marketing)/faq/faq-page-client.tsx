"use client";

import { FaqAccordion } from "@/components/marketing/faq-accordion";
import type { FaqCategory, FaqCategoryId } from "@/content/faq";
import { useState } from "react";

type FaqPageClientProps = {
  categories: FaqCategory[];
};

export function FaqPageClient({ categories }: FaqPageClientProps) {
  const [active, setActive] = useState<FaqCategoryId>(categories[0]?.id ?? "product");
  const current = categories.find((c) => c.id === active) ?? categories[0];

  return (
    <>
      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        {categories.map((category) => {
          const selected = category.id === active;
          return (
            <button
              key={category.id}
              type="button"
              onClick={() => setActive(category.id)}
              className={`relative rounded-xl border bg-[#f0e7cd] p-5 text-left shadow-sm transition ${
                selected
                  ? "border-[#c8372a] ring-2 ring-[#c8372a]/20"
                  : "border-[#ddcdab] hover:border-[#c8372a]/50"
              }`}
            >
              {selected ? (
                <span className="absolute inset-x-4 top-0 h-0.5 rounded-full bg-[#c8372a]" />
              ) : null}
              <span className="flex size-10 items-center justify-center rounded-lg bg-[#c8372a] text-lg font-bold text-white">
                {category.seal}
              </span>
              <p className={`mt-3 font-semibold ${selected ? "text-[#241d2b]" : "text-[#6a6072]"}`}>
                {category.label}
              </p>
              <p className="mt-1 text-xs text-[#6a6072]">{category.subtitle}</p>
            </button>
          );
        })}
      </div>

      {current ? (
        <section className="mt-10">
          <h2 className="sr-only">{current.label}</h2>
          <FaqAccordion items={current.items} />
        </section>
      ) : null}
    </>
  );
}
