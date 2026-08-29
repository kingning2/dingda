import { asset } from "@/lib/site";
import Link from "next/link";

export function DingDaBrand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/console" className="flex items-center gap-2.5">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={asset("assets/logo.webp")}
        alt="叮答"
        width={compact ? 28 : 32}
        height={compact ? 28 : 32}
        className="rounded-lg object-cover"
      />
      {!compact && <span className="text-lg font-semibold text-text-primary">叮答</span>}
    </Link>
  );
}
