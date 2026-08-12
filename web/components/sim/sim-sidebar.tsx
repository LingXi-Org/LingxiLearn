"use client";

import Link from "next/link";
import {
  CalendarDays,
  ChevronRight,
  CircleHelp,
  Database,
  FileText,
  Home,
  LogOut,
  MoreHorizontal,
  Network,
  PanelLeft,
  Plus,
  Search,
  Settings,
  Shapes,
  Table2,
  Workflow,
} from "lucide-react";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import type { Mission, SessionListItem } from "@/lib/types";
import { Brand } from "@/components/brand";
import { isCatalogueMissionVisible } from "@/lib/catalogue-visibility";
import { cn } from "@/lib/utils";
import { useLingxiIdentity } from "@/components/auth/lingxi-identity-provider";

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
  onClose?: () => void;
  className?: string;
}

/**
 * Sim's workspace navigation shape, kept local so LingxiLearn can retain its
 * own routes and session data while using the same persistent workspace rail.
 */
export function SimSidebar({
  sessions,
  missionById,
  missions = [],
  currentId,
  loading = false,
  starting,
  onStartMission,
  onClose,
  className,
}: SimSidebarProps) {
  const { configured, authenticated, login, logout } = useLingxiIdentity();
  const visibleSessions = sessions.filter((session) => isCatalogueMissionVisible(session.mission_id));

  return (
    <aside
      className={cn(
        "flex h-full min-h-0 w-[clamp(238px,19vw,360px)] shrink-0 flex-col bg-[var(--surface-1)] text-[var(--text-primary)]",
        className,
      )}
      aria-label="灵犀智学工作区导航"
    >
      <div className="flex h-[58px] shrink-0 items-center gap-2 border-b border-[var(--border)] px-3.5">
        <Brand iconClassName="size-7" className="min-w-0 flex-1" />
        <button
          type="button"
          className="grid size-8 shrink-0 place-items-center rounded-lg text-[var(--text-icon)] transition-colors hover:bg-[var(--surface-5)] hover:text-[var(--text-primary)]"
          aria-label="折叠侧栏"
          title="折叠侧栏"
          onClick={onClose}
        >
          <PanelLeft className="size-[18px]" strokeWidth={1.65} />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 [scrollbar-width:thin]">
        <nav className="space-y-1" aria-label="主导航">
          <SidebarNavLink href="/" icon={Home} onClick={onClose}>
            新对话
          </SidebarNavLink>
          <SidebarNavButton icon={Search} onClick={onClose}>
            搜索
          </SidebarNavButton>
          <SidebarNavButton icon={Network} onClick={onClose}>
            集成
          </SidebarNavButton>
        </nav>

        <SidebarSection title="聊天" className="mt-5">
          {visibleSessions.length === 0 && !loading && (
            <p className="px-2 py-1 text-[11px] leading-5 text-[var(--text-muted)]">暂无聊天记录</p>
          )}
          {loading && visibleSessions.length === 0 && <SidebarSkeletonRows count={2} />}
          {visibleSessions.slice(0, 8).map((session) => (
            <SidebarNavLink
              key={session.id}
              href={`/workspace/?id=${encodeURIComponent(session.id)}`}
              active={currentId === session.id}
              onClick={onClose}
            >
              <span className="min-w-0 flex-1 truncate">{missionById.get(session.mission_id)?.title ?? "学习任务"}</span>
            </SidebarNavLink>
          ))}
        </SidebarSection>

        <SidebarSection title="工作区" className="mt-5">
          <SidebarNavButton icon={Table2} onClick={onClose}>
            表格
          </SidebarNavButton>
          <SidebarNavButton icon={FileText} onClick={onClose}>
            文件
          </SidebarNavButton>
          <SidebarNavButton icon={Database} onClick={onClose}>
            知识库
          </SidebarNavButton>
          <SidebarNavButton icon={CalendarDays} onClick={onClose}>
            定时任务
          </SidebarNavButton>
          <SidebarNavButton icon={Shapes} onClick={onClose}>
            日志
          </SidebarNavButton>
        </SidebarSection>

        <SidebarSection
          title="工作流"
          className="mt-5"
          action={
            <span className="flex items-center gap-0.5">
              <button type="button" className="grid size-6 place-items-center rounded-md hover:bg-[var(--surface-5)]" aria-label="更多工作流">
                <MoreHorizontal className="size-4" />
              </button>
              <Link href="/" onClick={onClose} className="grid size-6 place-items-center rounded-md hover:bg-[var(--surface-5)]" aria-label="新建工作流">
                <Plus className="size-4" />
              </Link>
            </span>
          }
        >
          {loading && missions.length === 0 && <SidebarSkeletonRows count={3} />}
          {!loading && missions.length === 0 && (
            <p className="px-2 py-1 text-[11px] leading-5 text-[var(--text-muted)]">暂无工作流</p>
          )}
          {missions.slice(0, 8).map(({ mission, packId }) => {
            const content = (
              <>
                <Workflow className="size-[17px] shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} />
                <span className="min-w-0 flex-1 truncate">{mission.title}</span>
                {starting === mission.id && <span className="size-3 shrink-0 animate-pulse rounded-full bg-[var(--brand)]" />}
                {!starting && <ChevronRight className="size-3.5 shrink-0 text-[var(--text-icon)] opacity-0 transition-opacity group-hover:opacity-100" />}
              </>
            );

            if (onStartMission) {
              return (
                <button
                  key={mission.id}
                  type="button"
                  data-testid={`start-mission-${mission.id}`}
                  disabled={Boolean(starting)}
                  onClick={() => onStartMission(mission.id, packId)}
                  className="group flex min-h-[34px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-5)] hover:text-[var(--text-primary)] disabled:cursor-wait disabled:opacity-60"
                >
                  {content}
                </button>
              );
            }

            return (
              <Link
                key={mission.id}
                href="/"
                onClick={onClose}
                className="group flex min-h-[34px] items-center gap-2 rounded-lg px-2 text-[13px] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-5)] hover:text-[var(--text-primary)]"
              >
                {content}
              </Link>
            );
          })}
        </SidebarSection>
      </div>

      <div className="shrink-0 border-t border-[var(--border)] px-3 py-2">
        {configured && <button type="button" onClick={() => void (authenticated ? logout() : login())} className="mb-1 flex min-h-[36px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-5)] hover:text-[var(--text-primary)]">{authenticated ? <LogOut className="size-[18px] text-[var(--text-icon)]" strokeWidth={1.55} /> : <span className="grid size-[18px] place-items-center rounded-full bg-[var(--brand)] text-[10px] text-white">身</span>}{authenticated ? "退出 LingxiIdentity" : "登录 LingxiIdentity"}</button>}
        <SidebarNavButton icon={CircleHelp} onClick={onClose}>
          帮助
        </SidebarNavButton>
        <SidebarNavButton icon={Settings} onClick={onClose}>
          设置
        </SidebarNavButton>
      </div>
    </aside>
  );
}

function SidebarSection({ title, action, className, children }: { title: string; action?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <section className={className}>
      <div className="flex h-7 items-center justify-between px-2 text-[12px] text-[var(--text-muted)]">
        <h2>{title}</h2>
        {action}
      </div>
      <div className="space-y-0.5">{children}</div>
    </section>
  );
}

function SidebarNavLink({ href, icon: Icon, active = false, onClick, children }: { href: string; icon?: SidebarIcon; active?: boolean; onClick?: () => void; children: ReactNode }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "group flex min-h-[36px] items-center gap-2 rounded-lg px-2 text-[13px] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-5)] hover:text-[var(--text-primary)]",
        active && "bg-[var(--surface-active)] text-[var(--text-primary)]",
      )}
    >
      {Icon && <Icon className="size-[18px] shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} />}
      {children}
    </Link>
  );
}

function SidebarNavButton({ icon: Icon, onClick, children }: { icon: SidebarIcon; onClick?: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[36px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-5)] hover:text-[var(--text-primary)]"
    >
      <Icon className="size-[18px] shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} />
      {children}
    </button>
  );
}

function SidebarSkeletonRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="h-[34px] animate-pulse rounded-lg bg-[var(--surface-2)]" />
      ))}
    </>
  );
}
