import * as React from "react";

import { cn } from "@/lib/utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  shimmer?: boolean;
}

function Skeleton({ className, shimmer = false, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "rounded-md bg-muted/60 motion-reduce:animate-none",
        shimmer
          ? "bg-gradient-to-r from-muted/30 via-muted/70 to-muted/30 bg-[length:200%_100%] animate-shimmer"
          : "animate-pulse",
        className
      )}
      {...props}
    />
  );
}

export { Skeleton };
