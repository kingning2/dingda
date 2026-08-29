import Providers from "@/app/providers";
import { SITE_DISCOVERY_URLS, SITE_VERIFICATION, TOUTIAO_WEBMASTER, rootMetadata } from "@/lib/seo";
import { cn } from "@/utils/cn";
import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = rootMetadata;

const discoveryLinks = [
  { rel: "sitemap", type: "application/xml", title: "Sitemap", href: SITE_DISCOVERY_URLS.sitemap() },
  { rel: "alternate", type: "text/plain", title: "Robots", href: SITE_DISCOVERY_URLS.robotsTxt() },
  { rel: "alternate", type: "text/markdown", title: "LLMs summary", href: SITE_DISCOVERY_URLS.llmsTxt() },
  { rel: "alternate", type: "text/plain", title: "AI GEO summary", href: SITE_DISCOVERY_URLS.aiGeo() },
  { rel: "alternate", type: "text/plain", title: "Doubao GEO summary", href: SITE_DISCOVERY_URLS.doubaoGeo() },
] as const;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      suppressHydrationWarning
      lang="zh-CN"
      className={cn("h-full overflow-hidden antialiased", inter.className)}
    >
      <head>
        <meta name="google-site-verification" content={SITE_VERIFICATION.google} />
        <meta name={TOUTIAO_WEBMASTER.verifyMetaName} content={SITE_VERIFICATION.toutiao} />
        {discoveryLinks.map((link) => (
          <link
            key={link.href}
            rel={link.rel}
            type={link.type}
            title={link.title}
            href={link.href}
          />
        ))}
      </head>
      <body className="h-full overflow-hidden bg-background-gray-secondary_alt_2">
        <ThemeProvider defaultTheme="light" enableSystem>
          <Providers>{children}</Providers>
        </ThemeProvider>
        <Toaster />
      </body>
    </html>
  );
}
