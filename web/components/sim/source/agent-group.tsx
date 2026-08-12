"use client";

import { ChevronDown, Sparkles } from "lucide-react";
import { useState } from "react";
import type { SimAgentRun } from "@/lib/sim-adapter";
import { cn } from "./lib/cn";
import { Expandable, ExpandableContent } from "./expandable";
import { ShimmerText } from "./shimmer-text";

// Adapted directly from Sim's AgentGroup @ ce2dff3c. The expansion contract is
// retained: live lanes auto-open, completed lanes collapse, manual choice wins.
export function SimAgentGroup({ run, isStreaming, onSelect, defaultExpanded = false }: { run: SimAgentRun; isStreaming: boolean; onSelect?: (agent: string) => void; defaultExpanded?: boolean }) {
  const isLaneOpen = run.status === "running";
  const autoExpanded = isStreaming && isLaneOpen;
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(defaultExpanded ? true : null);
  const expanded = manualExpanded ?? autoExpanded;
  const toggle = () => { setManualExpanded(!expanded); onSelect?.(run.agent); };

  return <div className="flex flex-col gap-1.5" data-agent={run.agent}>
    <button type="button" onClick={toggle} className="group/agent flex cursor-pointer items-center gap-2 text-left">
      <div className="flex size-4 shrink-0 items-center justify-center"><Sparkles className="size-4 text-[var(--text-icon)]" /></div>
      {isLaneOpen ? <ShimmerText className="text-sm">{run.label}</ShimmerText> : <span className="text-sm text-[var(--text-body)]">{run.label}</span>}
      <ChevronDown className={cn("size-3.5 text-[var(--text-icon)] opacity-0 transition-[transform,opacity] duration-150 group-hover/agent:opacity-100 group-focus-visible/agent:opacity-100", !expanded && "-rotate-90")} />
      <span className={cn("ml-auto text-[11px]", run.status === "error" ? "text-red-600" : "text-[var(--text-muted)]")}>{run.status === "running" ? "执行中" : run.status === "error" ? "失败" : "完成"}</span>
    </button>
    <Expandable expanded={expanded}>
      <ExpandableContent>
        <div className="flex max-h-48 flex-col gap-1.5 overflow-y-auto py-0.5">
          {run.items.map((item) => <span key={item.id} className={cn("pl-6 text-[13px] leading-[18px] text-[var(--text-muted)]", item.status === "error" && "text-red-700")}>{item.content}</span>)}
        </div>
      </ExpandableContent>
    </Expandable>
  </div>;
}
