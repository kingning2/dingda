import { JsonLdScript } from "@/components/seo/json-ld-script";
import { FAQ_CATEGORIES } from "@/content/faq";
import { createPageMetadata } from "@/lib/seo";
import { buildFaqSchema } from "@/lib/seo/schemas";
import type { Metadata } from "next";
import Link from "next/link";
import { FaqPageClient } from "./faq-page-client";

export const metadata: Metadata = createPageMetadata({
  title: "常见问题 — 叮答怎么用、怎么选品、数据安不安全",
  description:
    "叮答 FAQ：产品能力、Agent 比价探索、下载入门、账号绑定与本地数据安全。帮商家和小白快速了解闲鱼 × 1688 选品工具。",
  path: "/faq/",
});

export default function FaqPage() {
  return (
    <>
      <JsonLdScript data={buildFaqSchema()} />
      <div className="min-h-screen bg-[#f5ede0] text-[#241d2b]">
        <header className="border-b border-[#ddcdab] bg-[#f5ede0]/90 backdrop-blur-md">
          <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
            <Link href="/" className="font-semibold">
              ← 返回首页
            </Link>
            <Link
              href="https://github.com/kingning2/dingda/releases"
              className="rounded-full bg-[#c8372a] px-4 py-2 text-sm font-medium text-white hover:bg-[#a82e23]"
            >
              下载
            </Link>
          </div>
        </header>

        <main className="mx-auto max-w-4xl px-6 py-12">
          <h1 className="text-center text-4xl font-bold">常见问题</h1>
          <p className="mx-auto mt-3 max-w-2xl text-center text-[#6a6072]">
            帮你更好地了解叮答选品工具 — Agent 探索、双边比价、本地数据与入门方式。
          </p>

          <FaqPageClient categories={FAQ_CATEGORIES} />

          <section className="mt-16 rounded-2xl border border-[#ddcdab] bg-[#efe9de] p-8 text-center">
            <h2 className="text-2xl font-bold">还需要更多帮助？</h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-[#6a6072]">
              如果这里没有解答你的问题，可以查看 GitHub 文档与 Issue，或在仓库提交反馈。我们也持续更新本页与
              llms.txt。
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-4 text-sm">
              <a
                href="https://github.com/kingning2/dingda/issues"
                className="rounded-full border border-[#c8372a] px-5 py-2 font-medium text-[#c8372a] hover:bg-[#c8372a] hover:text-white"
              >
                GitHub Issues
              </a>
              <Link
                href="/console/"
                className="rounded-full bg-[#c8372a] px-5 py-2 font-medium text-white hover:bg-[#a82e23]"
              >
                控制台演示
              </Link>
            </div>
          </section>

          <noscript>
            {FAQ_CATEGORIES.map((category) => (
              <section key={category.id} className="mt-12">
                <h2 className="mb-4 text-2xl font-bold">{category.label}</h2>
                <dl className="space-y-6">
                  {category.items.map((item) => (
                    <div key={item.id}>
                      <dt className="font-medium">{item.title}</dt>
                      <dd className="mt-2 text-sm text-[#6a6072]">{item.answer}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </noscript>
        </main>
      </div>
    </>
  );
}
