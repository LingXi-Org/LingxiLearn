"use client";

import { ChevronDown, Sparkles } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { SimAgentGroupItem, SimAgentRun } from "@/lib/sim-adapter";
import { cn } from "./lib/cn";
import { Expandable, ExpandableContent } from "./expandable";
import { ShimmerText } from "./shimmer-text";

// Adapted from Sim's recursive AgentGroup @ ce2dff3c. It preserves the source
// contract: live lanes auto-open, completed lanes collapse, manual choice wins,
// and each lane owns a bounded viewport that follows streamed output.
export function SimAgentGroup({ run, isStreaming, onSelect, defaultExpanded = false, isCurrentSection = false }: { run: SimAgentRun; isStreaming: boolean; onSelect?: (agent: string) => void; defaultExpanded?: boolean; isCurrentSection?: boolean }) {
  const isLaneOpen = run.status === "running";
  const groupItems = run.groupItems ?? [
    ...run.items.map((item) => ({ type: "text" as const, id: item.id, content: item.content, status: item.status })),
    ...(run.children ?? []).map((child) => ({ type: "agent" as const, id: child.id, run: child })),
  ];
  const hasWork = groupItems.length > 0;
  const autoExpanded = isStreaming && (isCurrentSection || isLaneOpen || Boolean(run.isDelegating));
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(defaultExpanded ? true : null);
  const expanded = hasAwaitingApproval(groupItems) || (manualExpanded ?? autoExpanded);
  const toggle = () => { setManualExpanded(!expanded); onSelect?.(run.agent); };

  return <div className="flex flex-col gap-1.5" data-agent={run.agent}>
    {hasWork ? <button type="button" onClick={toggle} className="group/agent flex cursor-pointer items-center gap-2 text-left">
      <div className="flex size-4 shrink-0 items-center justify-center"><Sparkles className="size-4 text-[var(--text-icon)]" /></div>
      {isLaneOpen || run.isDelegating ? <ShimmerText className="text-sm">{run.label}</ShimmerText> : <span className="text-sm text-[var(--text-body)]">{run.label}</span>}
      <ChevronDown className={cn("size-3.5 text-[var(--text-icon)] opacity-0 transition-[transform,opacity] duration-150 group-hover/agent:opacity-100 group-focus-visible/agent:opacity-100", !expanded && "-rotate-90")} />
      <span className={cn("ml-auto text-[11px]", run.status === "error" ? "text-red-600" : "text-[var(--text-muted)]")}>{run.status === "running" ? "执行中" : run.status === "error" ? "失败" : "完成"}</span>
    </button> : <div className="flex items-center gap-2"><div className="flex size-4 shrink-0 items-center justify-center"><Sparkles className="size-4 text-[var(--text-icon)]" /></div><span className="text-sm text-[var(--text-body)]">{run.label}</span></div>}
    {hasWork && <Expandable expanded={expanded}>
      <ExpandableContent>
        <BoundedViewport isStreaming={isStreaming}>
          <div className="flex flex-col gap-1.5 py-0.5">
            {groupItems.map((item, index) => item.type === "text"
              ? <span key={item.id} className={cn("pl-6 text-[13px] leading-[18px] text-[var(--text-muted)]", item.status === "error" && "text-red-700")}>{item.content}</span>
              : item.type === "tool"
                ? <div key={item.id} className="flex items-start gap-2 pl-6 text-[12px] leading-[18px] text-[var(--text-muted)]"><span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", item.status === "executing" ? "bg-[var(--brand)]" : item.status === "awaiting_approval" ? "bg-amber-500" : item.status === "error" ? "bg-red-600" : "bg-emerald-600")} /><span className="shrink-0">{item.title}</span>{item.detail && <span className="whitespace-pre-wrap break-all text-[11px] opacity-70">{item.detail}</span>}</div>
                : <div key={item.id} className="pl-6"><SimAgentGroup run={item.run} isStreaming={isStreaming} isCurrentSection={index === groupItems.length - 1} /></div>)}
          </div>
        </BoundedViewport>
      </ExpandableContent>
    </Expandable>}
  </div>;
}

function hasAwaitingApproval(items: SimAgentGroupItem[]): boolean {
  return items.some((item) => item.type === "tool"
    ? item.status === "awaiting_approval"
    : item.type === "agent"
      ? Boolean(item.run.groupItems && hasAwaitingApproval(item.run.groupItems))
      : false);
}

function BoundedViewport({ children, isStreaming }: { children: ReactNode; isStreaming: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  const stickToBottomRef = useRef(true);
  const previousScrollTop = useRef(0);
  const [hasOverflow, setHasOverflow] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => { if (event.deltaY < 0) stickToBottomRef.current = false; };
    const onScroll = () => {
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      if (distance < 8 && element.scrollTop > previousScrollTop.current) stickToBottomRef.current = true;
      previousScrollTop.current = element.scrollTop;
    };
    element.addEventListener("wheel", onWheel, { passive: true });
    element.addEventListener("scroll", onScroll, { passive: true });
    return () => { element.removeEventListener("wheel", onWheel); element.removeEventListener("scroll", onScroll); };
  }, []);

  useLayoutEffect(() => {
    const element = ref.current;
    if (element) setHasOverflow(element.scrollHeight > element.clientHeight);
    if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current);
    if (!isStreaming) return;
    const tick = () => {
      const node = ref.current;
      if (!node || !stickToBottomRef.current) { rafRef.current = null; return; }
      const gap = node.scrollHeight - node.clientHeight - node.scrollTop;
      if (gap < 1) { rafRef.current = null; return; }
      node.scrollTop += Math.max(1, gap * 0.18);
      rafRef.current = window.requestAnimationFrame(tick);
    };
    rafRef.current = window.requestAnimationFrame(tick);
    return () => { if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current); };
  });

  return <div className="relative">
    <div ref={ref} className={cn("max-h-[180px] overflow-y-auto pr-2", hasOverflow && "py-1")}>{children}</div>
    {hasOverflow && <><div className="pointer-events-none absolute inset-x-0 top-0 h-3 bg-gradient-to-b from-[var(--surface-1)] to-transparent" /><div className="pointer-events-none absolute inset-x-0 bottom-0 h-3 bg-gradient-to-t from-[var(--surface-1)] to-transparent" /></>}
  </div>;
}
