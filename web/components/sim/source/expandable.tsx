"use client";

import * as React from "react";
import * as CollapsiblePrimitive from "@radix-ui/react-collapsible";
import { cn } from "./lib/cn";

// Sim packages/emcn/src/components/expandable/expandable.tsx @ ce2dff3c.
interface ExpandableProps extends Omit<React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Root>, "open"> {
  expanded: boolean;
}

export const Expandable = React.forwardRef<React.ElementRef<typeof CollapsiblePrimitive.Root>, ExpandableProps>(
  ({ expanded, className, ...props }, ref) => <CollapsiblePrimitive.Root ref={ref} open={expanded} className={cn("w-full", className)} {...props} />,
);
Expandable.displayName = "Expandable";

export const ExpandableContent = React.forwardRef<React.ElementRef<typeof CollapsiblePrimitive.Content>, React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Content>>(
  ({ className, children, ...props }, ref) => (
    <CollapsiblePrimitive.Content ref={ref} className={cn("overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down", className)} {...props}>
      {children}
    </CollapsiblePrimitive.Content>
  ),
);
ExpandableContent.displayName = "ExpandableContent";
