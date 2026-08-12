"use client";

import { Menu, X } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Mission, SessionListItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SimSidebar, type SimMissionLink } from "@/components/sim/sim-sidebar";

/** A one-shot flag used to animate the first route transition into the workspace. */
export const SIM_LAYOUT_TRANSITION_KEY = "lingxilearn.sim.layout-transition";
const SIDEBAR_COLLAPSED_KEY = "lingxilearn.sim.sidebar-collapsed";

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
 * Sim's web workspace chrome. The data and routes remain LingxiLearn-owned;
 * the surrounding geometry follows Sim's WorkspaceChrome: a 238px rail,
 * optional 51px icon rail, and an 8px-inset rounded content pane.
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    setSidebarCollapsed(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1");
  }, []);

  const toggleSidebar = () => {
    setSidebarCollapsed((collapsed) => {
      const next = !collapsed;
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
      return next;
    });
  };

  const sidebarProps = useMemo(
    () => ({
      sessions,
      missionById,
      missions,
      currentId,
      loading,
      starting,
      onStartMission,
    }),
    [currentId, loading, missionById, missions, onStartMission, sessions, starting],
  );

  return (
    <div className="sim-workspace-window-frame relative flex h-dvh min-h-0 w-full bg-[var(--bg)]">
      <div
        className={cn(
          "sim-sidebar-shell relative hidden h-full shrink-0 overflow-hidden md:block",
          sidebarCollapsed ? "w-[51px]" : "w-[238px]",
        )}
      >
        <SimSidebar
          {...sidebarProps}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={toggleSidebar}
        />
      </div>

      <div className="flex min-w-0 flex-1 flex-col p-2 pl-0">
        <div className="flex h-11 shrink-0 items-center border-b border-[var(--border)] bg-[var(--surface-1)] px-3 md:hidden">
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(true)}
            className="grid size-8 place-items-center rounded-lg text-[var(--text-icon)] hover:bg-[var(--surface-hover)]"
            aria-label="打开侧栏"
          >
            <Menu className="size-[18px]" />
          </button>
          <span className="ml-2 truncate text-[13px] font-medium">{title}</span>
        </div>
        <main className="min-h-0 flex-1 overflow-hidden rounded-[8px] border border-[var(--border)] bg-[var(--bg)]">
          {children}
        </main>
      </div>

      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 flex bg-black/20 md:hidden" onClick={() => setMobileSidebarOpen(false)}>
          <div className="relative h-full w-[238px] shadow-[var(--shadow-overlay)]" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(false)}
              className="absolute left-[246px] top-3 z-10 grid size-8 place-items-center rounded-lg bg-[var(--surface-1)] text-[var(--text-icon)] shadow-sm"
              aria-label="关闭侧栏"
            >
              <X className="size-4" />
            </button>
            <SimSidebar
              {...sidebarProps}
              collapsed={false}
              onToggleCollapsed={() => undefined}
              onClose={() => setMobileSidebarOpen(false)}
            />
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
