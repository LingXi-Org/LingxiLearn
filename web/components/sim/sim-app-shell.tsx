"use client";

import { Menu, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { Mission, SessionListItem } from "@/lib/types";
import { SimSidebar, type SimMissionLink } from "@/components/sim/sim-sidebar";

/** A one-shot flag used to animate the first route transition into the workspace. */
export const SIM_LAYOUT_TRANSITION_KEY = "lingxilearn.sim.layout-transition";

interface SimAppShellProps {
  children: ReactNode;
  title: string;
  sessions: SessionListItem[];
  missionById: Map<string, Mission>;
  missions?: SimMissionLink[];
  currentId?: string;
  loading?: boolean;
  starting?: string;
  onStartMission?: (missionId: string, packId: string) => void;
}

/**
 * Sim's workspace chrome: a persistent rail inside a softly inset app window.
 * Routes and data stay LingxiLearn-owned; only the shell geometry is source-
 * derived from Sim's workspace layout.
 */
export function SimAppShell({
  children,
  title,
  sessions,
  missionById,
  missions,
  currentId,
  loading,
  starting,
  onStartMission,
}: SimAppShellProps) {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const sidebarProps = {
    sessions,
    missionById,
    missions,
    currentId,
    loading,
    starting,
    onStartMission,
  };

  return (
    <div className="sim-desktop-backdrop h-dvh min-h-[560px] w-full overflow-hidden p-1.5 sm:p-2.5">
      <div className="sim-app-frame mx-auto flex h-full w-full max-w-[2400px] overflow-hidden rounded-[14px] border border-[#d4d4d4] bg-[var(--surface-1)] shadow-[0_2px_12px_rgba(0,0,0,.14)]">
        <div className="hidden h-full md:flex">
          <SimSidebar {...sidebarProps} />
        </div>

        <div className="flex min-w-0 flex-1 flex-col bg-[var(--surface-1)]">
          <div className="flex h-11 shrink-0 items-center border-b border-[var(--border)] bg-[var(--surface-1)] px-3 md:hidden">
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(true)}
              className="grid size-8 place-items-center rounded-lg text-[var(--text-icon)] hover:bg-[var(--surface-5)]"
              aria-label="打开侧栏"
            >
              <Menu className="size-[18px]" />
            </button>
            <span className="ml-2 truncate text-[13px] font-medium">{title}</span>
          </div>
          <div className="min-h-0 flex-1 md:p-2 md:pl-0">
            <main className="h-full min-h-0 overflow-hidden rounded-[8px] border border-[var(--border)] bg-[var(--bg)]">{children}</main>
          </div>
        </div>
      </div>

      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 flex bg-black/20 md:hidden" onClick={() => setMobileSidebarOpen(false)}>
          <div className="h-full max-w-[86vw] shadow-[var(--shadow-overlay)]" onClick={(event) => event.stopPropagation()}>
            <div className="absolute left-[clamp(238px,86vw,360px)] top-3">
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(false)}
                className="grid size-8 place-items-center rounded-lg bg-[var(--surface-1)] text-[var(--text-icon)] shadow-sm"
                aria-label="关闭侧栏"
              >
                <X className="size-4" />
              </button>
            </div>
            <SimSidebar {...sidebarProps} onClose={() => setMobileSidebarOpen(false)} className="w-[min(86vw,320px)]" />
          </div>
        </div>
      )}
    </div>
  );
}

export function markSimLayoutTransition() {
  if (typeof window !== "undefined") window.sessionStorage.setItem(SIM_LAYOUT_TRANSITION_KEY, "1");
}

export function consumeSimLayoutTransition() {
  if (typeof window === "undefined") return false;
  const shouldAnimate = window.sessionStorage.getItem(SIM_LAYOUT_TRANSITION_KEY) === "1";
  if (shouldAnimate) window.sessionStorage.removeItem(SIM_LAYOUT_TRANSITION_KEY);
  return shouldAnimate;
}
