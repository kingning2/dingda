import Link from "next/link";
import {
  AGENT_PIPELINE,
  FEATURE_GROUPS,
  HOME_FAQ_ITEMS,
  PRODUCT_POSITIONING,
  WORKFLOW_STEPS,
} from "@/content/landing";
import { FaqAccordion } from "@/components/marketing/faq-accordion";
import { asset } from "@/lib/site";
import PromoPlayer, { DingDaLogo } from "./promo-player";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#f5ede0] text-[#241d2b]">
      <header className="sticky top-0 z-50 border-b border-[#ddcdab] bg-[#f5ede0]/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5 font-semibold">
            <DingDaLogo size={30} />
            <span>叮答</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm text-[#6a6072]">
            <a href="#how" className="hover:text-[#241d2b]">
              怎么工作
            </a>
            <a href="#features" className="hover:text-[#241d2b]">
              功能
            </a>
            <a href="#faq" className="hover:text-[#241d2b]">
              常见问题
            </a>
            <Link href="/faq" className="hover:text-[#241d2b]">
              全部 FAQ
            </Link>
            <Link
              href="/console"
              className="rounded-full border border-[#c8372a] px-4 py-2 font-medium text-[#c8372a] hover:bg-[#c8372a] hover:text-white"
            >
              控制台演示
            </Link>
            <a
              href="https://github.com/kingning2/dingda/releases"
              className="rounded-full bg-[#c8372a] px-4 py-2 font-medium text-white hover:bg-[#a82e23]"
            >
              下载
            </a>
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-6 py-16 text-center" aria-labelledby="hero-heading">
          <p className="mb-4 text-xs font-semibold tracking-[0.2em] text-[#c8372a] uppercase">
            闲鱼 × 1688 选品 · Agent 探索比价
          </p>
          <h1 id="hero-heading" className="mb-4 text-4xl font-bold tracking-tight md:text-5xl">
            {PRODUCT_POSITIONING.tagline}
          </h1>
          <p className="mx-auto mb-10 max-w-2xl text-[#6a6072]">
            {PRODUCT_POSITIONING.subtitle}
          </p>
          <PromoPlayer />
        </section>

        <section id="how" className="border-y border-[#ddcdab] bg-[#efe9de] py-16" aria-labelledby="how-heading">
          <div className="mx-auto max-w-6xl px-6">
            <h2 id="how-heading" className="mb-2 text-3xl font-bold">Agent + 爬虫，怎么帮你找货？</h2>
            <p className="mb-10 text-[#6a6072]">
              不是查价器，而是一条自动探索流水线——从「最近什么火」到「有没有利润」。
            </p>
            <ol className="grid gap-4 md:grid-cols-4">
              {AGENT_PIPELINE.map((item, index) => (
                <li
                  key={item.step}
                  className="rounded-xl border border-[#ddcdab] bg-[#f0e7cd] p-5"
                >
                  <span className="text-xs font-semibold tracking-widest text-[#c8372a]">
                    0{index + 1}
                  </span>
                  <h3 className="mt-2 text-lg font-semibold">{item.step}</h3>
                  <p className="mt-2 text-sm text-[#6a6072]">{item.desc}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="py-16">
          <div className="mx-auto max-w-6xl px-6">
            <h2 className="mb-8 text-center text-3xl font-bold">四步上手</h2>
            <div className="grid gap-4 md:grid-cols-4">
              {WORKFLOW_STEPS.map((step, index) => (
                <div key={step.title} className="text-center">
                  <span className="inline-flex size-10 items-center justify-center rounded-full bg-[#c8372a] text-sm font-bold text-white">
                    {index + 1}
                  </span>
                  <h3 className="mt-3 font-semibold">{step.title}</h3>
                  <p className="mt-1 text-sm text-[#6a6072]">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="features" className="bg-[#efe9de] py-16" aria-labelledby="features-heading">
          <div className="mx-auto max-w-6xl px-6">
            <h2 id="features-heading" className="mb-2 text-3xl font-bold">商家和小白，都能用同一套工具</h2>
            <p className="mb-10 text-[#6a6072]">
              已经在卖的，用它盯热门、扩品类；刚入门的，用它找第一批发力点。
            </p>
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {FEATURE_GROUPS.map((group) => (
                <article
                  key={group.title}
                  className="rounded-xl border border-[#ddcdab] bg-[#f0e7cd] p-5"
                >
                  <div className="mb-3 flex items-center gap-3">
                    <span className="grid size-10 place-items-center rounded-lg bg-[#c8372a] text-lg font-bold text-white">
                      {group.seal}
                    </span>
                    <h3 className="text-lg font-semibold">{group.title}</h3>
                  </div>
                  <p className="text-sm leading-7 text-[#6a6072]">{group.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="py-16" aria-labelledby="faq-heading">
          <div className="mx-auto max-w-3xl px-6">
            <h2 id="faq-heading" className="mb-2 text-3xl font-bold">
              你可能想问
            </h2>
            <p className="mb-8 text-sm text-[#6a6072]">
              精选常见问题，更多请查看
              <Link href="/faq" className="ml-1 font-medium text-[#c8372a] hover:underline">
                完整 FAQ 页
              </Link>
              。
            </p>
            <FaqAccordion items={HOME_FAQ_ITEMS} />
          </div>
        </section>
      </main>

      <footer className="border-t border-[#ddcdab] bg-[#e9d9b6] py-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 md:flex-row md:items-start md:justify-between">
          <div className="flex gap-3">
            <DingDaLogo size={36} />
            <div>
              <p className="font-semibold">叮答 DingDa</p>
              <p className="text-sm text-[#6a6072]">Agent 探索热门货，找出有利润的品</p>
            </div>
          </div>
          <div className="flex flex-col gap-2 text-sm">
            <a href="https://github.com/kingning2/dingda">GitHub 源码</a>
            <Link href="/console">控制台演示</Link>
            <Link href="/faq">常见问题</Link>
            <a href={asset("ai-geo.txt")} rel="alternate" type="text/plain">
              AI GEO 摘要
            </a>
            <a href={asset("doubao-geo.txt")} rel="alternate" type="text/plain">
              豆包 GEO
            </a>
            <a href={asset("llms.txt")} rel="alternate" type="text/markdown">
              llms.txt
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
