"use client";

import React, { useState } from "react";
import { Check, ChevronRight, Copy, FileCode, History, RotateCcw, X } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  CodeEditor,
  type CodeEditorHandle,
  type CursorPosition,
} from "@/components/CodeEditor";
import { getLanguageInfo, type EditorTab } from "./editor-utils";

interface CodeWorkspaceProps {
  value: string;
  onChange: (v: string) => void;
  tabs: EditorTab[];
  activeTabId: string | null;
  onSelectTab?: (id: string) => void;
  onCloseTab?: (id: string) => void;
  onClear?: () => void;
  projectName?: string;
  onCursorChange?: (pos: CursorPosition) => void;
  editorRef?: React.Ref<CodeEditorHandle>;
  className?: string;
}

const UNTITLED: EditorTab = { id: "", name: "Untitled", kind: "scratch" };

function TabIcon({ tab }: { tab: EditorTab }) {
  if (tab.kind === "session") {
    return <History className="h-3.5 w-3.5 shrink-0 text-[var(--accent-purple)]/80" />;
  }
  const ext = tab.name.split(".").pop()?.toLowerCase();
  const color =
    ext === "h" || ext === "hpp"
      ? "text-[oklch(0.72_0.12_300)]"
      : ext === "ino"
        ? "text-[oklch(0.72_0.12_190)]"
        : "text-[oklch(0.70_0.12_250)]";
  return <FileCode className={`h-3.5 w-3.5 shrink-0 ${color}`} />;
}

export function CodeWorkspace({
  value,
  onChange,
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onClear,
  projectName,
  onCursorChange,
  editorRef,
  className = "",
}: CodeWorkspaceProps) {
  const [copied, setCopied] = useState(false);
  const [cleared, setCleared] = useState(false);

  const visibleTabs = activeTabId === null ? [...tabs, UNTITLED] : tabs;
  const activeTab = visibleTabs.find((t) => (t.id || null) === activeTabId) ?? UNTITLED;
  const language = getLanguageInfo(activeTab.kind === "file" ? activeTab.name : null);

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

  const handleTabKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const buttons = Array.from(
      e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')
    );
    const idx = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (idx === -1) return;
    e.preventDefault();
    const next = buttons[(idx + (e.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length];
    next.focus();
    next.click();
  };

  return (
    <section
      aria-label="Code editor"
      className={`flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-ide-editor ${className}`}
    >
      {/* Tab strip */}
      <div className="flex h-11 lg:h-9 shrink-0 items-stretch border-b border-ide-border bg-ide-tabbar select-none">
        <div
          role="tablist"
          aria-label="Open editors"
          className="flex min-w-0 flex-1 items-stretch overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          onKeyDown={handleTabKeyDown}
        >
          {visibleTabs.map((tab) => {
            const isActive = tab === activeTab;
            return (
              <div
                key={tab.id || "untitled"}
                className={`group relative flex shrink-0 items-center border-r border-ide-border-subtle ${
                  isActive
                    ? "bg-ide-editor text-foreground"
                    : "bg-ide-tabbar text-muted-foreground hover:bg-ide-hover hover:text-foreground/90"
                }`}
              >
                {isActive && (
                  <span aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-[var(--accent-purple)]" />
                )}
                {isActive && (
                  <span aria-hidden="true" className="absolute inset-x-0 -bottom-px h-px bg-ide-editor" />
                )}
                <button
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => tab.id && onSelectTab?.(tab.id)}
                  className="flex h-full items-center gap-1.5 pl-3 pr-1.5 font-mono text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[var(--accent-purple)]/60"
                  title={tab.modified ? `${tab.name} (modified in editor, not saved to project)` : tab.name}
                >
                  <TabIcon tab={tab} />
                  <span className={`max-w-[160px] truncate ${tab.kind === "scratch" ? "italic" : ""}`}>
                    {tab.name}
                  </span>
                </button>
                {tab.id && onCloseTab ? (
                  <button
                    type="button"
                    onClick={() => onCloseTab(tab.id)}
                    aria-label={`Close ${tab.name}`}
                    className="relative mr-1.5 flex h-8 w-8 lg:h-5 lg:w-5 items-center justify-center rounded text-muted-foreground hover:bg-white/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/60"
                  >
                    {tab.modified && (
                      <span
                        aria-hidden="true"
                        className="h-2 w-2 rounded-full bg-foreground/70 group-hover:hidden"
                      />
                    )}
                    <X
                      className={`h-3.5 w-3.5 ${
                        tab.modified ? "hidden group-hover:block" : isActive ? "" : "lg:opacity-0 lg:group-hover:opacity-100"
                      }`}
                    />
                  </button>
                ) : (
                  <span className="w-2" />
                )}
              </div>
            );
          })}
        </div>

        {/* Editor actions */}
        <div className="flex shrink-0 items-center gap-0.5 border-l border-ide-border-subtle px-1.5">
          {value && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={handleCopy}
                  aria-label="Copy source code"
                  className={`flex h-9 w-9 lg:h-7 lg:w-7 items-center justify-center rounded transition-colors ${
                    copied
                      ? "text-[var(--color-emerald)]"
                      : "text-muted-foreground hover:bg-ide-hover hover:text-foreground"
                  }`}
                >
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom">{copied ? "Copied to clipboard" : "Copy source code"}</TooltipContent>
            </Tooltip>
          )}
          {value && onClear && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={handleClear}
                  aria-label="Clear code editor"
                  className={`flex h-9 w-9 lg:h-7 lg:w-7 items-center justify-center rounded transition-colors ${
                    cleared
                      ? "text-[var(--color-warning-amber)]"
                      : "text-muted-foreground hover:bg-ide-hover hover:text-[var(--color-error-red)]"
                  }`}
                >
                  {cleared ? <Check className="h-3.5 w-3.5" /> : <RotateCcw className="h-3.5 w-3.5" />}
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom">{cleared ? "Editor cleared" : "Clear editor contents"}</TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Breadcrumbs */}
      <div className="flex h-6 shrink-0 items-center gap-1 overflow-hidden border-b border-ide-border-subtle bg-ide-editor px-3 font-mono text-[11px] text-muted-foreground/80 select-none">
        {projectName && (
          <>
            <span className="truncate">{projectName}</span>
            <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground/50" />
          </>
        )}
        <span className="truncate text-foreground/75">{activeTab.name}</span>
        <span className="ml-auto shrink-0 pl-3 text-muted-foreground/60">{language.label}</span>
      </div>

      <CodeEditor
        ref={editorRef}
        value={value}
        onChange={onChange}
        language={language.id}
        documentKey={activeTab.id || "untitled"}
        onCursorChange={onCursorChange}
        ariaLabel={`Source editor: ${activeTab.name}`}
        placeholder="Paste C/C++ firmware source here, or open a file from the Explorer…"
      />
    </section>
  );
}
