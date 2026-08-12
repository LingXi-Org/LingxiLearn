"use client";

import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Home,
  LogIn,
  MoreHorizontal,
  Network,
  PanelLeft,
  Plus,
  Search,
  Shapes,
  Workflow,
} from "lucide-react";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import type { Mission, SessionListItem } from "@/lib/types";
import { cn } from "@/lib/utils";

type SidebarIcon = LucideIcon;

export interface SimMissionLink {
  mission: Mission;
  packId: string;
}

interface SimSidebarProps {
  sessions: SessionListItem[];
  missionById: Map<string, Mission>;
  missions?: SimMissionLink[];
  currentId?: string;
  loading?: boolean;
  starting?: string;
  onStartMission?: (missionId: string, packId: string) => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onClose?: () => void;
  className?: string;
}

/** Sim's sidebar geometry with LingxiLearn-owned navigation and data. */
export function SimSidebar({
  sessions,
  missionById,
  missions = [],
  currentId,
  loading = false,
  starting,
  onStartMission,
  collapsed = false,
  onToggleCollapsed,
  onClose,
  className,
}: SimSidebarProps) {
  const visibleSessions = sessions;

  return (
    <aside
      className={cn("sim-sidebar-container flex h-full w-full min-h-0 flex-col overflow-hidden bg-[var(--surface-1)] text-[var(--text-primary)]", className)}
      data-collapsed={collapsed || undefined}
      aria-label="灵犀智学工作区导航"
    >
      <div className="relative flex shrink-0 items-center px-2 pt-3">
        <div className={cn("flex h-[30px] min-w-0 flex-1 items-center gap-2 rounded-lg px-2", collapsed && "justify-center px-0")}>
          <img src="/logo_icon.svg" alt="" className="size-4 shrink-0" />
          <span className="sim-sidebar-label truncate text-[13px] font-medium">Lingxi</span>
        </div>
        <div className={cn("flex h-[30px] items-center gap-px overflow-hidden transition-all duration-200", collapsed && "w-0 opacity-0")}>
          <SidebarIconButton icon={Search} label="搜索" onClick={onClose} />
          <SidebarIconButton icon={PanelLeft} label="折叠侧栏" onClick={onToggleCollapsed} />
        </div>
        {collapsed && <SidebarIconButton icon={PanelLeft} label="展开侧栏" onClick={onToggleCollapsed} />}
      </div>

      <div className="mt-4 flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden [scrollbar-width:thin]">
        <div className="flex shrink-0 flex-col gap-[1px] px-2 pb-2">
          <SidebarNavLink href="/" icon={Home} collapsed={collapsed} onClick={onClose}>
            新对话
          </SidebarNavLink>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto border-t border-[var(--border)] px-2 pb-2 pt-2">
          <SidebarSection title="聊天" collapsed={collapsed} icon={Network}>
            {visibleSessions.length === 0 && !loading && <SidebarEmpty collapsed={collapsed}>暂无聊天记录</SidebarEmpty>}
            {loading && visibleSessions.length === 0 && <SidebarSkeletonRows count={2} collapsed={collapsed} />}
            {visibleSessions.slice(0, 8).map((session) => (
              <SidebarNavLink
                key={session.id}
                href={`/workspace/?id=${encodeURIComponent(session.id)}`}
                active={currentId === session.id}
                collapsed={collapsed}
                icon={Network}
                onClick={onClose}
              >
                <span className="sim-sidebar-label min-w-0 flex-1 truncate">{missionById.get(session.mission_id)?.title ?? "学习任务"}</span>
              </SidebarNavLink>
            ))}
          </SidebarSection>

          <SidebarSection
            title="工作流"
            collapsed={collapsed}
            icon={Workflow}
            action={
              <span className="flex items-center justify-center gap-2">
                <button type="button" className="grid size-5 place-items-center rounded-sm text-[var(--text-icon)] hover:bg-[var(--surface-hover)]" aria-label="更多工作流">
                  <MoreHorizontal className="size-[14px]" />
                </button>
                <Link href="/" onClick={onClose} className="grid size-5 place-items-center rounded-sm text-[var(--text-icon)] hover:bg-[var(--surface-hover)]" aria-label="新建工作流">
                  <Plus className="size-[16px]" />
                </Link>
              </span>
            }
          >
            {loading && missions.length === 0 && <SidebarSkeletonRows count={3} collapsed={collapsed} />}
            {!loading && missions.length === 0 && <SidebarEmpty collapsed={collapsed}>暂无工作流</SidebarEmpty>}
            {missions.slice(0, 8).map(({ mission, packId }) => {
              const content = (
                <>
                  <Workflow className="size-4 shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} />
                  <span className="sim-sidebar-label min-w-0 flex-1 truncate">{mission.title}</span>
                  {starting === mission.id && <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-[var(--brand-accent)]" />}
                  {!starting && <ChevronRight className="sim-sidebar-label size-3.5 shrink-0 text-[var(--text-icon)] opacity-0 transition-opacity group-hover:opacity-100" />}
                </>
              );
              const className = cn(
                "group flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[14px] text-[var(--text-body)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] disabled:pointer-events-none disabled:opacity-70",
                collapsed && "justify-center px-0",
              );
              return onStartMission ? (
                <button key={mission.id} type="button" data-testid={`start-mission-${mission.id}`} disabled={Boolean(starting)} onClick={() => onStartMission(mission.id, packId)} className={className}>
                  {content}
                </button>
              ) : (
                <Link key={mission.id} href="/" onClick={onClose} className={className}>{content}</Link>
              );
            })}
          </SidebarSection>
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-[1px] border-t border-[var(--border)] px-2 py-2">
        <SidebarNavButton icon={LogIn} collapsed={collapsed} onClick={onClose}>Sign in (placeholder)</SidebarNavButton>
        <SidebarNavButton icon={CircleHelp} collapsed={collapsed} onClick={onClose}>帮助</SidebarNavButton>
      </div>
    </aside>
  );
}

function SidebarSection({ title, icon: Icon, action, collapsed, children }: { title: string; icon: SidebarIcon; action?: ReactNode; collapsed: boolean; children: ReactNode }) {
  return (
    <section className="group/section flex flex-col">
      <div className="flex h-[18px] shrink-0 items-center">
        <div className={cn("flex h-full min-w-0 flex-1 items-center gap-2 px-2", collapsed && "justify-center px-0")}>
          <span className={cn("sim-sidebar-label min-w-0 truncate text-[12px] text-[var(--text-muted)]", collapsed && "hidden")}>{title}</span>
          {!collapsed && <ChevronDown className="size-3.5 shrink-0 text-[var(--text-icon)] opacity-0 transition-opacity group-hover/section:opacity-100" />}
          {collapsed && <Icon className="size-4 text-[var(--text-icon)]" strokeWidth={1.55} />}
        </div>
        {!collapsed && action && <div className="flex shrink-0 items-center pr-2">{action}</div>}
      </div>
      <div className="flex flex-col gap-[1px] pt-1.5">{children}</div>
    </section>
  );
}

function SidebarNavLink({ href, icon: Icon, active = false, collapsed = false, onClick, children }: { href: string; icon?: SidebarIcon; active?: boolean; collapsed?: boolean; onClick?: () => void; children: ReactNode }) {
  return (
    <Link href={href} onClick={onClick} className={cn("group flex h-[30px] items-center gap-2 rounded-lg px-2 text-[14px] text-[var(--text-body)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]", active && "bg-[var(--surface-active)] text-[var(--text-primary)]", collapsed && "justify-center px-0")}>
      {Icon && <Icon className="size-4 shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} />}
      <span className="sim-sidebar-label min-w-0 flex-1 truncate">{children}</span>
    </Link>
  );
}

function SidebarNavButton({ icon: Icon, collapsed = false, onClick, children }: { icon: SidebarIcon; collapsed?: boolean; onClick?: () => void; children: ReactNode }) {
  return (
    <button type="button" onClick={onClick} className={cn("group flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[14px] text-[var(--text-body)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]", collapsed && "justify-center px-0")}>
      <Icon className="size-4 shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} />
      <span className="sim-sidebar-label min-w-0 truncate">{children}</span>
    </button>
  );
}

function SidebarIconButton({ icon: Icon, label, onClick }: { icon: SidebarIcon; label: string; onClick?: () => void }) {
  return <button type="button" onClick={onClick} className="grid size-[30px] shrink-0 place-items-center rounded-lg text-[var(--text-icon)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]" aria-label={label} title={label}><Icon className="size-4" strokeWidth={1.45} /></button>;
}

function SidebarEmpty({ children, collapsed }: { children: ReactNode; collapsed: boolean }) {
  return <div className={cn("h-[30px] px-2 text-[12px] leading-[30px] text-[var(--text-muted)]", collapsed && "hidden")}>{children}</div>;
}

function SidebarSkeletonRows({ count, collapsed }: { count: number; collapsed: boolean }) {
  return <>{Array.from({ length: count }, (_, index) => <div key={index} className={cn("h-[30px] animate-pulse rounded-lg bg-[var(--surface-3)]", collapsed && "mx-auto w-7")} />)}</>;
}
