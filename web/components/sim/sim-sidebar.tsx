"use client";

import Link from "next/link";
import { CircleHelp, Home, LogIn, LogOut, PanelLeft, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useOidcAdapter } from "@/components/auth/oidc-adapter";

interface SimSidebarProps {
  currentTaskId?: string;
  taskStatus?: string;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onClose?: () => void;
}

export function SimSidebar({ currentTaskId, taskStatus, collapsed = false, onToggleCollapsed, onClose }: SimSidebarProps) {
  const { configured, isAuthenticated, isLoading, signIn, signOut } = useOidcAdapter();
  const handleAuth = () => void (isAuthenticated ? signOut() : signIn());
  return (
    <aside className="sim-sidebar-container flex h-full w-full min-h-0 flex-col overflow-hidden bg-[var(--surface-1)] text-[var(--text-primary)]" data-collapsed={collapsed || undefined} aria-label="灵犀 Agent 工作区导航">
      <div className="relative flex shrink-0 items-center px-2 pt-3">
        <div className={cn("flex h-[30px] min-w-0 flex-1 items-center gap-2 rounded-lg px-2", collapsed && "justify-center px-0")}>
          <img src="/logo_icon.svg" alt="" className="size-4 shrink-0" />
          <span className="sim-sidebar-label truncate text-[13px] font-medium">Lingxi</span>
        </div>
        {!collapsed && <SidebarIconButton icon={PanelLeft} label="折叠侧栏" onClick={onToggleCollapsed} />}
        {collapsed && <SidebarIconButton icon={PanelLeft} label="展开侧栏" onClick={onToggleCollapsed} />}
      </div>
      <div className="mt-4 flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto border-t border-[var(--border)] px-2 pb-2 pt-3">
        <SidebarNavLink href="/" icon={Home} collapsed={collapsed} onClick={onClose}>新问题</SidebarNavLink>
        {currentTaskId && (
          <section className="border-t border-[var(--border)] pt-3">
            {!collapsed && <p className="px-2 text-[11px] text-[var(--text-muted)]">当前任务</p>}
            <div className={cn("mt-1 flex items-center gap-2 rounded-lg px-2 py-2 text-xs", collapsed && "justify-center px-0")} title={currentTaskId}>
              <Workflow className="size-4 shrink-0 text-[var(--brand)]" />
              {!collapsed && <span className="min-w-0 flex-1 truncate">{currentTaskId}</span>}
              {!collapsed && <span className="shrink-0 text-[10px] text-[var(--text-muted)]">{statusLabel(taskStatus)}</span>}
            </div>
          </section>
        )}
      </div>
      <div className="flex shrink-0 flex-col gap-[1px] border-t border-[var(--border)] px-2 py-2">
        {configured && <SidebarNavButton icon={isAuthenticated ? LogOut : LogIn} collapsed={collapsed} disabled={isLoading} onClick={handleAuth}>{isLoading ? "处理中…" : isAuthenticated ? "退出登录" : "登录 / 注册"}</SidebarNavButton>}
        <SidebarNavButton icon={CircleHelp} collapsed={collapsed}>帮助</SidebarNavButton>
      </div>
    </aside>
  );
}

function statusLabel(status?: string) {
  return status === "completed" ? "完成" : status === "partial" ? "部分完成" : status === "failed" ? "失败" : status === "running" ? "执行中" : "等待";
}

function SidebarNavLink({ href, icon: Icon, collapsed = false, onClick, children }: { href: string; icon: LucideIcon; collapsed?: boolean; onClick?: () => void; children: ReactNode }) {
  return <Link href={href} onClick={onClick} className={cn("group flex h-[30px] items-center gap-2 rounded-lg px-2 text-[14px] text-[var(--text-body)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]", collapsed && "justify-center px-0")}><Icon className="size-4 shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} /><span className="sim-sidebar-label min-w-0 flex-1 truncate">{children}</span></Link>;
}

function SidebarNavButton({ icon: Icon, collapsed = false, disabled, onClick, children }: { icon: LucideIcon; collapsed?: boolean; disabled?: boolean; onClick?: () => void; children: ReactNode }) {
  return <button type="button" disabled={disabled} onClick={onClick} className={cn("group flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[14px] text-[var(--text-body)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]", collapsed && "justify-center px-0")}><Icon className="size-4 shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} /><span className="sim-sidebar-label min-w-0 truncate">{children}</span></button>;
}

function SidebarIconButton({ icon: Icon, label, onClick }: { icon: LucideIcon; label: string; onClick?: () => void }) {
  return <button type="button" onClick={onClick} className="grid size-[30px] shrink-0 place-items-center rounded-lg text-[var(--text-icon)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]" aria-label={label} title={label}><Icon className="size-4" strokeWidth={1.45} /></button>;
}
