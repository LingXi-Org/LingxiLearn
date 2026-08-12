"use client";

import { forwardRef, useCallback, useLayoutEffect, useRef, useState, type KeyboardEvent, type TextareaHTMLAttributes } from "react";
import { cn } from "./lib/cn";
import type { NativeSkill } from "@/lib/types";
import { SimSkillsMenuDropdown, type SimSkillsMenuHandle } from "./skills-menu-dropdown";

/**
 * Sim prompt editor surface. The editor instance used by the full Sim input
 * owns attachments, mentions and resource menus; this host passes the same
 * controlled textarea contract while its data adapter supplies the workspace
 * submit lifecycle.
 * Sim snapshot: 48c59c8a70d647267200165ead35c39e067d9d59.
 */
export interface SimPromptEditorProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange" | "onSubmit"> {
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
  skills?: NativeSkill[];
  onSkillSelect?: (skill: NativeSkill) => void;
}

export const SimPromptEditor = forwardRef<HTMLTextAreaElement, SimPromptEditorProps>(function SimPromptEditor(
  { value, onValueChange, onSubmit, skills = [], onSkillSelect, className, ...props },
  ref,
) {
  const pendingCursorRef = useRef<number | null>(null);
  const skillsMenuRef = useRef<SimSkillsMenuHandle>(null);
  const [slashQuery, setSlashQuery] = useState<string | undefined>();

  const textarea = typeof ref === "object" && ref !== null ? ref.current : null;

  const resize = useCallback(() => {
    const textarea = typeof ref === "object" && ref !== null ? ref.current : null;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 192)}px`;
  }, [ref]);

  useLayoutEffect(() => resize(), [resize, value]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (skillsMenuRef.current && slashQuery !== undefined) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        skillsMenuRef.current.moveActive(event.key === "ArrowDown" ? 1 : -1);
        return;
      }
      if (event.key === "Enter" || (event.key === "Tab" && !event.shiftKey)) {
        if (skillsMenuRef.current.selectActive()) {
          event.preventDefault();
          return;
        }
      }
      if (event.key === "Escape") {
        event.preventDefault();
        skillsMenuRef.current.close();
        setSlashQuery(undefined);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
    props.onKeyDown?.(event);
  };

  const updateSlashMenu = (nextValue: string, nextCaret: number) => {
    const tokenStart = Math.max(nextValue.lastIndexOf(" ", nextCaret - 1), nextValue.lastIndexOf("\n", nextCaret - 1)) + 1;
    const token = nextValue.slice(tokenStart, nextCaret);
    if (!token.startsWith("/") || /\s/.test(token) || !skills.length || !onSkillSelect) {
      setSlashQuery(undefined);
      skillsMenuRef.current?.close();
      return;
    }
    setSlashQuery(token.slice(1));
    const target = typeof ref === "object" && ref !== null ? ref.current : null;
    if (target) {
      pendingCursorRef.current = nextCaret;
      const rect = target.getBoundingClientRect();
      skillsMenuRef.current?.open({ left: rect.left, top: rect.bottom });
    }
  };

  const handleSkillSelect = (skill: NativeSkill) => {
    const target = typeof ref === "object" && ref !== null ? ref.current : null;
    const caret = target?.selectionStart ?? value.length;
    const tokenStart = Math.max(value.lastIndexOf(" ", caret - 1), value.lastIndexOf("\n", caret - 1)) + 1;
    const nextValue = `${value.slice(0, tokenStart)}/${skill.id} ${value.slice(caret)}`;
    onValueChange(nextValue);
    setSlashQuery(undefined);
    onSkillSelect?.(skill);
    window.requestAnimationFrame(() => {
      const nextCaret = tokenStart + skill.id.length + 2;
      const node = typeof ref === "object" && ref !== null ? ref.current : null;
      node?.focus();
      node?.setSelectionRange(nextCaret, nextCaret);
    });
  };

  return (
    <>
      <textarea
        {...props}
        ref={ref}
        value={value}
        rows={1}
        onChange={(event) => {
          onValueChange(event.target.value);
          updateSlashMenu(event.target.value, event.target.selectionStart ?? event.target.value.length);
        }}
        onKeyDown={handleKeyDown}
        className={cn(
          "block max-h-[200px] min-h-[56px] w-full resize-none overflow-y-auto bg-transparent text-[14px] leading-6 tracking-[-0.015em] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-70",
          className,
        )}
      />
      {skills.length > 0 && onSkillSelect && (
        <SimSkillsMenuDropdown
          ref={skillsMenuRef}
          skills={skills}
          onSkillSelect={handleSkillSelect}
          onClose={() => setSlashQuery(undefined)}
          textareaRef={typeof ref === "object" && ref !== null ? ref : { current: textarea }}
          pendingCursorRef={pendingCursorRef}
          slashQuery={slashQuery}
        />
      )}
    </>
  );
});
