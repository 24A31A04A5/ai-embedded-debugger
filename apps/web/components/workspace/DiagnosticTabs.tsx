"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  CircleX,
  FileTerminal,
  Info,
  RotateCcw,
  Terminal,
  Usb,
} from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CodeEditor } from "@/components/CodeEditor";

export type BottomPanelTab = "problems" | "output" | "terminal" | "serial";

export type Problem = {
  severity: "error" | "warning" | "info";
  message: string;
  source: string;
  file?: string | null;
  line?: number | null;
  column?: number | null;
  location?: string | null;
};

interface DiagnosticTabsProps {
  compilerOutput: string;
  onCompilerChange: (v: string) => void;
  serialLogs: string;
  onSerialChange: (v: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  activeTab?: BottomPanelTab;
  onActiveTabChange?: (tab: BottomPanelTab) => void;
  problems?: Problem[];
  hasDiagnosis?: boolean;
  onSelectProblem?: (problem: Problem) => void;
  collapsible?: boolean;
  className?: string;
}

const TRIGGER_CLASS =
  "h-10 lg:h-7 shrink-0 gap-1.5 rounded-full border-0 bg-transparent px-3 text-[11px] font-medium text-muted-foreground shadow-none transition-colors hover:text-foreground data-[state=active]:border-0 data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none";

const ICON_BUTTON =
  "lg-chip flex h-10 w-10 lg:h-7 lg:w-7 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60";

function CountBadge({ count, tone = "neutral" }: { count: number; tone?: "neutral" | "error" }) {
  if (count <= 0) return null;
  return (
    <span
      className={`ml-1.5 rounded-full px-1.5 text-[10px] font-mono leading-4 ${
        tone === "error" ? "bg-[var(--color-error-red)]/20 text-[var(--color-error-red)]" : "bg-white/10 text-muted-foreground"
      }`}
    >
      {count}
    </span>
  );
}

function ProblemIcon({ severity }: { severity: Problem["severity"] }) {
  if (severity === "error") return <CircleX className="h-3.5 w-3.5 shrink-0 text-[var(--color-error-red)]" />;
  if (severity === "warning") return <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[var(--color-warning-amber)]" />;
  return <Info className="h-3.5 w-3.5 shrink-0 text-[var(--color-info-blue)]" />;
}

export function DiagnosticTabs({
  compilerOutput,
  onCompilerChange,
  serialLogs,
  onSerialChange,
  isCollapsed,
  onToggleCollapse,
  activeTab: controlledTab,
  onActiveTabChange,
  problems = [],
  hasDiagnosis = false,
  onSelectProblem,
  collapsible = true,
  className = "",
}: DiagnosticTabsProps) {
  const [uncontrolledTab, setUncontrolledTab] = useState<BottomPanelTab>("output");
  const activeTab = controlledTab ?? uncontrolledTab;
  const [cleared, setCleared] = useState(false);

  const compilerLines = compilerOutput ? compilerOutput.split("\n").length : 0;
  const serialLines = serialLogs ? serialLogs.split("\n").length : 0;
  const errorCount = problems.filter((p) => p.severity === "error").length;

  const setTab = (tab: BottomPanelTab) => {
    setUncontrolledTab(tab);
    onActiveTabChange?.(tab);
  };
  const expandOnClick = () => {
    if (isCollapsed) onToggleCollapse();
  };

  const clearable = activeTab === "output" ? !!compilerOutput : activeTab === "serial" ? !!serialLogs : false;

  const handleClearCurrent = () => {
    if (activeTab === "output") onCompilerChange("");
    else if (activeTab === "serial") onSerialChange("");
    setCleared(true);
    setTimeout(() => setCleared(false), 1500);
  };

  return (
    <section
      aria-label="Diagnostics panel"
      className={`flex flex-col overflow-hidden ${className}`}
    >
      <Tabs
        value={activeTab}
        onValueChange={(v) => setTab(v as BottomPanelTab)}
        className="flex h-full flex-1 flex-col overflow-hidden"
      >
        <div className="flex h-14 lg:h-12 shrink-0 items-center justify-between gap-2 px-2">
          <TabsList className="lg-segmented h-auto min-w-0 justify-start gap-0.5 overflow-x-auto border-0 backdrop-blur-none [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <TabsTrigger value="problems" className={TRIGGER_CLASS} onClick={expandOnClick}>
              <CircleX className="lg-red h-3.5 w-3.5" />
              Problems
              <CountBadge count={problems.length} tone={errorCount > 0 ? "error" : "neutral"} />
            </TabsTrigger>
            <TabsTrigger value="output" className={TRIGGER_CLASS} onClick={expandOnClick}>
              <FileTerminal className="lg-white h-3.5 w-3.5" />
              Output
              <CountBadge count={compilerLines} />
            </TabsTrigger>
            <TabsTrigger value="terminal" className={TRIGGER_CLASS} onClick={expandOnClick}>
              <Terminal className="lg-green h-3.5 w-3.5" />
              Terminal
            </TabsTrigger>
            <TabsTrigger value="serial" className={TRIGGER_CLASS} onClick={expandOnClick}>
              <Usb className="lg-green h-3.5 w-3.5" />
              Serial / UART
              <CountBadge count={serialLines} />
            </TabsTrigger>
          </TabsList>

          <div className="flex shrink-0 items-center gap-1">
            {!isCollapsed && clearable && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={handleClearCurrent}
                    aria-label={`Clear ${activeTab === "output" ? "compiler output" : "serial logs"}`}
                    className={`${ICON_BUTTON} ${
                      cleared ? "text-[var(--color-warning-amber)]" : "text-muted-foreground hover:text-[var(--color-error-red)]"
                    }`}
                  >
                    {cleared ? <Check className="h-3.5 w-3.5" /> : <RotateCcw className="h-3.5 w-3.5" />}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top">
                  {cleared ? "Cleared" : `Clear ${activeTab === "output" ? "compiler output" : "serial logs"}`}
                </TooltipContent>
              </Tooltip>
            )}

            {collapsible && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={onToggleCollapse}
                    aria-label={isCollapsed ? "Expand diagnostics panel" : "Collapse diagnostics panel"}
                    aria-expanded={!isCollapsed}
                    className={`${ICON_BUTTON} text-muted-foreground hover:text-foreground`}
                  >
                    {isCollapsed ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top">{isCollapsed ? "Expand panel" : "Collapse panel"}</TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>

        {!isCollapsed && (
          <div className="lg-well relative mx-2 mb-2 flex min-h-0 flex-1 overflow-hidden">
            <TabsContent value="problems" className="ide-scroll m-0 flex-1 overflow-y-auto data-[state=inactive]:hidden">
              {problems.length === 0 ? (
                <p className="px-4 py-3 text-xs text-muted-foreground">
                  {hasDiagnosis
                    ? "No problems were reported by the last analysis."
                    : "No problems detected yet. Run Analyze with AI to parse compiler diagnostics and code issues."}
                </p>
              ) : (
                <ul className="space-y-0.5 p-1.5 font-mono text-xs" aria-label="Problems">
                  {problems.map((p, idx) => {
                    const where = p.file || p.location;
                    const pos = typeof p.line === "number" ? `[Ln ${p.line}${p.column ? `, Col ${p.column}` : ""}]` : "";
                    const clickable = Boolean(onSelectProblem && typeof p.line === "number");
                    return (
                      <li key={idx}>
                        <button
                          type="button"
                          disabled={!clickable}
                          onClick={() => clickable && onSelectProblem?.(p)}
                          className="flex w-full items-start gap-2 rounded-lg px-2.5 py-2 lg:py-1.5 text-left min-h-11 lg:min-h-0 transition-colors enabled:hover:bg-white/[0.06] focus-visible:outline-none focus-visible:bg-ide-selected disabled:cursor-default"
                        >
                          <ProblemIcon severity={p.severity} />
                          <span className="min-w-0 flex-1 text-foreground/90 [overflow-wrap:anywhere]">{p.message}</span>
                          <span className="shrink-0 text-muted-foreground/70">
                            {p.source}
                            {where ? ` · ${where}` : ""} {pos}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </TabsContent>

            <TabsContent value="output" className="m-0 flex flex-1 overflow-hidden data-[state=inactive]:hidden">
              <CodeEditor
                value={compilerOutput}
                onChange={onCompilerChange}
                language="plaintext"
                ariaLabel="Compiler output"
                placeholder="Paste GCC / Clang / ARM-GCC compiler diagnostics, build errors, or linker output here…"
              />
            </TabsContent>

            <TabsContent value="terminal" className="m-0 flex-1 overflow-y-auto data-[state=inactive]:hidden">
              <p className="px-4 py-3 font-mono text-xs text-muted-foreground">
                No terminal is attached — this web workspace does not run a shell. Paste build output into OUTPUT
                and device logs into SERIAL / UART.
              </p>
            </TabsContent>

            <TabsContent value="serial" className="m-0 flex flex-1 overflow-hidden data-[state=inactive]:hidden">
              <CodeEditor
                value={serialLogs}
                onChange={onSerialChange}
                language="plaintext"
                ariaLabel="Serial / UART logs"
                placeholder="Paste Serial Monitor traces, UART console logs, panic dumps, or FreeRTOS assertion logs here…"
              />
            </TabsContent>
          </div>
        )}
      </Tabs>
    </section>
  );
}
