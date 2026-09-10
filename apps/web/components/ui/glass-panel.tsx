import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const glassPanelVariants = cva(
  "relative transition-all duration-200",
  {
    variants: {
      variant: {
        default: "glass-panel",
        subtle: "glass-panel-subtle",
        card: "glass-card",
        strong: "glass-card shadow-elevated",
      },
      glow: {
        none: "",
        emerald: "glow-emerald",
        purple: "glow-purple",
        indigo: "glow-indigo",
      },
    },
    defaultVariants: {
      variant: "default",
      glow: "none",
    },
  }
);

export interface GlassPanelProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof glassPanelVariants> {}

const GlassPanel = React.forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ className, variant, glow, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(glassPanelVariants({ variant, glow, className }))}
        {...props}
      />
    );
  }
);
GlassPanel.displayName = "GlassPanel";

export { GlassPanel, glassPanelVariants };
