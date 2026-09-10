"use client";

import * as React from "react";
import { Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface AIRetrievalBadgeProps {
  evidenceCount?: number;
  citationCount?: number;
  className?: string;
}

export function AIRetrievalBadge({
  evidenceCount,
  citationCount,
  className = "",
}: AIRetrievalBadgeProps) {
  const totalSignals = (evidenceCount ?? 0) + (citationCount ?? 0);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant="ai"
          className={`cursor-help inline-flex items-center gap-1.5 py-0.5 px-2 text-[11px] font-medium border-[var(--accent-purple)]/40 bg-[var(--accent-purple)]/10 text-purple-200 shadow-sm ${className}`}
        >
          <Sparkles className="h-3 w-3 text-[var(--accent-purple)]" />
          <span>Grounded in Evidence</span>
          {totalSignals > 0 && (
            <span className="ml-1 rounded-full bg-[var(--accent-purple)]/30 px-1 text-[9px] font-mono">
              {totalSignals}
            </span>
          )}
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-xs">
        Reasoning conclusions and register bitmasks cite verified compiler outputs, serial traces, or project datasheets.
      </TooltipContent>
    </Tooltip>
  );
}
