"use client";

import React from "react";
import Link from "next/link";
import {
  ChevronDown,
  FolderOpen,
  History,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Sparkles,
} from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { UserButton } from "@clerk/nextjs";
import { type DebugSessionSummary } from "@/lib/api-client";

export type Project = {
  id: string;
  name: string;
  description?: string;
  active?: boolean;
};

interface WorkspaceHeaderProps {
  mobileSidebarOpen: boolean;
  onToggleMobileSidebar: () => void;
  activeProject?: Project;
  projects?: Project[];
  onSelectProject?: (id: string) => void;
  onCreateProject?: () => void;
  sessions?: DebugSessionSummary[];
  activeSessionId?: string | null;
  onSelectSession?: (id: string) => void;
  isAnalyzing: boolean;
  onAnalyze: () => void;
  canAnalyze: boolean;
  hasDiagnosis: boolean;
  className?: string;
}

const PILL =
  "lg-chip inline-flex h-11 lg:h-8 min-w-0 items-center gap-1.5 rounded-full px-3 text-xs font-medium text-foreground/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60";

const MENU_CONTENT = "lg-glass lg-glass-strong rounded-2xl border-0 p-1.5 text-foreground";
const MENU_LABEL = "px-2 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground";
const MENU_ITEM = "cursor-pointer rounded-xl px-2.5 py-2 text-xs focus:bg-white/10";

export function WorkspaceHeader({
  mobileSidebarOpen,
  onToggleMobileSidebar,
  activeProject,
  projects = [],
  onSelectProject,
  onCreateProject,
  sessions = [],
  activeSessionId,
  onSelectSession,
  isAnalyzing,
  onAnalyze,
  canAnalyze,
  hasDiagnosis,
  className = "",
}: WorkspaceHeaderProps) {
  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const status = isAnalyzing
    ? { label: "Analyzing", dot: "bg-[var(--accent-purple)] animate-pulse motion-reduce:animate-none" }
    : hasDiagnosis
      ? { label: "Diagnosis ready", dot: "bg-[var(--color-success-green)] shadow-[0_0_8px_oklch(0.65_0.19_145/0.8)]" }
      : { label: "Idle", dot: "bg-muted-foreground/70" };

  return (
    <header
      className={`lg-glass z-20 flex h-14 shrink-0 items-center justify-between gap-2 px-2 sm:px-3 lg:h-[52px] lg:rounded-[18px] ${className}`}
    >
      {/* Left: explorer drawer toggle (< lg) + brand */}
      <div className="flex min-w-0 items-center gap-1.5">
        <button
          type="button"
          className="lg-ghost flex h-11 w-11 items-center justify-center rounded-full text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60 lg:hidden"
          onClick={onToggleMobileSidebar}
          aria-label={mobileSidebarOpen ? "Close Explorer" : "Open Explorer"}
          aria-expanded={mobileSidebarOpen}
        >
          {mobileSidebarOpen ? <PanelLeftClose className="lg-white h-[18px] w-[18px]" /> : <PanelLeftOpen className="lg-white h-[18px] w-[18px]" />}
        </button>

        <Link
          href="/"
          className="flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-2.5 rounded-full pr-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60 lg:min-h-0 lg:min-w-0"
          aria-label="AI Embedded Debugger Home"
        >
          <img
            src="/brand/ai-embedded-debugger-logo.png"
            alt=""
            width={1536}
            height={1024}
            className="h-9 w-auto shrink-0 object-contain"
          />
          <span className="hidden text-[13px] font-semibold tracking-tight text-foreground md:inline">
            AI Embedded Debugger
          </span>
        </Link>
      </div>

      {/* Center: project / session context */}
      <div className="flex min-w-0 flex-1 items-center justify-center gap-1.5">
        {projects.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className={`${PILL} max-w-[160px] sm:max-w-[240px]`}
                aria-label={`Project: ${activeProject ? activeProject.name : "none selected"}. Change project`}
              >
                <FolderOpen className="lg-green h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{activeProject ? activeProject.name : "Select Project"}</span>
                <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="center" sideOffset={8} className={`w-60 ${MENU_CONTENT}`}>
              <DropdownMenuLabel className={MENU_LABEL}>Projects</DropdownMenuLabel>
              {projects.map((p) => (
                <DropdownMenuItem
                  key={p.id}
                  onClick={() => onSelectProject?.(p.id)}
                  className={`${MENU_ITEM} flex items-center justify-between ${
                    p.id === activeProject?.id ? "lg-chip-active font-medium" : "text-foreground/85"
                  }`}
                >
                  <span className="truncate">{p.name}</span>
                  {p.id === activeProject?.id && (
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[oklch(0.86_0.14_158)]" aria-label="active" />
                  )}
                </DropdownMenuItem>
              ))}
              {onCreateProject && (
                <>
                  <DropdownMenuSeparator className="my-1.5 bg-white/10" />
                  <DropdownMenuItem onClick={onCreateProject} className={`${MENU_ITEM} flex items-center gap-2`}>
                    <Plus className="h-3.5 w-3.5" />
                    <span>Create new project</span>
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {sessions.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className={`${PILL} hidden max-w-[220px] font-normal text-muted-foreground hover:text-foreground md:inline-flex`}
                aria-label={`Session: ${activeSession ? activeSession.title : "none"}. Change session`}
              >
                <History className="lg-white h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{activeSession ? activeSession.title : "No session"}</span>
                <ChevronDown className="h-3 w-3 shrink-0 opacity-60" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" sideOffset={8} className={`w-68 ${MENU_CONTENT}`}>
              <DropdownMenuLabel className={MENU_LABEL}>Debug sessions ({sessions.length})</DropdownMenuLabel>
              {sessions.slice(0, 8).map((s) => (
                <DropdownMenuItem
                  key={s.id}
                  onClick={() => onSelectSession?.(s.id)}
                  className={`${MENU_ITEM} flex flex-col items-start gap-0.5 ${
                    s.id === activeSessionId ? "lg-chip-active font-medium" : "text-foreground/85"
                  }`}
                >
                  <span className="w-full truncate">{s.title}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {new Date(s.created_at).toLocaleDateString()}
                  </span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Right: status, primary action, profile */}
      <div className="flex shrink-0 items-center gap-2">
        <span
          className="lg-chip hidden h-8 items-center gap-2 rounded-full px-3 text-[11px] text-muted-foreground xl:inline-flex"
          aria-live="polite"
        >
          <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} aria-hidden="true" />
          {status.label}
        </span>

        <button
          type="button"
          className="lg-primary inline-flex h-11 items-center gap-1.5 rounded-full px-4 text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 lg:h-8"
          onClick={onAnalyze}
          disabled={isAnalyzing || !canAnalyze}
          title={!canAnalyze ? "Add source code, compiler output, or serial logs to analyze" : undefined}
        >
          {isAnalyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          <span className="hidden sm:inline">{isAnalyzing ? "Analyzing…" : "Analyze with AI"}</span>
          <span className="sm:hidden">{isAnalyzing ? "…" : "Analyze"}</span>
        </button>

        <div className="flex h-11 w-11 items-center justify-center lg:h-8 lg:w-8">
          <UserButton
            appearance={{
              elements: {
                avatarBox: "h-8 w-8 rounded-full ring-1 ring-white/20 shadow-[0_4px_12px_-4px_oklch(0_0_0/0.6)]",
              },
            }}
          />
        </div>
      </div>
    </header>
  );
}
