import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./lib/cn";

/**
 * Copied from Sim's `packages/emcn/src/components/button/button.tsx`.
 * The component is kept source-compatible while its surrounding data flow is
 * supplied by LingxiLearn.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center transition-colors disabled:pointer-events-none disabled:opacity-70 outline-none focus:outline-none focus-visible:outline-none rounded-[5px]",
  {
    variants: {
      variant: {
        default: "text-[var(--text-secondary)] hover:bg-[var(--surface-6)] bg-[var(--surface-4)] border border-[var(--border)]",
        active: "bg-[var(--surface-5)] text-[var(--text-primary)] border border-[var(--border)]",
        outline: "text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--text-muted)] bg-transparent",
        primary: "bg-[var(--text-primary)] text-[var(--text-inverse)] hover:bg-[var(--text-body)]",
        ghost: "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
        quiet: "text-[var(--text-secondary)] hover:bg-[var(--surface-active)]",
      },
      size: {
        sm: "px-1.5 py-1 text-[length:11px]",
        md: "px-2 py-1.5 text-[length:12px]",
        icon: "size-[20px] rounded-sm p-0 [&_svg]:[stroke-width:1.25]",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export interface SimButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export const SimButton = forwardRef<HTMLButtonElement, SimButtonProps>(function SimButton({ className, variant, size, ...props }, ref) {
  return <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
});
