import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-xl border p-4 text-sm [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground [&>svg~*]:pl-7",
  {
    variants: {
      variant: {
        default: "bg-card text-foreground border-border",
        destructive:
          "border-[oklch(0.65_0.2_25/0.4)] bg-[oklch(0.65_0.2_25/0.12)] text-[var(--color-error-red)] [&>svg]:text-[var(--color-error-red)]",
        ai: "border-[oklch(0.60_0.22_290/0.4)] bg-[oklch(0.60_0.22_290/0.10)] text-purple-200 [&>svg]:text-[var(--accent-purple)] shadow-[0_0_12px_oklch(0.60_0.22_290/0.10)]",
        success:
          "border-[oklch(0.65_0.19_145/0.4)] bg-[oklch(0.65_0.19_145/0.10)] text-[var(--color-success-green)] [&>svg]:text-[var(--color-success-green)]",
        warning:
          "border-[oklch(0.75_0.15_75/0.4)] bg-[oklch(0.75_0.15_75/0.10)] text-[var(--color-warning-amber)] [&>svg]:text-[var(--color-warning-amber)]",
        info: "border-[oklch(0.65_0.15_250/0.4)] bg-[oklch(0.65_0.15_250/0.10)] text-[var(--color-info-blue)] [&>svg]:text-[var(--color-info-blue)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>
>(({ className, variant, ...props }, ref) => (
  <div
    ref={ref}
    role="alert"
    className={cn(alertVariants({ variant }), className)}
    {...props}
  />
));
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    className={cn("mb-1 font-semibold leading-none tracking-tight", className)}
    {...props}
  />
));
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("text-sm [&_p]:leading-relaxed text-muted-foreground", className)}
    {...props}
  />
));
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };
