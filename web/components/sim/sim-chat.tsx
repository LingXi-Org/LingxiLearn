"use client";

import { Check, Clipboard, FileText, LoaderCircle, Sparkles, Wrench, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { SimComposer } from "@/components/sim/sim-composer";
import type { SimActivity, SimContentBlock, SimMessage } from "@/lib/sim-adapter";
import { cn } from "@/lib/utils";

export function SimChat({
  messages,
  activity,
  placeholder,
  disabled = false,
  running = false,
  onSend,
  onStopGeneration,
  header,
  notice,
}: {
  messages: SimMessage[];
  activity?: SimActivity;
  placeholder: string;
  disabled?: boolean;
  running?: boolean;
  onSend: (text: string) => Promise<void> | void;
  onStopGeneration?: () => void;
  header?: ReactNode;
  notice?: ReactNode;
}) {
  return (
    <section className="flex h-full min-h-0 flex-col bg-[var(--bg)] text-[var(--text-primary)]" data-testid="sim-chat">
      {header}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-7">
        <div className="mx-auto flex w-full max-w-[760px] flex-col">
          {messages.length === 0 && <div className="grid min-h-[45vh] place-items-center text-center text-sm text-[var(--text-muted)]">等待 Sim 会话开始</div>}
          {messages.map((message) => <SimMessageRow key={message.id} message={message} />)}
          {activity && <SimActivity activity={activity} />}
        </div>
      </div>
      <div className="sticky bottom-0 shrink-0 bg-gradient-to-b from-transparent via-[var(--bg)]/95 to-[var(--bg)] px-4 pb-4 pt-8">
        <div className="mx-auto w-full max-w-[780px]">
          {notice}
          <SimComposer onSubmit={onSend} placeholder={placeholder} disabled={disabled} isSending={running} onStopGeneration={onStopGeneration} />
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
  return (
    <article className={cn("group/message mb-7 flex w-full flex-col", isUser && "items-end")}>
      <div className={cn(
        "text-[15px] leading-7",
        isUser ? "max-w-[82%] rounded-[16px] bg-[var(--surface-5)] px-4 py-2.5" : "w-full",
        message.status === "error" && "text-red-700",
      )}>
        {message.content && <div className="whitespace-pre-wrap">{message.content}</div>}
        {!isUser && message.contentBlocks.filter((block) => block.type !== "text").map((block) => <SimBlock key={block.id} block={block} />)}
      </div>
      {!isUser && message.content && (
        <button type="button" onClick={() => void copy()} className="mt-1 grid size-8 place-items-center self-start rounded-md text-[var(--text-icon)] opacity-0 transition-opacity hover:bg-[var(--surface-hover)] group-hover/message:opacity-100" aria-label="复制消息">
          {copied ? <Check className="size-4" /> : <Clipboard className="size-4" />}
        </button>
      )}
    </article>
  );
}

function SimBlock({ block }: { block: SimContentBlock }) {
  if (block.type === "tool_call" && block.toolCall) {
    const failed = block.toolCall.status === "error";
    const done = block.toolCall.status === "success";
    return <div className="mt-3 flex items-start gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"><span className={cn("mt-0.5 grid size-5 place-items-center rounded-full bg-[var(--surface-4)]", failed && "text-red-600", done && "text-emerald-600")}>{failed ? <X className="size-3" /> : done ? <Check className="size-3" /> : <LoaderCircle className="size-3 animate-spin" />}</span><span className="min-w-0"><span className="font-medium">{block.toolCall.displayTitle}</span>{block.toolCall.detail && <span className="ml-2 text-[var(--text-muted)]">{block.toolCall.detail}</span>}</span></div>;
  }
  if (block.type === "subagent") return <div className="mt-3 flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"><Sparkles className="size-3.5 text-[var(--brand)]" /><span>{block.title || block.agent || "Sub Agent"}</span><span className="ml-auto text-[var(--text-muted)]">{block.status === "error" ? "失败" : block.status === "complete" ? "完成" : "执行中"}</span></div>;
  if (block.type === "resource") return <div className="mt-3 flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"><FileText className="size-3.5 text-[var(--text-icon)]" /><span>{block.title || "学习产物"}</span><span className="ml-auto text-emerald-600">已就绪</span></div>;
  if (block.type === "status") return <div className="mt-3 flex items-center gap-2 border-l-2 border-[var(--brand)] px-3 py-1 text-xs text-[var(--text-secondary)]"><Wrench className="size-3.5" /><span>{block.content}</span></div>;
  return null;
}

function SimActivity({ activity }: { activity: SimActivity }) {
  if (!activity.summary && !activity.plan.length && !activity.tools.length && !activity.evidence.length) return null;
  return <div className="mb-7 border-l border-[var(--border)] pl-4 text-sm text-[var(--text-secondary)]"><div className="flex items-center gap-2 font-medium text-[var(--text-primary)]"><Sparkles className="size-4 text-[var(--brand)]" />执行过程</div><p className="mt-2 leading-6">{activity.summary}</p>{activity.plan.length > 0 && <ol className="mt-3 space-y-1.5">{activity.plan.map((step, index) => <li key={`${step}-${index}`}><span className="mr-2 font-mono text-[10px] text-[var(--text-muted)]">{String(index + 1).padStart(2, "0")}</span>{step}</li>)}</ol>}{activity.tools.map((tool) => <div key={tool.id} className="mt-2 flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"><Wrench className="size-3.5 text-[var(--text-icon)]" /><span>{tool.displayTitle}</span><span className="ml-auto text-[var(--text-muted)]">{tool.detail || (tool.status === "executing" ? "执行中" : tool.status === "error" ? "失败" : "完成")}</span></div>)}</div>;
}
