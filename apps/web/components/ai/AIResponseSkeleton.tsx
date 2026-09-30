"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export function AIResponseSkeleton() {
  return (
    <div className="space-y-5 p-4" aria-busy="true">
      <div className="flex items-center gap-2.5 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--accent-purple)] motion-reduce:animate-none" />
        <span>Correlating source, compiler output, serial logs and datasheets…</span>
      </div>

      <div className="space-y-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton shimmer className="h-12 w-full" />
      </div>

      <div className="space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-2 w-28" />
      </div>

      <div className="space-y-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-2/3" />
      </div>

      <div className="space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton shimmer className="h-24 w-full" />
      </div>
    </div>
  );
}
