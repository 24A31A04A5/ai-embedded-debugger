"use client";

import * as React from "react";
import { AlertCircle, AlertTriangle, HelpCircle, Target } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { type LikelyCause } from "./types";

interface CauseListProps {
  causes: LikelyCause[];
  rootCauseSummary?: string | null;
  confidenceLevel?: "high" | "medium" | "low" | null;
}

function getPlausibilityBadge(plausibility: LikelyCause["plausibility"]) {
  switch (plausibility) {
    case "high":
      return (
        <Badge
          variant="error"
          className="text-[10px] font-semibold uppercase tracking-wider shrink-0 gap-1 border-[var(--color-error-red)]/40 bg-[var(--color-error-red)]/10 text-[var(--color-error-red)]"
        >
          <AlertCircle className="h-3 w-3" />
          <span>High Plausibility</span>
        </Badge>
      );
    case "medium":
      return (
        <Badge
          variant="warning"
          className="text-[10px] font-semibold uppercase tracking-wider shrink-0 gap-1 border-[var(--color-warning-amber)]/40 bg-[var(--color-warning-amber)]/10 text-[var(--color-warning-amber)]"
        >
          <AlertTriangle className="h-3 w-3" />
          <span>Medium Plausibility</span>
        </Badge>
      );
    case "low":
    default:
      return (
        <Badge
          variant="outline"
          className="text-[10px] font-semibold uppercase tracking-wider shrink-0 gap-1 border-muted-foreground/40 text-muted-foreground"
        >
          <HelpCircle className="h-3 w-3" />
          <span>Low Plausibility</span>
        </Badge>
      );
  }
}

export function CauseList({ causes, rootCauseSummary, confidenceLevel }: CauseListProps) {
  if ((!causes || causes.length === 0) && !rootCauseSummary) return null;

  return (
    <div className="space-y-2.5">
      {rootCauseSummary && (
        <div className="p-3.5 rounded-xl border border-[var(--accent-purple)]/40 bg-[var(--accent-purple)]/10 backdrop-blur-sm space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--accent-purple)]">
              <Target className="h-3.5 w-3.5" />
              Primary Root Cause Identified
            </span>
            {confidenceLevel && (
              <Badge
                variant={confidenceLevel === "high" ? "success" : confidenceLevel === "medium" ? "warning" : "outline"}
                className="text-[9px] uppercase tracking-wider font-mono"
              >
                {confidenceLevel} Confidence
              </Badge>
            )}
          </div>
          <p className="text-xs sm:text-sm text-foreground/95 leading-relaxed font-medium">
            {rootCauseSummary}
          </p>
        </div>
      )}
      {causes.map((item, idx) => (
        <div
          key={idx}
          className="group flex flex-col sm:flex-row sm:items-start justify-between gap-3 p-3.5 rounded-xl border border-border/50 bg-card/60 backdrop-blur-sm hover:border-[var(--accent-purple)]/30 hover:bg-card/90 transition-all shadow-sm"
        >
          <div className="flex-1 min-w-0 pr-2">
            <p className="text-xs sm:text-sm text-foreground/90 leading-relaxed font-medium">
              {item.cause}
            </p>
          </div>
          <div className="shrink-0 self-start">
            {getPlausibilityBadge(item.plausibility)}
          </div>
        </div>
      ))}
    </div>
  );
}
