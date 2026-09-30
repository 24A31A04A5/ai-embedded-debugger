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
      className={`h-6 shrink-0 items-stretch justify-between border-t border-ide-border bg-ide-statusbar font-mono text-[11px] text-muted-foreground select-none ${className}`}
    >
      <div className="flex min-w-0 items-stretch">
        <span
          role="status"
          aria-live="polite"
          className={`flex items-center gap-1.5 px-2.5 ${
            aiStatus === "error"
              ? "bg-[var(--color-error-red)]/15 text-[var(--color-error-red)]"
              : "bg-[var(--accent-purple)]/15 text-[oklch(0.80_0.10_290)]"
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
          className="flex items-center gap-2 px-2.5 hover:bg-ide-hover hover:text-foreground focus-visible:outline-none focus-visible:bg-ide-hover"
          aria-label={`${errorCount} errors, ${warningCount} warnings. Show problems`}
        >
          <span className="flex items-center gap-1">
            <CircleX className={`h-3 w-3 ${errorCount ? "text-[var(--color-error-red)]" : ""}`} />
            {errorCount}
          </span>
          <span className="flex items-center gap-1">
            <AlertTriangle className={`h-3 w-3 ${warningCount ? "text-[var(--color-warning-amber)]" : ""}`} />
            {warningCount}
          </span>
        </button>

        {projectName && (
          <span className="hidden md:flex min-w-0 items-center gap-1.5 px-2.5">
            <FolderOpen className="h-3 w-3 shrink-0" />
            <span className="truncate">{projectName}</span>
          </span>
        )}
      </div>

      <div className="flex shrink-0 items-stretch">
        <span className="flex items-center px-2.5 text-foreground/75">
          Ln {cursor.line}, Col {cursor.column}
          {cursor.selected > 0 && <span className="ml-1 text-muted-foreground">({cursor.selected} selected)</span>}
        </span>
        <span className="hidden md:flex items-center px-2.5">Spaces: {tabSize}</span>
        <span className="hidden md:flex items-center px-2.5">UTF-8</span>
        <span className="hidden md:flex items-center px-2.5">{lineEnding}</span>
        <span className="flex items-center px-2.5">{languageLabel}</span>
      </div>
    </footer>
  );
}
