import type { ComponentPropsWithoutRef, ElementType } from "react";
import { cn } from "./lib/cn";
import styles from "./shimmer-text.module.css";

// Sim apps/sim/components/ui/shimmer-text.tsx @ ce2dff3c.
type ShimmerTextProps<T extends ElementType = "span"> = { as?: T; children: React.ReactNode; className?: string } & Omit<ComponentPropsWithoutRef<T>, "as" | "children" | "className">;

export function ShimmerText<T extends ElementType = "span">({ as, children, className, ...props }: ShimmerTextProps<T>) {
  const Comp = as ?? "span";
  return <Comp className={cn(styles.shimmer, className)} {...props}>{children}</Comp>;
}
