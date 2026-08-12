import type { ReactNode } from "react";
import { SimButton } from "./button";

/** Sim workspace resource-tab treatment used by the current resource panel. */
export function SimResourceTab({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon?: ReactNode; children: ReactNode }) {
  return <SimButton type="button" variant="quiet" size="sm" onClick={onClick} className={`h-full shrink-0 rounded-none border-b-2 px-2 text-[11px] ${active ? "border-[var(--brand)] text-[var(--text-primary)]" : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"}`}>{icon}{children}</SimButton>;
}
