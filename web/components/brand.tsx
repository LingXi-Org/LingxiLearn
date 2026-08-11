import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <Link href="/" className={cn("inline-flex items-center gap-2.5", className)} aria-label="灵犀智学首页">
      <Image src="/logo_icon.svg" alt="" width={36} height={36} className="size-9" priority />
      {!compact && <span className="text-[15px] font-semibold tracking-[-0.02em]">灵犀智学</span>}
    </Link>
  );
}
