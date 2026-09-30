"use client";

import * as React from "react";

interface RecommendedStepsProps {
  steps: string[];
}

export function RecommendedSteps({ steps }: RecommendedStepsProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <ol className="space-y-2">
      {steps.map((step, idx) => (
        <li key={idx} className="flex items-start gap-2.5">
          <span className="mt-px flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded bg-white/[0.06] font-mono text-[10px] font-semibold text-foreground/80">
            {idx + 1}
          </span>
          <p className="text-xs leading-relaxed text-foreground/90">{step}</p>
        </li>
      ))}
    </ol>
  );
}
