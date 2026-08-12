"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { SimButton } from "@/components/sim/source/button";
import { SimArrowUp, SimPlus } from "@/components/sim/source/icons";

/**
 * LingxiLearn adaptation of sim's workspace UserInput surface.
 *
 * The structure and interaction states follow the upstream Sim source at
 * `apps/sim/app/workspace/[workspaceId]/home/components/user-input`, while
 * the submit callback remains owned by LingxiLearn's REST/SSE session model.
 * Upstream source: https://github.com/simstudioai/sim/commit/ce2dff3c
 */

const SEND_BUTTON_BASE = "size-[28px] rounded-full border-0 p-0 transition-colors";
const SEND_BUTTON_ACTIVE = "bg-[#383838] hover:bg-[#575757]";
const SEND_BUTTON_DISABLED = "bg-[#808080]";

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

  const resize = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 192)}px`;
  }, []);

  useLayoutEffect(() => {
    resize();
  }, [resize, value]);

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
      <textarea
        ref={textareaRef}
        aria-label={ariaLabel}
        value={value}
        placeholder={placeholder}
        rows={1}
        disabled={disabled || isSending}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        className="block max-h-[200px] min-h-[56px] w-full resize-none overflow-y-auto bg-transparent text-[14px] leading-6 tracking-[-0.015em] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-70"
      />
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <span className="grid size-7 place-items-center rounded-full text-[var(--text-icon)]" title="问题将进入 Agent 编排"><SimPlus className="size-4" /></span>
          <span className="text-[11px] text-[var(--text-muted)]">Agent Task</span>
        </div>
        <div className="flex items-center gap-1.5">
        {isSending ? (
          <span className="grid size-7 place-items-center rounded-full bg-[var(--surface-5)]" aria-label="任务提交中" title="任务提交中"><span className="size-3 animate-spin rounded-full border-2 border-white/40 border-t-white" /></span>
        ) : (
          <SimButton
            type="submit"
            variant="ghost"
            size="icon"
            disabled={disabled || isSending || !value.trim()}
            className={cn(
              SEND_BUTTON_BASE,
              "grid place-items-center text-white",
              disabled || isSending || !value.trim() ? SEND_BUTTON_DISABLED : SEND_BUTTON_ACTIVE,
            )}
            aria-label="发送任务"
            title="发送任务"
          >
            <SimArrowUp className="size-4" />
          </SimButton>
        )}
        </div>
      </div>
    </form>
  );
}
