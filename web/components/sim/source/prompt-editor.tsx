"use client";

import { forwardRef, useCallback, useLayoutEffect, type KeyboardEvent, type TextareaHTMLAttributes } from "react";
import { cn } from "./lib/cn";

/**
 * Sim prompt editor surface, reduced to the interaction contract used by
 * LingxiLearn. The upstream editor's attachment, mention and resource menus
 * are intentionally omitted because those capabilities are not mounted here.
 * Sim snapshot: ce2dff3c.
 */
export interface SimPromptEditorProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange" | "onSubmit"> {
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
}

export const SimPromptEditor = forwardRef<HTMLTextAreaElement, SimPromptEditorProps>(function SimPromptEditor(
  { value, onValueChange, onSubmit, className, ...props },
  ref,
) {
  const resize = useCallback(() => {
    const textarea = typeof ref === "object" && ref !== null ? ref.current : null;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 192)}px`;
  }, [ref]);

  useLayoutEffect(() => resize(), [resize, value]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
    props.onKeyDown?.(event);
  };

  return (
    <textarea
      {...props}
      ref={ref}
      value={value}
      rows={1}
      onChange={(event) => onValueChange(event.target.value)}
      onKeyDown={handleKeyDown}
      className={cn(
        "block max-h-[200px] min-h-[56px] w-full resize-none overflow-y-auto bg-transparent text-[14px] leading-6 tracking-[-0.015em] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-70",
        className,
      )}
    />
  );
});
