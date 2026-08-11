"use client";

import {
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import {
  ArrowDown,
  ArrowUp,
  Check,
  Clipboard,
  Lightbulb,
  Plus,
  RotateCcw,
  Sparkle,
  Square,
} from "lucide-react";
import { useCallback, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AgentActivity, WorkspaceMessage } from "@/lib/workspace";

const actionClass = "grid size-8 place-items-center rounded-md text-[#737373] transition-colors hover:bg-black/[.05] hover:text-[#171717]";

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
  return (
    <Runtime messages={[]} running={running} disabled={disabled} onSend={onSend}>
      <LearningComposer className={cn("mx-auto w-full max-w-[780px]", className)} placeholder={placeholder} />
    </Runtime>
  );
}

export function LearningConversation({
  messages,
  activity,
  canSend,
  running,
  onSend,
  onHint,
  onWalkthrough,
}: {
  messages: WorkspaceMessage[];
  activity: AgentActivity;
  canSend: boolean;
  running: boolean;
  onSend: (text: string) => Promise<void> | void;
  onHint?: () => void;
  onWalkthrough?: () => void;
}) {
  return (
    <Runtime messages={messages} running={running} disabled={!canSend} onSend={onSend}>
      <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col bg-[#fafafa] text-[#202020]">
        <ThreadPrimitive.Viewport className="flex min-h-0 grow flex-col overflow-y-auto px-4 pt-7">
          <div className="mx-auto flex w-full max-w-[760px] grow flex-col">
            <ThreadPrimitive.Messages components={{ Message: LearningMessage }} />
            <AgentProcess activity={activity} />
          </div>
          <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mx-auto mt-auto w-full max-w-[780px] bg-gradient-to-b from-transparent via-[#fafafa]/90 to-[#fafafa] pb-3 pt-8">
            {(onHint || onWalkthrough) && (
              <div className="mb-2 flex gap-2">
                {onHint && <Button variant="outline" size="sm" onClick={onHint} disabled={!canSend}><Lightbulb className="size-4" />给我提示</Button>}
                {onWalkthrough && <Button variant="ghost" size="sm" onClick={onWalkthrough} disabled={!canSend}><RotateCcw className="size-4" />复盘过程</Button>}
              </div>
            )}
            <LearningComposer placeholder={canSend ? "继续对话…" : "请先在右侧完成当前任务"} />
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
        <ThreadPrimitive.ScrollToBottom className="absolute bottom-28 left-1/2 grid size-9 -translate-x-1/2 place-items-center rounded-full border border-[#dedede] bg-white text-[#666]">
          <ArrowDown className="size-4" />
        </ThreadPrimitive.ScrollToBottom>
      </ThreadPrimitive.Root>
    </Runtime>
  );
}

function LearningComposer({ className, placeholder }: { className?: string; placeholder: string }) {
  return (
    <ComposerPrimitive.Root className={cn("flex min-h-[118px] w-full flex-col rounded-[22px] border border-[#cfcfcf] bg-white px-3.5 pb-2.5 pt-3 shadow-[0_12px_30px_rgba(0,0,0,.045)]", className)}>
      <ComposerPrimitive.Input
        aria-label="学习任务输入"
        placeholder={placeholder}
        rows={2}
        className="block max-h-72 min-h-14 w-full resize-none bg-transparent text-[16px] leading-7 text-[#202020] outline-none placeholder:text-[#a1a1a1]"
      />
      <div className="mt-auto flex items-center gap-2">
        <button type="button" disabled title="附件功能即将开放" className="grid size-8 place-items-center rounded-md text-[#777] hover:bg-black/[.05] disabled:opacity-55" aria-label="添加附件">
          <Plus className="size-4" />
        </button>
        <span className="ml-auto text-sm text-[#777]">灵犀智学</span>
        <AuiIf condition={(state) => state.thread.isRunning}>
          <ComposerPrimitive.Cancel className="grid size-8 place-items-center rounded-md bg-[#202020] text-white" aria-label="停止生成">
            <Square className="size-3 fill-current" />
          </ComposerPrimitive.Cancel>
        </AuiIf>
        <AuiIf condition={(state) => !state.thread.isRunning}>
          <ComposerPrimitive.Send className="grid size-8 place-items-center rounded-md bg-[#202020] text-white transition-colors hover:bg-black disabled:bg-[#d5d5d5]" aria-label="发送任务">
            <ArrowUp className="size-4" />
          </ComposerPrimitive.Send>
        </AuiIf>
      </div>
    </ComposerPrimitive.Root>
  );
}

function LearningMessage() {
  return (
    <MessagePrimitive.Root className="group/message mb-7 flex w-full flex-col">
      <AuiIf condition={(state) => state.message.role === "user"}>
        <div className="ml-auto max-w-[82%] rounded-2xl bg-[#ececec] px-4 py-2.5 text-[15px] leading-6">
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
    <div className="mb-7 border-l border-[#cfcfcf] pl-4 text-sm text-[#666]">
      <div className="flex items-center gap-2 font-medium text-[#202020]"><Sparkle className="size-4 text-[#5b5ce2]" />执行过程</div>
      {activity.summary && <p className="mt-2 leading-6">{activity.summary}</p>}
      {activity.plan.length > 0 && <ol className="mt-3 space-y-1.5">{activity.plan.map((step, index) => <li key={`${step}-${index}`}>{index + 1}. {step}</li>)}</ol>}
      {activity.tools.map((tool) => <div key={tool.id} className="mt-2 rounded-lg border border-[#dedede] bg-white px-3 py-2">{tool.name}{tool.detail ? ` · ${tool.detail}` : ""}</div>)}
    </div>
  );
}
