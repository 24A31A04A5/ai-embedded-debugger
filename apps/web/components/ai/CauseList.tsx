"use client";

import * as React from "react";
import { type LikelyCause } from "./types";

interface CauseListProps {
  causes: LikelyCause[];
  rootCauseSummary?: string | null;
  confidenceLevel?: "high" | "medium" | "low" | null;
}

const PLAUSIBILITY: Record<LikelyCause["plausibility"], { label: string; className: string }> = {
  high: { label: "High", className: "text-[var(--color-error-red)] bg-[var(--color-error-red)]/10" },
  medium: { label: "Medium", className: "text-[var(--color-warning-amber)] bg-[var(--color-warning-amber)]/10" },
  low: { label: "Low", className: "text-muted-foreground bg-white/[0.06]" },
};

export function CauseList({ causes, rootCauseSummary, confidenceLevel }: CauseListProps) {
  if ((!causes || causes.length === 0) && !rootCauseSummary) return null;

  return (
    <div className="space-y-2">
      {rootCauseSummary && (
        <div className="border-l-2 border-[var(--accent-purple)] pl-3">
          <p className="text-xs font-medium leading-relaxed text-foreground">{rootCauseSummary}</p>
          {confidenceLevel && (
            <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">{confidenceLevel} confidence</p>
          )}
        </div>
      )}
      <ul className="space-y-1.5">
        {causes.map((item, idx) => {
          const meta = PLAUSIBILITY[item.plausibility] ?? PLAUSIBILITY.low;
          return (
            <li key={idx} className="flex items-start justify-between gap-3">
              <p className="min-w-0 flex-1 text-xs leading-relaxed text-foreground/90">{item.cause}</p>
              <span
                className={`shrink-0 rounded px-1.5 py-px font-mono text-[10px] font-medium uppercase ${meta.className}`}
                title={`${meta.label} plausibility`}
              >
                {meta.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
