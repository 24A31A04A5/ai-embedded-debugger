import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-primary/30 bg-primary/20 text-primary shadow-sm",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        destructive:
          "border-[oklch(0.65_0.2_25/0.3)] bg-[oklch(0.65_0.2_25/0.15)] text-[var(--color-error-red)]",
        error:
          "border-[oklch(0.65_0.2_25/0.3)] bg-[oklch(0.65_0.2_25/0.15)] text-[var(--color-error-red)]",
        outline: "text-foreground border-border",
        ai: "border-[oklch(0.60_0.22_290/0.3)] bg-[oklch(0.60_0.22_290/0.15)] text-[var(--accent-purple)] shadow-[0_0_8px_oklch(0.60_0.22_290/0.15)]",
        success:
          "border-[oklch(0.65_0.19_145/0.3)] bg-[oklch(0.65_0.19_145/0.15)] text-[var(--color-success-green)]",
        warning:
          "border-[oklch(0.75_0.15_75/0.3)] bg-[oklch(0.75_0.15_75/0.15)] text-[var(--color-warning-amber)]",
        info: "border-[oklch(0.65_0.15_250/0.3)] bg-[oklch(0.65_0.15_250/0.15)] text-[var(--color-info-blue)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
