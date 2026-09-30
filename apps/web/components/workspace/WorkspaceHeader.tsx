"use client";

import React from "react";
import Link from "next/link";
import {
  Bug,
  ChevronDown,
  FolderOpen,
  History,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  sidebarOpen: boolean;
  mobileSidebarOpen: boolean;
  onToggleSidebar: () => void;
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
}

const TOOLBAR_BUTTON =
  "h-11 w-11 lg:h-7 lg:w-7 rounded text-muted-foreground hover:bg-ide-hover hover:text-foreground";

const MENU_CONTENT = "bg-[oklch(0.2_0.004_270)] border-ide-border shadow-xl";

export function WorkspaceHeader({
  sidebarOpen,
  mobileSidebarOpen,
  onToggleSidebar,
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
}: WorkspaceHeaderProps) {
  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const status = isAnalyzing
    ? { label: "Analyzing", dot: "bg-[var(--accent-purple)] animate-pulse motion-reduce:animate-none" }
    : hasDiagnosis
      ? { label: "Diagnosis ready", dot: "bg-[var(--color-success-green)]" }
      : { label: "Idle", dot: "bg-muted-foreground/60" };

  return (
    <header className="z-20 flex h-12 lg:h-10 shrink-0 items-center justify-between gap-2 border-b border-ide-border bg-ide-titlebar px-1.5 sm:px-2">
      {/* Left: sidebar toggle + brand */}
      <div className="flex min-w-0 items-center gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className={`hidden lg:inline-flex ${TOOLBAR_BUTTON}`}
              onClick={onToggleSidebar}
              aria-label={sidebarOpen ? "Hide Explorer" : "Show Explorer"}
              aria-pressed={sidebarOpen}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">{sidebarOpen ? "Hide Explorer" : "Show Explorer"}</TooltipContent>
        </Tooltip>

        <Button
          variant="ghost"
          size="icon"
          className={`lg:hidden ${TOOLBAR_BUTTON}`}
          onClick={onToggleMobileSidebar}
          aria-label={mobileSidebarOpen ? "Close Explorer" : "Open Explorer"}
          aria-expanded={mobileSidebarOpen}
        >
          {mobileSidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
        </Button>

        <Link
          href="/"
          className="flex min-h-11 min-w-11 lg:min-h-0 lg:min-w-0 shrink-0 items-center justify-center gap-2 rounded px-1.5 py-1 hover:bg-ide-hover"
          aria-label="AI Embedded Debugger Home"
        >
          <span className="flex h-5 w-5 items-center justify-center rounded bg-[var(--accent-purple)]/90">
            <Bug className="h-3 w-3 text-white" />
          </span>
          <span className="hidden md:inline text-xs font-semibold tracking-tight text-foreground/90">
            AI Embedded Debugger
          </span>
        </Link>
      </div>

      {/* Center: project / session context */}
      <div className="flex min-w-0 flex-1 items-center justify-center gap-1">
        {projects.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-11 lg:h-7 min-w-0 max-w-[150px] sm:max-w-[220px] gap-1.5 rounded border border-ide-border-subtle bg-white/[0.03] px-2 text-xs font-medium text-foreground/90 hover:bg-ide-hover"
                aria-label={`Project: ${activeProject ? activeProject.name : "none selected"}. Change project`}
              >
                <FolderOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate">{activeProject ? activeProject.name : "Select Project"}</span>
                <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="center" className={`w-56 ${MENU_CONTENT}`}>
              <DropdownMenuLabel className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Projects
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {projects.map((p) => (
                <DropdownMenuItem
                  key={p.id}
                  onClick={() => onSelectProject?.(p.id)}
                  className={`flex cursor-pointer items-center justify-between text-xs ${
                    p.id === activeProject?.id ? "bg-ide-selected font-medium text-foreground" : "text-foreground/80"
                  }`}
                >
                  <span className="truncate">{p.name}</span>
                  {p.id === activeProject?.id && (
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-foreground/70" aria-label="active" />
                  )}
                </DropdownMenuItem>
              ))}
              {onCreateProject && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={onCreateProject} className="flex cursor-pointer items-center gap-2 text-xs">
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
              <Button
                variant="ghost"
                size="sm"
                className="hidden md:inline-flex h-11 lg:h-7 min-w-0 max-w-[200px] gap-1.5 rounded px-2 text-xs font-normal text-muted-foreground hover:bg-ide-hover hover:text-foreground"
                aria-label={`Session: ${activeSession ? activeSession.title : "none"}. Change session`}
              >
                <History className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{activeSession ? activeSession.title : "No session"}</span>
                <ChevronDown className="h-3 w-3 shrink-0 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className={`w-64 ${MENU_CONTENT}`}>
              <DropdownMenuLabel className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Debug sessions ({sessions.length})
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {sessions.slice(0, 8).map((s) => (
                <DropdownMenuItem
                  key={s.id}
                  onClick={() => onSelectSession?.(s.id)}
                  className={`flex cursor-pointer flex-col items-start gap-0.5 py-1.5 text-xs ${
                    s.id === activeSessionId ? "bg-ide-selected font-medium text-foreground" : "text-foreground/80"
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
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
        <span
          className="hidden lg:inline-flex items-center gap-1.5 px-1 text-[11px] text-muted-foreground"
          aria-live="polite"
        >
          <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} aria-hidden="true" />
          {status.label}
        </span>

        <Button
          size="sm"
          variant="ai"
          className="h-11 lg:h-7 gap-1.5 rounded px-3 text-xs font-semibold shadow-none border-0 bg-none bg-[oklch(0.55_0.2_290)] hover:bg-[oklch(0.6_0.2_290)] hover:brightness-100"
          onClick={onAnalyze}
          disabled={isAnalyzing || !canAnalyze}
          title={!canAnalyze ? "Add source code, compiler output, or serial logs to analyze" : undefined}
        >
          {isAnalyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          <span className="hidden sm:inline">{isAnalyzing ? "Analyzing…" : "Analyze with AI"}</span>
          <span className="sm:hidden">{isAnalyzing ? "…" : "Analyze"}</span>
        </Button>

        <div className="flex h-11 w-11 lg:h-7 lg:w-7 items-center justify-center">
          <UserButton
            appearance={{
              elements: {
                avatarBox: "h-6 w-6 rounded ring-1 ring-white/10",
              },
            }}
          />
        </div>
      </div>
    </header>
  );
}
