"use client";

import { Check, Clipboard, FileText, Sparkles, Wrench } from "lucide-react";
import { useState, type ReactNode } from "react";
import { SimComposer } from "@/components/sim/sim-composer";
import { SimButton } from "@/components/sim/source/button";
import { SimAgentGroup } from "@/components/sim/source/agent-group";
import { Expandable, ExpandableContent } from "@/components/sim/source/expandable";
import { useSmoothText } from "@/hooks/use-smooth-text";
import type { SimActivity, SimContentBlock, SimMessage } from "@/lib/sim-adapter";
import { cn } from "@/lib/utils";

export function SimChat({
  messages,
  activity,
  placeholder,
  disabled = false,
  running = false,
  onSend,
  header,
  notice,
}: {
  messages: SimMessage[];
  activity?: SimActivity;
  placeholder: string;
  disabled?: boolean;
  running?: boolean;
  onSend: (text: string) => Promise<void> | void;
  header?: ReactNode;
  notice?: ReactNode;
}) {
  return (
    <section className="flex h-full min-h-0 flex-col bg-[var(--bg)] text-[var(--text-primary)]" data-testid="sim-chat">
      {header}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-7">
        <div className="mx-auto flex w-full max-w-[760px] flex-col">
          {activity && <SimActivity activity={activity} />}
          {messages.length === 0 && <div className="grid min-h-[45vh] place-items-center text-center text-sm text-[var(--text-muted)]">输入问题开始 Agent 编排</div>}
          {messages.map((message) => <SimMessageRow key={message.id} message={message} />)}
        </div>
      </div>
      <div className="sticky bottom-0 shrink-0 bg-gradient-to-b from-transparent via-[var(--bg)]/95 to-[var(--bg)] px-4 pb-4 pt-8">
        <div className="mx-auto w-full max-w-[780px]">
          {notice}
          <SimComposer onSubmit={onSend} placeholder={placeholder} disabled={disabled} isSending={running} />
        </div>
      </div>
    </section>
  );
}

function SimMessageRow({ message }: { message: SimMessage }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (!message.content || !navigator.clipboard) return;
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };
  const isUser = message.role === "user";
  const displayedContent = useSmoothText(message.content, !isUser && message.status === "streaming");
  return (
    <article className={cn("group/message mb-7 flex w-full flex-col", isUser && "items-end")}>
      <div className={cn(
        "text-[15px] leading-7",
        isUser ? "max-w-[82%] rounded-[16px] bg-[var(--surface-5)] px-4 py-2.5" : "w-full",
        message.status === "error" && "text-red-700",
      )}>
        {displayedContent && <div className="whitespace-pre-wrap">{displayedContent}</div>}
        {!isUser && message.contentBlocks.filter((block) => block.type !== "text").map((block) => <SimBlock key={block.id} block={block} />)}
      </div>
      {!isUser && message.content && (
        <SimButton type="button" variant="quiet" size="icon" onClick={() => void copy()} className="mt-1 grid size-8 place-items-center self-start rounded-md opacity-0 transition-opacity group-hover/message:opacity-100" aria-label="复制消息">
          {copied ? <Check className="size-4" /> : <Clipboard className="size-4" />}
        </SimButton>
      )}
    </article>
  );
}

function SimBlock({ block }: { block: SimContentBlock }) {
  if (block.type === "subagent") return <div className="mt-3 flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"><Sparkles className="size-3.5 text-[var(--brand)]" /><span>{block.title || block.agent || "Sub Agent"}</span><span className="ml-auto text-[var(--text-muted)]">{block.status === "error" ? "失败" : block.status === "complete" ? "完成" : "执行中"}</span></div>;
  if (block.type === "resource") return <div className="mt-3 flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"><FileText className="size-3.5 text-[var(--text-icon)]" /><span>{block.title || "学习产物"}</span><span className="ml-auto text-emerald-600">已就绪</span></div>;
  if (block.type === "status") return <div className="mt-3 flex items-center gap-2 border-l-2 border-[var(--brand)] px-3 py-1 text-xs text-[var(--text-secondary)]"><Wrench className="size-3.5" /><span>{block.content}</span></div>;
  return null;
}

function SimActivity({ activity }: { activity: SimActivity }) {
  const [expanded, setExpanded] = useState(true);
  if (!activity.summary && !activity.agents.length && !activity.tools.length && !activity.evidence.length) return null;
  return <div className="mb-7 rounded-xl border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-sm text-[var(--text-secondary)]" data-testid="sim-execution-trace">
    <SimButton type="button" variant="quiet" onClick={() => setExpanded((value) => !value)} className="flex w-full items-center justify-start gap-2 rounded-none px-0 text-left font-medium text-[var(--text-primary)]"><Sparkles className="size-4 text-[var(--brand)]" /><span>AgentGroup · {activity.summary}</span><span className="ml-auto text-[11px] font-normal text-[var(--text-muted)]">{expanded ? "收起" : `${activity.agents.length} 个 Agent`}</span></SimButton>
    <Expandable expanded={expanded}><ExpandableContent><div className="mt-2 space-y-3 border-t border-[var(--border)] pt-2">{activity.agents.length ? activity.agents.map((run, index) => <SimAgentGroup key={run.id} run={run} isStreaming={activity.running} isCurrentSection={index === activity.agents.length - 1} />) : <p className="py-2 text-xs text-[var(--text-muted)]">等待 Agent 事件…</p>}</div></ExpandableContent></Expandable>
  </div>;
}
