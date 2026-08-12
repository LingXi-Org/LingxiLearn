"use client";

import {
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  AuiIf,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import {
  Check,
  Clipboard,
  Sparkle,
} from "lucide-react";
import { useCallback, type ReactNode } from "react";
import { SimComposer } from "@/components/sim/sim-composer";
import { cn } from "@/lib/utils";
import type { AgentActivity, WorkspaceMessage } from "@/lib/workspace";

const actionClass = "grid size-8 place-items-center rounded-md text-[var(--text-icon)] transition-colors hover:bg-[var(--surface-5)] hover:text-[var(--text-primary)]";

function textFromAppend(message: AppendMessage) {
  return message.content.find((part) => part.type === "text")?.text?.trim() ?? "";
}

function Runtime({
  children,
  messages,
  running,
  disabled,
  onSend,
}: {
  children: ReactNode;
  messages: WorkspaceMessage[];
  running: boolean;
  disabled: boolean;
  onSend: (text: string) => Promise<void> | void;
}) {
  const convertMessage = useCallback((message: WorkspaceMessage): ThreadMessageLike => ({
    id: message.id,
    role: message.role,
    content: [{ type: "text", text: message.text }],
    status: message.role === "assistant" ? { type: "complete", reason: "stop" } : undefined,
  }), []);

  const onNew = useCallback(async (message: AppendMessage) => {
    const text = textFromAppend(message);
    if (text && !disabled) await onSend(text);
  }, [disabled, onSend]);

  const runtime = useExternalStoreRuntime({
    messages,
    convertMessage,
    isRunning: running,
    isDisabled: disabled,
    onNew,
  });

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}

export function LearningPrompt({
  onSend,
  placeholder,
  disabled = false,
  running = false,
  className,
}: {
  onSend: (text: string) => Promise<void> | void;
  placeholder: string;
  disabled?: boolean;
  running?: boolean;
  className?: string;
}) {
  return <LearningComposer className={cn("mx-auto w-full max-w-[780px]", className)} placeholder={placeholder} disabled={disabled} running={running} onSend={onSend} />;
}

export function LearningConversation({
  messages,
  activity,
  canSend,
  running,
  onSend,
}: {
  messages: WorkspaceMessage[];
  activity: AgentActivity;
  canSend: boolean;
  running: boolean;
  onSend: (text: string) => Promise<void> | void;
}) {
  return (
    <Runtime messages={messages} running={running} disabled={!canSend} onSend={onSend}>
      <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col bg-[var(--bg)] text-[var(--text-primary)]">
        <ThreadPrimitive.Viewport className="flex min-h-0 grow flex-col overflow-y-auto px-4 pt-7">
          <div className="mx-auto flex w-full max-w-[760px] grow flex-col">
            <ThreadPrimitive.Messages components={{ Message: LearningMessage }} />
            <AgentProcess activity={activity} />
          </div>
          <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mx-auto mt-auto w-full max-w-[780px] bg-gradient-to-b from-transparent via-[#fafafa]/90 to-[#fafafa] pb-3 pt-8">
            <LearningComposer
              placeholder={canSend ? "继续对话…" : "请先在右侧完成当前任务"}
              disabled={!canSend}
              running={running}
              onSend={onSend}
            />
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
        <ThreadPrimitive.ScrollToBottom className="absolute bottom-28 left-1/2 grid size-9 -translate-x-1/2 place-items-center rounded-full border border-[var(--border)] bg-[var(--surface-1)] text-[var(--text-icon)]">
          <span className="text-xs">↓</span>
        </ThreadPrimitive.ScrollToBottom>
      </ThreadPrimitive.Root>
    </Runtime>
  );
}

function LearningComposer({
  className,
  placeholder,
  disabled,
  running,
  onSend,
}: {
  className?: string;
  placeholder: string;
  disabled?: boolean;
  running?: boolean;
  onSend: (text: string) => Promise<void> | void;
}) {
  return (
    <SimComposer
      className={className}
      placeholder={placeholder}
      disabled={disabled}
      isSending={running}
      onSubmit={onSend}
      onStopGeneration={() => undefined}
    />
  );
}

function LearningMessage() {
  return (
    <MessagePrimitive.Root className="group/message mb-7 flex w-full flex-col">
      <AuiIf condition={(state) => state.message.role === "user"}>
        <div className="ml-auto max-w-[82%] rounded-[16px] bg-[var(--surface-5)] px-4 py-2.5 text-[15px] leading-6">
          <MessagePrimitive.Parts components={{ Text: ({ text }) => <span className="whitespace-pre-wrap">{text}</span> }} />
        </div>
      </AuiIf>
      <AuiIf condition={(state) => state.message.role === "assistant"}>
        <div className="w-full text-[15px] leading-[1.7rem]">
          <MessagePrimitive.Parts components={{ Text: ({ text }) => <div className="whitespace-pre-wrap">{text}</div> }} />
        </div>
      </AuiIf>
      <ActionBarPrimitive.Root hideWhenRunning autohide="not-last" className="mt-1 flex justify-end opacity-0 transition-opacity group-hover/message:opacity-100">
        <ActionBarPrimitive.Copy className={actionClass} aria-label="复制消息">
          <AuiIf condition={(state) => state.message.isCopied}><Check className="size-4" /></AuiIf>
          <AuiIf condition={(state) => !state.message.isCopied}><Clipboard className="size-4" /></AuiIf>
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
    </MessagePrimitive.Root>
  );
}

function AgentProcess({ activity }: { activity: AgentActivity }) {
  if (!activity.summary && activity.plan.length === 0 && activity.tools.length === 0) return null;
  return (
    <div className="mb-7 border-l border-[var(--border)] pl-4 text-sm text-[var(--text-secondary)]">
      <div className="flex items-center gap-2 font-medium text-[var(--text-primary)]"><Sparkle className="size-4 text-[var(--brand)]" />执行过程</div>
      {activity.summary && <p className="mt-2 leading-6">{activity.summary}</p>}
      {activity.plan.length > 0 && <ol className="mt-3 space-y-1.5">{activity.plan.map((step, index) => <li key={`${step}-${index}`}>{index + 1}. {step}</li>)}</ol>}
      {activity.tools.map((tool) => <div key={tool.id} className="mt-2 rounded-lg border border-[#dedede] bg-white px-3 py-2">{tool.name}{tool.detail ? ` · ${tool.detail}` : ""}</div>)}
    </div>
  );
}
