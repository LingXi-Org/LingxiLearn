"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { Mic, Paperclip } from "lucide-react";
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

const SEND_BUTTON_BASE = "h-[28px] w-[28px] rounded-full border-0 p-0 transition-colors";
const SEND_BUTTON_ACTIVE = "bg-[#383838] hover:bg-[#575757]";
const SEND_BUTTON_DISABLED = "bg-[#808080]";

interface SimComposerProps {
  onSubmit: (text: string) => void | Promise<void>;
  placeholder: string;
  disabled?: boolean;
  isSending?: boolean;
  onStopGeneration?: () => void;
  className?: string;
  "aria-label"?: string;
}

export function SimComposer({
  onSubmit,
  placeholder,
  disabled = false,
  isSending = false,
  onStopGeneration,
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
        "flex min-h-[122px] w-full flex-col rounded-[16px] border border-[#e1e1e1] bg-[var(--surface-1)] px-4 pb-3 pt-3.5",
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
        className="block max-h-48 min-h-14 w-full resize-none overflow-y-auto bg-transparent text-[14px] leading-6 tracking-[-0.015em] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-70"
      />
      <div className="mt-auto flex items-center gap-1.5 pt-3">
        <SimButton
          type="button"
          variant="ghost"
          size="icon"
          disabled
          title="附件功能即将开放"
          aria-label="添加资源"
          className="grid size-7 place-items-center rounded-full text-[var(--text-icon)] transition-colors hover:bg-[var(--surface-5)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <SimPlus className="size-4" />
        </SimButton>
        <SimButton
          type="button"
          variant="ghost"
          size="icon"
          disabled
          title="附件功能即将开放"
          aria-label="添加附件"
          className="grid size-7 place-items-center rounded-full text-[var(--text-icon)] transition-colors hover:bg-[var(--surface-5)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Paperclip className="size-[17px]" strokeWidth={1.6} />
        </SimButton>
        <SimButton
          type="button"
          variant="ghost"
          size="icon"
          disabled
          title="技能快捷方式即将开放"
          aria-label="打开快捷方式"
          className="grid size-7 place-items-center rounded-full text-[var(--text-icon)] transition-colors hover:bg-[var(--surface-5)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="text-[17px] leading-none">/</span>
        </SimButton>
        <div className="ml-auto flex items-center gap-1.5">
          <SimButton
            type="button"
            variant="ghost"
            size="icon"
            disabled
            title="语音输入即将开放"
            aria-label="语音输入"
            className="grid size-7 place-items-center rounded-full text-[var(--text-icon)] transition-colors hover:bg-[var(--surface-5)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Mic className="size-[17px]" strokeWidth={1.6} />
          </SimButton>
        {isSending ? (
          <SimButton
            type="button"
            variant="ghost"
            size="icon"
            onClick={onStopGeneration}
            disabled={!onStopGeneration}
            className={cn(SEND_BUTTON_BASE, SEND_BUTTON_ACTIVE, "grid place-items-center text-white disabled:opacity-50")}
            aria-label="停止生成"
            title="停止生成"
          >
            <span className="size-3 rounded-[3px] bg-current" />
          </SimButton>
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
