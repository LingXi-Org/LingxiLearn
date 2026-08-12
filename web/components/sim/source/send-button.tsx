"use client";

import { SimArrowUp } from "./icons";
import { SimButton, type SimButtonProps } from "./button";
import { cn } from "./lib/cn";

/** Sim's send-button treatment, limited to the current task submit state. */
export function SimSendButton({ disabled, isSending = false, className, ...props }: SimButtonProps & { isSending?: boolean }) {
  if (isSending) {
    return <span className="grid size-7 place-items-center rounded-full bg-[var(--surface-5)]" aria-label="任务提交中" title="任务提交中"><span className="size-3 animate-spin rounded-full border-2 border-white/40 border-t-white" /></span>;
  }

  return (
    <SimButton
      {...props}
      type={props.type ?? "submit"}
      variant="ghost"
      size="icon"
      disabled={disabled}
      className={cn(
        "grid size-7 place-items-center rounded-full border-0 p-0 text-white transition-colors",
        disabled ? "bg-[#808080]" : "bg-[#383838] hover:bg-[#575757]",
        className,
      )}
      aria-label={props["aria-label"] ?? "发送任务"}
      title={props.title ?? "发送任务"}
    >
      <SimArrowUp className="size-4" />
    </SimButton>
  );
}
