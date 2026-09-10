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
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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

  return (
    <header className="flex min-h-[52px] shrink-0 items-center justify-between border-b border-border/40 bg-[oklch(0.12_0.015_260/0.92)] backdrop-blur-xl px-3 sm:px-4 z-20">
      {/* Left Context: Brand & Sidebar Toggles */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {/* Desktop sidebar toggle */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="hidden md:inline-flex h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-white/5 rounded-md"
              onClick={onToggleSidebar}
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            {sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          </TooltipContent>
        </Tooltip>

        {/* Mobile sidebar toggle */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-white/5 rounded-md"
          onClick={onToggleMobileSidebar}
          aria-label={mobileSidebarOpen ? "Close navigation" : "Open navigation"}
        >
          {mobileSidebarOpen ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <PanelLeftOpen className="h-4 w-4" />
          )}
        </Button>

        <Separator orientation="vertical" className="h-4 hidden sm:block bg-border/40" />

        {/* Brand Mark */}
        <Link
          href="/"
          className="flex items-center gap-2 shrink-0 group"
          aria-label="AI Embedded Debugger Home"
        >
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-[var(--accent-purple)] to-[var(--accent-indigo)] shadow-sm shadow-[var(--accent-purple)]/25 border border-purple-400/20 group-hover:scale-105 transition-transform">
            <Bug className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="hidden sm:inline-flex text-xs sm:text-sm font-semibold text-foreground tracking-tight items-center gap-1.5 font-display">
            <span className="rounded bg-[var(--accent-purple)]/20 px-1 py-0.5 text-[9px] font-bold text-purple-200 border border-[var(--accent-purple)]/30 tracking-wider font-mono">
              AI
            </span>
            <span className="text-foreground/95">Embedded Debugger</span>
          </span>
        </Link>
      </div>

      {/* Center Context: Project & Session Selectors */}
      <div className="flex items-center gap-2 min-w-0 mx-2">
        {/* Project Selector */}
        {projects.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 sm:h-8 gap-1.5 sm:gap-2 px-2 sm:px-2.5 text-xs font-medium text-foreground/90 hover:bg-white/5 border border-border/40 rounded-lg max-w-[130px] sm:max-w-[200px] md:max-w-xs"
              >
                <FolderOpen className="h-3.5 w-3.5 text-[var(--accent-purple)] shrink-0" />
                <span className="truncate">{activeProject ? activeProject.name : "Select Project"}</span>
                <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="center" className="w-56 bg-[oklch(0.15_0.015_260/0.95)] backdrop-blur-xl border-border/80">
              <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                Active Project
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {projects.map((p) => (
                <DropdownMenuItem
                  key={p.id}
                  onClick={() => onSelectProject?.(p.id)}
                  className={`flex items-center justify-between text-xs cursor-pointer ${
                    p.id === activeProject?.id
                      ? "text-[var(--accent-purple)] font-medium bg-[var(--accent-purple)]/10"
                      : "text-foreground/80 hover:text-foreground"
                  }`}
                >
                  <span className="truncate">{p.name}</span>
                  {p.id === activeProject?.id && (
                    <div className="h-1.5 w-1.5 rounded-full bg-[var(--accent-purple)] shadow-[0_0_6px_var(--accent-purple)] shrink-0" />
                  )}
                </DropdownMenuItem>
              ))}
              {onCreateProject && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={onCreateProject}
                    className="flex items-center gap-2 text-xs text-[var(--accent-purple)] cursor-pointer hover:bg-[var(--accent-purple)]/10"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Create new project</span>
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {/* Active Session Dropdown (Desktop >= md) */}
        {sessions.length > 0 && (
          <div className="hidden md:flex items-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1.5 px-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-white/5 border border-border/30 rounded-lg max-w-[170px]"
                >
                  <History className="h-3 w-3 text-[var(--accent-indigo)] shrink-0" />
                  <span className="truncate">
                    {activeSession ? activeSession.title : "Active Session"}
                  </span>
                  <ChevronDown className="h-3 w-3 text-muted-foreground/60 shrink-0" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-64 bg-[oklch(0.15_0.015_260/0.95)] backdrop-blur-xl border-border/80">
                <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                  Debug Sessions ({sessions.length})
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {sessions.slice(0, 8).map((s) => (
                  <DropdownMenuItem
                    key={s.id}
                    onClick={() => onSelectSession?.(s.id)}
                    className={`flex flex-col items-start gap-0.5 text-xs cursor-pointer py-1.5 ${
                      s.id === activeSessionId
                        ? "text-[var(--accent-purple)] font-medium bg-[var(--accent-purple)]/10"
                        : "text-foreground/80"
                    }`}
                  >
                    <span className="truncate w-full font-medium">{s.title}</span>
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {new Date(s.created_at).toLocaleDateString()}
                    </span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}

        {/* Status indicator */}
        <Badge
          variant={
            isAnalyzing
              ? "ai"
              : hasDiagnosis
                ? "success"
                : "outline"
          }
          className="hidden lg:inline-flex text-[10px] font-mono"
        >
          {isAnalyzing ? "Analyzing" : hasDiagnosis ? "Ready" : "Idle"}
        </Badge>
      </div>

      {/* Right Actions: Primary Analyze Button & User Profile */}
      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        <Button
          size="sm"
          variant="ai"
          className="gap-1.5 sm:gap-2 text-xs font-semibold shrink-0 px-2.5 sm:px-3.5 shadow-sm shadow-[var(--accent-purple)]/20"
          onClick={onAnalyze}
          disabled={isAnalyzing || !canAnalyze}
        >
          {isAnalyzing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5 text-white" />
          )}
          <span>{isAnalyzing ? "Analyzing..." : "Analyze with AI"}</span>
        </Button>

        <Separator orientation="vertical" className="h-4 bg-border/40" />

        <div className="flex items-center">
          <UserButton
            appearance={{
              elements: {
                avatarBox: "h-7 w-7 rounded-lg ring-1 ring-border/60 hover:ring-[var(--accent-purple)]/50 transition-all",
              },
            }}
          />
        </div>
      </div>
    </header>
  );
}
