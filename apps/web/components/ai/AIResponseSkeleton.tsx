"use client";

import * as React from "react";
import { Cpu, Sparkles } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";

export function AIResponseSkeleton() {
  return (
    <div className="flex flex-col gap-5 p-6 animate-fade-in motion-reduce:animate-none">
      {/* Processing Status Banner */}
      <Card variant="ai" className="p-4 border-[var(--accent-purple)]/30">
        <div className="flex items-center gap-3">
          <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-purple)]/20 text-[var(--accent-purple)] border border-[var(--accent-purple)]/40">
            <Cpu className="h-4 w-4 animate-pulse motion-reduce:animate-none" />
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent-purple)] opacity-75 motion-reduce:animate-none" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--accent-purple)]" />
            </span>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-1.5">
                <Sparkles className="h-3 w-3 text-[var(--accent-purple)]" />
                AI Diagnostic Engine Active
              </h4>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Disassembling compiler error cascades &amp; cross-referencing MCU register maps...
            </p>
          </div>
        </div>
      </Card>

      {/* Observed Problem Skeleton */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton shimmer className="h-16 w-full" />
      </div>

      {/* Likely Causes Skeleton */}
      <div className="space-y-2.5">
        <Skeleton className="h-4 w-28" />
        <div className="space-y-2">
          <Skeleton shimmer className="h-12 w-full" />
          <Skeleton shimmer className="h-12 w-full" />
        </div>
      </div>

      {/* Recommended Steps Skeleton */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-40" />
        <div className="space-y-1.5">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-5 w-5/6" />
          <Skeleton className="h-5 w-2/3" />
        </div>
      </div>

      {/* Proposed Fix Code Skeleton */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-36" />
        <Skeleton shimmer className="h-28 w-full rounded-lg" />
      </div>
    </div>
  );
}
