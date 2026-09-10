"use client";

import React, { useState } from "react";
import {
  Check,
  Copy,
  FileCode,
  RotateCcw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CodeEditor } from "@/components/CodeEditor";

interface CodeWorkspaceProps {
  value: string;
  onChange: (v: string) => void;
  activeFileName?: string;
  onClear?: () => void;
  className?: string;
}

export function CodeWorkspace({
  value,
  onChange,
  activeFileName = "main.c",
  onClear,
  className = "",
}: CodeWorkspaceProps) {
  const [copied, setCopied] = useState(false);
  const [cleared, setCleared] = useState(false);

  const handleCopy = async () => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error("Failed to copy code", e);
    }
  };

  const handleClear = () => {
    if (!onClear) return;
    onClear();
    setCleared(true);
    setTimeout(() => setCleared(false), 1500);
  };

  // Compute real metrics from actual code
  const lineCount = value ? value.split("\n").length : 0;
  const charCount = value ? value.length : 0;
  const isCpp = activeFileName.endsWith(".cpp") || activeFileName.endsWith(".hpp");

  return (
    <div className={`flex flex-1 flex-col overflow-hidden bg-[oklch(0.10_0.015_260)] border border-border/40 rounded-xl shadow-lg relative ${className}`}>
      {/* Editor Tab Framing Bar */}
      <div className="flex items-center justify-between border-b border-border/40 bg-[oklch(0.12_0.015_260/0.95)] px-3 py-1.5 shrink-0 select-none">
        {/* Active file tab */}
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[oklch(0.14_0.02_270)] border border-[var(--accent-purple)]/30 text-foreground font-mono text-xs shadow-xs transition-all duration-150">
            <FileCode className="h-3.5 w-3.5 text-[var(--accent-purple)] shrink-0" />
            <span className="font-medium truncate max-w-[140px] sm:max-w-[220px]">
              {activeFileName}
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-purple)] shadow-[0_0_6px_var(--accent-purple)] ml-1 shrink-0" />
          </div>

          <Badge variant="outline" className="hidden sm:inline-flex text-[10px] font-mono text-muted-foreground border-border/40 py-0.5">
            {isCpp ? "C++20" : "C11 (GCC)"}
          </Badge>
        </div>

        {/* Real Code Stats & Quick Actions */}
        <div className="flex items-center gap-2">
          {lineCount > 0 && (
            <div className="hidden sm:flex items-center gap-2 text-[10px] font-mono text-muted-foreground/70 pr-1">
              <span>{lineCount} lines</span>
              <span>•</span>
              <span>{charCount} chars</span>
            </div>
          )}

          {value && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-6 px-2 text-[11px] gap-1 rounded transition-all duration-150 active:scale-95 ${
                    copied
                      ? "text-[var(--color-emerald)] bg-[var(--color-emerald)]/10"
                      : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                  }`}
                  onClick={handleCopy}
                  aria-label="Copy source code"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3" />
                      <span className="font-medium">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span className="hidden sm:inline">Copy</span>
                    </>
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                {copied ? "Copied to clipboard!" : "Copy source code"}
              </TooltipContent>
            </Tooltip>
          )}

          {value && onClear && (
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
                  onClick={handleClear}
                  aria-label="Clear code editor"
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
                {cleared ? "Editor cleared" : "Clear editor contents"}
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Editor Content Area */}
      <div className="flex flex-1 overflow-hidden relative">
        <CodeEditor
          value={value}
          onChange={onChange}
          language={isCpp ? "cpp" : "c"}
          placeholder="Paste C/C++ firmware source code here, or select an uploaded file from the left panel…"
        />
      </div>
    </div>
  );
}
