"use client";

import React, { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  FileTerminal,
  RotateCcw,
  Terminal,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CodeEditor } from "@/components/CodeEditor";

interface DiagnosticTabsProps {
  compilerOutput: string;
  onCompilerChange: (v: string) => void;
  serialLogs: string;
  onSerialChange: (v: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  className?: string;
}

export function DiagnosticTabs({
  compilerOutput,
  onCompilerChange,
  serialLogs,
  onSerialChange,
  isCollapsed,
  onToggleCollapse,
  className = "",
}: DiagnosticTabsProps) {
  const [activeTab, setActiveTab] = useState<"compiler" | "serial">("compiler");
  const [cleared, setCleared] = useState(false);

  const compilerLines = compilerOutput ? compilerOutput.split("\n").length : 0;
  const serialLines = serialLogs ? serialLogs.split("\n").length : 0;

  const handleClearCurrent = () => {
    if (activeTab === "compiler") {
      onCompilerChange("");
    } else {
      onSerialChange("");
    }
    setCleared(true);
    setTimeout(() => setCleared(false), 1500);
  };

  const hasCurrentContent = activeTab === "compiler" ? !!compilerOutput : !!serialLogs;

  return (
    <div className={`flex flex-col bg-[oklch(0.11_0.015_260)] border border-border/40 rounded-xl overflow-hidden transition-all duration-200 ${className}`}>
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as "compiler" | "serial")}
        className="flex flex-1 flex-col h-full overflow-hidden"
      >
        {/* Diagnostic Bar Header */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-[oklch(0.12_0.015_260/0.95)] border-b border-border/30 shrink-0">
          <div className="flex items-center gap-2">
            <TabsList className="h-7 bg-black/20 p-0.5 border border-border/30 rounded-md">
              <TabsTrigger
                value="compiler"
                className="h-6 px-2.5 text-xs gap-1.5 data-[state=active]:bg-[var(--accent-purple)]/15 data-[state=active]:text-foreground data-[state=active]:border-[var(--accent-purple)]/30 font-medium transition-all duration-150"
              >
                <FileTerminal className="h-3 w-3 text-[var(--color-warning-amber)]" />
                <span>Compiler Output</span>
                {compilerLines > 0 && (
                  <span className="ml-1 rounded bg-white/10 px-1 text-[9px] font-mono text-muted-foreground">
                    {compilerLines}
                  </span>
                )}
              </TabsTrigger>

              <TabsTrigger
                value="serial"
                className="h-6 px-2.5 text-xs gap-1.5 data-[state=active]:bg-[var(--accent-purple)]/15 data-[state=active]:text-foreground data-[state=active]:border-[var(--accent-purple)]/30 font-medium transition-all duration-150"
              >
                <Terminal className="h-3 w-3 text-[var(--accent-indigo)]" />
                <span>Serial / UART Logs</span>
                {serialLines > 0 && (
                  <span className="ml-1 rounded bg-white/10 px-1 text-[9px] font-mono text-muted-foreground">
                    {serialLines}
                  </span>
                )}
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Actions & Collapse/Expand Toggle */}
          <div className="flex items-center gap-1.5">
            {!isCollapsed && hasCurrentContent && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={`h-6 px-2 text-[11px] gap-1 rounded transition-all duration-150 active:scale-95 ${
                      cleared
                        ? "text-[var(--color-warning-amber)] bg-[var(--color-warning-amber)]/10"
                        : "text-muted-foreground hover:text-[var(--color-error-red)] hover:bg-white/5"
                    }`}
                    onClick={handleClearCurrent}
                    aria-label="Clear active log panel"
                  >
                    {cleared ? (
                      <>
                        <Check className="h-3 w-3" />
                        <span className="hidden sm:inline font-medium">Cleared</span>
                      </>
                    ) : (
                      <>
                        <RotateCcw className="h-3 w-3" />
                        <span className="hidden sm:inline">Clear</span>
                      </>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  {cleared ? "Cleared!" : `Clear ${activeTab === "compiler" ? "compiler output" : "serial logs"}`}
                </TooltipContent>
              </Tooltip>
            )}

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-white/5 rounded transition-all duration-150 active:scale-95"
                  onClick={onToggleCollapse}
                  aria-label={isCollapsed ? "Expand diagnostic drawer" : "Collapse diagnostic drawer"}
                >
                  {isCollapsed ? (
                    <ChevronUp className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                {isCollapsed ? "Expand diagnostic drawer" : "Collapse diagnostic drawer"}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Tab Contents (only when expanded) */}
        {!isCollapsed && (
          <div className="flex flex-1 overflow-hidden relative">
            <TabsContent value="compiler" className="flex-1 h-full m-0 data-[state=inactive]:hidden overflow-hidden">
              <CodeEditor
                value={compilerOutput}
                onChange={onCompilerChange}
                language="bash"
                placeholder="Paste GCC / Clang / ARM-GCC compiler diagnostics, build errors, or linker outputs here…"
              />
            </TabsContent>

            <TabsContent value="serial" className="flex-1 h-full m-0 data-[state=inactive]:hidden overflow-hidden">
              <CodeEditor
                value={serialLogs}
                onChange={onSerialChange}
                language="bash"
                placeholder="Paste Serial Monitor traces, UART console logs, panic dumps, or FreeRTOS assertion logs here…"
              />
            </TabsContent>
          </div>
        )}
      </Tabs>
    </div>
  );
}
