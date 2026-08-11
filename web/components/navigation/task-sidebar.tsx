"use client";

import Link from "next/link";
import { BookOpen, ChevronRight, Compass, MessageSquarePlus, PanelLeftClose, X } from "lucide-react";
import type { Mission, SessionListItem } from "@/lib/types";
import { Brand } from "@/components/brand";
import { cn } from "@/lib/utils";

export function TaskSidebar({
  sessions,
  missionById,
  currentId,
  mobile = false,
  onClose,
}: {
  sessions: SessionListItem[];
  missionById: Map<string, Mission>;
  currentId?: string;
  mobile?: boolean;
  onClose?: () => void;
}) {
  return (
    <aside className={cn(
      "home-sidebar flex h-full w-[248px] shrink-0 flex-col border-r border-[#e1e1e1] bg-[#f5f5f5] px-3 py-4 xl:w-[264px] 2xl:w-[280px]",
      mobile && "w-[min(86vw,340px)] shadow-2xl 2xl:w-[min(86vw,340px)]",
    )}>
      <div className="flex h-11 items-center justify-between px-2">
        <Brand />
        {onClose && (
          <button onClick={onClose} className="grid size-8 place-items-center rounded-lg hover:bg-black/5" aria-label="关闭任务列表">
            <X className="size-4" />
          </button>
        )}
      </div>

      <nav className="mt-8">
        <Link href="/" onClick={onClose} className="group flex h-12 items-center gap-3 rounded-xl bg-[#e6e6e6] px-3 text-[15px] font-medium transition-colors hover:bg-[#dedede]">
          <span className="grid size-8 place-items-center rounded-lg text-[var(--ink)]"><MessageSquarePlus className="size-[18px]" /></span>
          新建学习任务
        </Link>
        <Link href="/#courses" onClick={onClose} className="mt-1 flex h-11 items-center gap-3 rounded-xl px-3 text-[15px] text-[#343434] transition-colors hover:bg-black/[.045]">
          <span className="grid size-8 place-items-center"><Compass className="size-[18px]" /></span>
          发现课程
        </Link>
      </nav>

      <div className="mt-8 flex items-center gap-2 px-3 text-[15px] text-[var(--muted)]">
        <BookOpen className="size-[18px]" /> 我的课程
      </div>
      <div className="mt-2 flex-1 space-y-1 overflow-auto">
        {sessions.length === 0 && <div className="px-3 py-8 text-center text-sm text-[var(--muted-2)]">暂无课程</div>}
        {sessions.map((session) => {
          const mission = missionById.get(session.mission_id);
          return (
            <Link
              key={session.id}
              href={`/workspace/?id=${encodeURIComponent(session.id)}`}
              onClick={onClose}
              className={cn(
                "group flex items-center gap-2 rounded-xl px-3 py-3 transition-all hover:bg-black/[.045]",
                currentId === session.id && "bg-white",
              )}
            >
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{mission?.title ?? "学习课程"}</span>
              <ChevronRight className="size-4 text-[var(--muted-2)] opacity-0 transition-opacity group-hover:opacity-100" />
            </Link>
          );
        })}
      </div>
      <div className="mt-auto flex items-center gap-3 border-t border-black/[.06] px-3 pt-4 text-sm text-[var(--muted)]">
        <PanelLeftClose className="size-4" />
        <span>学习工作台</span>
      </div>
    </aside>
  );
}
