"use client";

import { CircleHelp, Home, LogIn, LogOut, Moon, PanelLeft, Puzzle, Search, Sun, Workflow, X } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { AgentTaskListItem, NativeSkill } from "@/lib/types";
import { useOidcAdapter } from "@/components/auth/oidc-adapter";
import { SimSidebarButton, SimSidebarIconButton, SimSidebarLink } from "@/components/sim/source/sidebar-primitives";
import { useTheme } from "@/components/theme/theme-provider";

interface SimSidebarProps {
  currentTaskId?: string;
  taskStatus?: string;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onClose?: () => void;
}

export function SimSidebar({ currentTaskId, taskStatus, collapsed = false, onToggleCollapsed, onClose }: SimSidebarProps) {
  const { configured, isAuthenticated, isLoading, signIn, signOut } = useOidcAdapter();
  const { theme, toggleTheme } = useTheme();
  const [tasks, setTasks] = useState<AgentTaskListItem[]>([]);
  const [skills, setSkills] = useState<NativeSkill[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  useEffect(() => {
    if (configured && !isAuthenticated) {
      setTasks([]);
      return;
    }
    let active = true;
    const refresh = () => void api.agentTasks().then(({ tasks: next }) => {
      if (active) setTasks(next);
    }).catch(() => {
      // The workspace remains usable when history is temporarily unavailable.
    });
    refresh();
    const timer = window.setInterval(refresh, 15_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [configured, currentTaskId, isAuthenticated]);
  useEffect(() => {
    let active = true;
    void api.skills().then(({ skills: next }) => { if (active) setSkills(next); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  const handleAuth = () => void (isAuthenticated ? signOut() : signIn());
  const query = searchText.trim().toLocaleLowerCase();
  const matchingTasks = tasks.filter((item) => `${item.intent?.topic || ""} ${item.prompt}`.toLocaleLowerCase().includes(query));
  const matchingSkills = skills.filter((skill) => `${skill.display_name} ${skill.id} ${skill.description}`.toLocaleLowerCase().includes(query));
  return (
    <aside className="sim-sidebar-container flex h-full w-full min-h-0 flex-col overflow-hidden bg-[var(--surface-1)] text-[var(--text-primary)]" data-collapsed={collapsed || undefined} aria-label="灵犀 Agent 工作区导航">
      <div className="relative flex shrink-0 items-center px-2 pt-3">
        <div className={cn("flex h-[30px] min-w-0 flex-1 items-center gap-2 rounded-lg px-2", collapsed && "justify-center px-0")}>
          {!collapsed && <><img src="/logo_icon_black.svg" alt="" className="size-4 shrink-0 dark:hidden" /><img src="/logo_icon_white.svg" alt="" className="hidden size-4 shrink-0 dark:block" /></>}
          <span className="sim-sidebar-label truncate text-[13px] font-medium">Lingxi</span>
        </div>
        {!collapsed && <SimSidebarIconButton icon={PanelLeft} label="折叠侧栏" onClick={onToggleCollapsed} />}
        {collapsed && <SimSidebarIconButton icon={PanelLeft} label="展开侧栏" onClick={onToggleCollapsed} />}
      </div>
      <div className="mt-4 flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto border-t border-[var(--border)] px-2 pb-2 pt-3">
        <SimSidebarLink href="/" icon={Home} collapsed={collapsed} onClick={onClose}>新问题</SimSidebarLink>
        {collapsed && <div className="space-y-0.5">
          <SimSidebarIconButton icon={Search} label="搜索" onClick={() => { onToggleCollapsed?.(); setSearchOpen(true); }} />
          <SimSidebarLink href="/workspace/?panel=skills" icon={Puzzle} collapsed onClick={onClose}>Skills</SimSidebarLink>
        </div>}
        {!collapsed && <div className="space-y-1">
          {searchOpen ? <div className="flex h-[30px] items-center gap-2 rounded-lg bg-[var(--surface-hover)] px-2">
            <Search className="size-4 shrink-0 text-[var(--text-icon)]" />
            <input autoFocus value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="搜索对话和 Skills" className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-muted)]" aria-label="搜索对话和 Skills" />
            <button type="button" onClick={() => { setSearchOpen(false); setSearchText(""); }} className="text-[var(--text-muted)]" aria-label="关闭搜索"><X className="size-3.5" /></button>
          </div> : <SimSidebarButton icon={Search} onClick={() => setSearchOpen(true)}>搜索</SimSidebarButton>}
          {searchOpen && query && <div className="max-h-56 space-y-3 overflow-y-auto rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-2 text-[11px] shadow-sm">
            <SearchResults title="对话" empty="没有匹配的对话" items={matchingTasks.map((item) => ({ id: item.id, label: item.intent?.topic || item.prompt, href: `/workspace/?task=${encodeURIComponent(item.id)}` }))} onClick={onClose} />
            <SearchResults title="Skills" empty="没有匹配的 Skill" items={matchingSkills.map((skill) => ({ id: skill.id, label: skill.display_name, href: `/workspace/?panel=skills&skill=${encodeURIComponent(skill.id)}` }))} onClick={onClose} />
          </div>}
        </div>}
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
        {tasks.length > 0 && (
          <section className="border-t border-[var(--border)] pt-3">
            {!collapsed && <p className="px-2 text-[11px] text-[var(--text-muted)]">历史对话</p>}
            <div className="mt-1 space-y-0.5">
              {tasks.map((item) => {
                const title = item.intent?.topic || item.prompt || "未命名对话";
                const href = `/workspace/?task=${encodeURIComponent(item.id)}`;
                return <SimSidebarLink key={item.id} href={href} icon={Workflow} collapsed={collapsed} onClick={onClose}>{title}</SimSidebarLink>;
              })}
            </div>
          </section>
        )}
        {!collapsed && <section className="border-t border-[var(--border)] pt-3">
          <p className="px-2 text-[11px] text-[var(--text-muted)]">原生组件</p>
          <div className="mt-1">
            <SimSidebarLink href="/workspace/?panel=skills" icon={Puzzle} collapsed={collapsed} onClick={onClose}>Skills</SimSidebarLink>
          </div>
        </section>}
      </div>
      <div className={cn("flex shrink-0 border-t border-[var(--border)] px-2 pt-[9px] pb-2", collapsed ? "flex-col-reverse gap-[1px]" : "items-center gap-[1px]")}>
        {configured && <div className={cn(!collapsed && "min-w-0 flex-1")}><SimSidebarButton icon={isAuthenticated ? LogOut : LogIn} collapsed={collapsed} disabled={isLoading} onClick={handleAuth} className={!collapsed ? "max-w-full" : undefined}>{isLoading ? "处理中…" : isAuthenticated ? "退出登录" : "登录 / 注册"}</SimSidebarButton></div>}
        <SimSidebarIconButton icon={theme === "dark" ? Sun : Moon} label={theme === "dark" ? "切换到浅色主题" : "切换到深色主题"} onClick={toggleTheme} pressed={theme === "dark"} />
        <SimSidebarIconButton icon={CircleHelp} label="帮助" onClick={onClose} />
      </div>
    </aside>
  );
}

function SearchResults({ title, empty, items, onClick }: { title: string; empty: string; items: Array<{ id: string; label: string; href: string }>; onClick?: () => void }) {
  return <div><p className="mb-1 px-1 text-[10px] font-medium text-[var(--text-muted)]">{title}</p>{items.length ? items.slice(0, 8).map((item) => <SimSidebarLink key={item.id} href={item.href} icon={Workflow} onClick={onClick}>{item.label}</SimSidebarLink>) : <p className="px-1 text-[11px] text-[var(--text-muted)]">{empty}</p>}</div>;
}

function statusLabel(status?: string) {
  return status === "completed" ? "完成" : status === "partial" ? "部分完成" : status === "failed" ? "失败" : status === "running" ? "执行中" : "等待";
}
