"use client";

import React from "react";
import Link from "next/link";
import { CircleAlert, Files, FileTerminal, House, Sparkles, Usb } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { type BottomPanelTab } from "./DiagnosticTabs";

interface ActivityRailProps {
  explorerOpen: boolean;
  onToggleExplorer: () => void;
  aiOpen: boolean;
  onToggleAI: () => void;
  bottomTab: BottomPanelTab;
  bottomPanelOpen: boolean;
  onShowBottomTab: (tab: BottomPanelTab) => void;
  problemCount: number;
  hasErrors: boolean;
  className?: string;
}

function RailButton({
  label,
  active,
  onClick,
  children,
  badge,
  badgeTone = "neutral",
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  badge?: number;
  badgeTone?: "neutral" | "error";
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          aria-label={label}
          aria-pressed={active}
          className={`relative flex h-10 w-10 items-center justify-center rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60 ${
            active ? "lg-chip-active text-foreground" : "lg-ghost text-muted-foreground hover:text-foreground"
          }`}
        >
          {children}
          {typeof badge === "number" && badge > 0 && (
            <span
              aria-hidden="true"
              className={`absolute -right-0.5 -top-0.5 min-w-4 rounded-full px-1 text-center font-mono text-[9px] font-semibold leading-4 ${
                badgeTone === "error" ? "bg-[var(--color-error-red)] text-white" : "bg-white/20 text-foreground"
              }`}
            >
              {badge}
            </span>
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

export function ActivityRail({
  explorerOpen,
  onToggleExplorer,
  aiOpen,
  onToggleAI,
  bottomTab,
  bottomPanelOpen,
  onShowBottomTab,
  problemCount,
  hasErrors,
  className = "",
}: ActivityRailProps) {
  return (
    <nav
      aria-label="Workbench"
      className={`lg-glass lg-panel flex w-14 shrink-0 flex-col items-center gap-1.5 py-2.5 ${className}`}
    >
      <RailButton label={explorerOpen ? "Hide Explorer" : "Show Explorer"} active={explorerOpen} onClick={onToggleExplorer}>
        <Files className="lg-green h-[18px] w-[18px]" />
      </RailButton>
      <RailButton
        label="Problems"
        active={bottomPanelOpen && bottomTab === "problems"}
        onClick={() => onShowBottomTab("problems")}
        badge={problemCount}
        badgeTone={hasErrors ? "error" : "neutral"}
      >
        <CircleAlert className="lg-red h-[18px] w-[18px]" />
      </RailButton>
      <RailButton
        label="Compiler output"
        active={bottomPanelOpen && bottomTab === "output"}
        onClick={() => onShowBottomTab("output")}
      >
        <FileTerminal className="lg-white h-[18px] w-[18px]" />
      </RailButton>
      <RailButton
        label="Serial / UART logs"
        active={bottomPanelOpen && bottomTab === "serial"}
        onClick={() => onShowBottomTab("serial")}
      >
        <Usb className="lg-green h-[18px] w-[18px]" />
      </RailButton>

      <span aria-hidden="true" className="my-1 h-px w-6 bg-white/10" />

      <RailButton label={aiOpen ? "Hide AI Debug" : "Show AI Debug"} active={aiOpen} onClick={onToggleAI}>
        <Sparkles className="lg-green h-[18px] w-[18px]" />
      </RailButton>

      <div className="mt-auto">
        <Tooltip>
          <TooltipTrigger asChild>
            <Link
              href="/"
              aria-label="Home"
              className="lg-ghost flex h-10 w-10 items-center justify-center rounded-xl text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
            >
              <House className="lg-white h-[18px] w-[18px]" />
            </Link>
          </TooltipTrigger>
          <TooltipContent side="right">Home</TooltipContent>
        </Tooltip>
      </div>
    </nav>
  );
}
