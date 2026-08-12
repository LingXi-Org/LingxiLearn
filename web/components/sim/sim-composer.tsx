"use client";

import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { SimPlus } from "@/components/sim/source/icons";
import { SimPromptEditor } from "@/components/sim/source/prompt-editor";
import { SimSendButton } from "@/components/sim/source/send-button";

/**
 * LingxiLearn adaptation of sim's workspace UserInput surface.
 *
 * The structure and interaction states follow the upstream Sim source at
 * `apps/sim/app/workspace/[workspaceId]/home/components/user-input`, while
 * the submit callback remains owned by LingxiLearn's REST/SSE session model.
 * Upstream source: https://github.com/simstudioai/sim/commit/ce2dff3c
 */

interface SimComposerProps {
  onSubmit: (text: string) => void | Promise<void>;
  placeholder: string;
  disabled?: boolean;
  isSending?: boolean;
  className?: string;
  "aria-label"?: string;
}

export function SimComposer({
  onSubmit,
  placeholder,
  disabled = false,
  isSending = false,
  className,
  "aria-label": ariaLabel = "学习任务输入",
}: SimComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isSending) return;
    setValue("");
    void onSubmit(trimmed);
  }, [disabled, isSending, onSubmit, value]);

  return (
    <form
      className={cn(
        "relative z-10 mx-auto flex w-full max-w-[780px] cursor-text flex-col rounded-2xl border border-[var(--border-1)] bg-[var(--surface-2)] px-2.5 py-2",
        className,
      )}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <SimPromptEditor
        ref={textareaRef}
        aria-label={ariaLabel}
        value={value}
        placeholder={placeholder}
        disabled={disabled || isSending}
        onValueChange={setValue}
        onSubmit={submit}
      />
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <span className="grid size-7 place-items-center rounded-full text-[var(--text-icon)]" title="问题将进入 Agent 编排"><SimPlus className="size-4" /></span>
          <span className="text-[11px] text-[var(--text-muted)]">Agent Task</span>
        </div>
        <div className="flex items-center gap-1.5">
        <SimSendButton
          isSending={isSending}
          disabled={disabled || isSending || !value.trim()}
          aria-label="发送任务"
          title="发送任务"
        />
        </div>
      </div>
    </form>
  );
}
