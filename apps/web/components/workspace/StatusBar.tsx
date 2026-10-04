"use client";

import React from "react";
import { AlertTriangle, CircleX, FolderOpen, Loader2, Sparkles } from "lucide-react";

import { type CursorPosition } from "@/components/CodeEditor";

export type AIStatus = "idle" | "analyzing" | "complete" | "error";

interface StatusBarProps {
  aiStatus: AIStatus;
  projectName?: string;
  errorCount: number;
  warningCount: number;
  onShowProblems?: () => void;
  cursor: CursorPosition;
  tabSize: number;
  lineEnding: "CRLF" | "LF";
  languageLabel: string;
  className?: string;
}

const AI_LABEL: Record<AIStatus, string> = {
  idle: "AI idle",
  analyzing: "Analyzing…",
  complete: "Analysis complete",
  error: "Analysis failed",
};

export function StatusBar({
  aiStatus,
  projectName,
  errorCount,
  warningCount,
  onShowProblems,
  cursor,
  tabSize,
  lineEnding,
  languageLabel,
  className = "",
}: StatusBarProps) {
  return (
    <footer
      aria-label="Status bar"
      className={`lg-glass h-9 shrink-0 items-center justify-between gap-2 px-1.5 font-mono text-[11px] text-muted-foreground select-none lg:rounded-[14px] ${className}`}
    >
      <div className="flex min-w-0 items-center gap-1">
        <span
          role="status"
          aria-live="polite"
          className={`flex h-6 items-center gap-1.5 rounded-full px-2.5 ${
            aiStatus === "error"
              ? "bg-[var(--color-error-red)]/15 text-[var(--color-error-red)]"
              : "bg-[var(--accent-purple)]/20 text-white shadow-[inset_0_0_0_1px_oklch(0.74_0.16_158/0.35)]"
          }`}
        >
          {aiStatus === "analyzing" ? (
            <Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" />
          ) : (
            <Sparkles className="h-3 w-3" />
          )}
          {AI_LABEL[aiStatus]}
        </span>

        <button
          type="button"
          onClick={onShowProblems}
          className="lg-ghost flex h-6 items-center gap-2 rounded-full px-2.5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
          aria-label={`${errorCount} errors, ${warningCount} warnings. Show problems`}
        >
          <span className="flex items-center gap-1">
            <CircleX className="lg-red h-3 w-3" />
            {errorCount}
          </span>
          <span className="flex items-center gap-1">
            <AlertTriangle className="lg-yellow h-3 w-3" />
            {warningCount}
          </span>
        </button>

        {projectName && (
          <span className="hidden md:flex min-w-0 items-center gap-1.5 px-2.5">
            <FolderOpen className="lg-green h-3 w-3 shrink-0" />
            <span className="truncate">{projectName}</span>
          </span>
        )}
      </div>

      <div className="flex shrink-0 items-center">
        <span className="flex items-center px-2.5 text-foreground/80">
          Ln {cursor.line}, Col {cursor.column}
          {cursor.selected > 0 && <span className="ml-1 text-muted-foreground">({cursor.selected} selected)</span>}
        </span>
        <span className="hidden md:flex items-center px-2.5">Spaces: {tabSize}</span>
        <span className="hidden md:flex items-center px-2.5">UTF-8</span>
        <span className="hidden md:flex items-center px-2.5">{lineEnding}</span>
        <span className="ml-1 flex h-6 items-center rounded-full bg-white/[0.06] px-2.5 text-foreground/85">{languageLabel}</span>
      </div>
    </footer>
  );
}
