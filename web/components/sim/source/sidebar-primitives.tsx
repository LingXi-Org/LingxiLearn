import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "./lib/cn";

/** Sidebar primitives extracted from Sim's workspace sidebar at ce2dff3c. */
const itemClass = "group flex h-[30px] items-center gap-2 rounded-lg px-2 text-[14px] text-[var(--text-body)] outline-none transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] focus-visible:bg-[var(--surface-hover)] focus-visible:text-[var(--text-primary)] focus-visible:ring-1 focus-visible:ring-[var(--ring)] disabled:pointer-events-none disabled:opacity-60";

export function SimSidebarLink({ href, icon: Icon, collapsed = false, onClick, children }: { href: string; icon: LucideIcon; collapsed?: boolean; onClick?: () => void; children: ReactNode }) {
  return <Link href={href} onClick={onClick} className={cn(itemClass, collapsed && "justify-center px-0")}><Icon className="size-4 shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} /><span className="sim-sidebar-label min-w-0 flex-1 truncate">{children}</span></Link>;
}

export function SimSidebarButton({ icon: Icon, collapsed = false, disabled, onClick, className, children }: { icon: LucideIcon; collapsed?: boolean; disabled?: boolean; onClick?: () => void; className?: string; children: ReactNode }) {
  return <button type="button" disabled={disabled} onClick={onClick} className={cn(itemClass, "w-full text-left", collapsed && "justify-center px-0", className)}><Icon className="size-4 shrink-0 text-[var(--text-icon)]" strokeWidth={1.55} /><span className="sim-sidebar-label min-w-0 truncate">{children}</span></button>;
}

export function SimSidebarIconButton({ icon: Icon, label, onClick, className, pressed }: { icon: LucideIcon; label: string; onClick?: () => void; className?: string; pressed?: boolean }) {
  return <button type="button" onClick={onClick} className={cn("grid size-[30px] shrink-0 place-items-center rounded-lg text-[var(--text-icon)] outline-none transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] focus-visible:bg-[var(--surface-hover)] focus-visible:text-[var(--text-primary)] focus-visible:ring-1 focus-visible:ring-[var(--ring)]", className)} aria-label={label} title={label} aria-pressed={pressed}><Icon className="size-4" strokeWidth={1.45} /></button>;
}
