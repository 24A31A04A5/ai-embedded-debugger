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
          <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/[0.08] font-mono text-[10px] font-semibold text-foreground/85 shadow-[inset_0_1px_0_oklch(1_0_0/0.14),inset_0_0_0_1px_oklch(1_0_0/0.06)]">
            {idx + 1}
          </span>
          <p className="text-xs leading-relaxed text-foreground/90">{step}</p>
        </li>
      ))}
    </ol>
  );
}
