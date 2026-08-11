"use client";

import Link from "next/link";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
      <span className="grid place-items-center w-8 h-8 rounded-[10px] bg-accent-500 text-white font-semibold text-[15px] shadow-sm group-hover:bg-accent-600 transition-colors">
        灵
      </span>
      <span className={compact ? "hidden sm:block" : ""}>
        <span className="block font-semibold tracking-tight leading-none">LingxiLearn</span>
        {!compact && <span className="block text-[11px] muted mt-0.5">工科 AI 助教</span>}
      </span>
    </Link>
  );
}

export function BrainBadge({ brain }: { brain?: string }) {
  if (!brain) return null;
  const labels: Record<string, string> = {
    scripted: "确定性引擎",
    openai: "OpenAI 兼容模型",
    coze: "Coze",
  };
  const title =
    brain === "scripted"
      ? "当前未配置 LLM，教练由确定性教学引擎驱动。判分、误区识别、掌握度与证据本来就不依赖模型，因此完整闭环照常运行。"
      : "教练措辞由模型生成；判分、误区识别与证据引用仍由确定性引擎负责。";
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 text-[11px] muted px-2 py-1 rounded-full border"
      style={{ borderColor: "var(--line)" }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{
          background: brain === "scripted" ? "var(--color-ink-400)" : "var(--color-accent-500)",
        }}
      />
      {labels[brain] ?? brain}
    </span>
  );
}

export function Pill({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "bad" | "accent";
  children: React.ReactNode;
}) {
  const tones: Record<string, string> = {
    neutral: "var(--color-ink-400)",
    ok: "var(--color-ok-500)",
    warn: "var(--color-warn-500)",
    bad: "var(--color-bad-500)",
    accent: "var(--color-accent-500)",
  };
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full"
      style={{
        color: tones[tone],
        background: `color-mix(in oklab, ${tones[tone]} 12%, transparent)`,
      }}
    >
      {children}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[12px] muted">
      <span
        className="w-3 h-3 rounded-full border-2 border-transparent animate-spin"
        style={{
          borderTopColor: "var(--color-accent-500)",
          borderRightColor: "var(--color-accent-500)",
        }}
      />
      {label}
    </span>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full grid place-items-center p-8 text-center">
      <p className="text-[13px] muted max-w-xs leading-relaxed">{children}</p>
    </div>
  );
}
