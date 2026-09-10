"use client";

import * as React from "react";

interface RecommendedStepsProps {
  steps: string[];
}

export function RecommendedSteps({ steps }: RecommendedStepsProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="space-y-2">
      {steps.map((step, idx) => (
        <div
          key={idx}
          className="flex items-start gap-3 p-2.5 rounded-lg border border-border/40 bg-card/40 hover:bg-card/70 transition-colors"
        >
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent-purple)]/15 text-[var(--accent-purple)] border border-[var(--accent-purple)]/30 text-[11px] font-mono font-bold mt-0.5">
            {idx + 1}
          </span>
          <p className="text-xs sm:text-sm text-foreground/90 leading-relaxed">
            {step}
          </p>
        </div>
      ))}
    </div>
  );
}
