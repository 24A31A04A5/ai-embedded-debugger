"use client";

import React, { useEffect, useRef, useState } from "react";
import MonacoEditor, { type OnMount } from "@monaco-editor/react";
import { useTheme } from "next-themes";
import { X } from "lucide-react";

interface CodeDiffPreviewProps {
  /** Original code (left pane) */
  originalCode: string;
  /** AI suggested fix / modified code (right pane) */
  suggestedCode: string;
  /** Filename to display in labels */
  filename: string;
  /** Language identifier (e.g., "c", "cpp") */
  language?: string;
  /** Called when the user closes the preview */
  onClose?: () => void;
  /** Whether the preview is currently loading */
  isLoading?: boolean;
  /** Error state message */
  error?: string | null;
  /** Whether this is a full-file replacement vs partial snippet (affects UI) */
  isFullFileReplacement?: boolean;
}

// Monaco language map - consistent with CodeEditor.tsx
const LANGUAGE_MAP: Record<string, string> = {
  c: "c",
  cpp: "cpp",
  cc: "cpp",
  h: "cpp",
  hpp: "cpp",
  bash: "bash",
  sh: "bash",
  json: "json",
  javascript: "javascript",
  typescript: "typescript",
  python: "python",
  rust: "rust",
  go: "go",
  java: "java",
  markdown: "markdown",
};

/**
 * Monaco Diff Preview - Side-by-side original vs AI suggested fix
 *
 * Design decisions:
 * - Read-only both panes (no user editing)
 * - Dark/light theme compatible via Next.js theme
 * - SSR-safe with client-only rendering fallback
 * - Responsive: stacked layout on narrow screens
 * - Labels: "Original Code" and "AI Suggested Fix"
 * - Displays filename and language
 */
export function CodeDiffPreview({
  originalCode,
  suggestedCode,
  filename = "source.c",
  language = "c",
  onClose,
  isLoading = false,
  error,
  isFullFileReplacement = false,
}: CodeDiffPreviewProps) {
  const { resolvedTheme } = useTheme();
  const leftEditorRef = useRef<{ getValue: () => string; setValue: (v: string) => void } | null>(null);
  const rightEditorRef = useRef<{ getValue: () => string; setValue: (v: string) => void } | null>(null);

  // SSR safety - wait for client-side mount
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const monacoTheme = resolvedTheme === "dark" ? "vs-dark" : "light";
  const monacoLanguage = LANGUAGE_MAP[language] || "plaintext";

  // Handle loading state
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-center bg-[oklch(0.10_0.015_260)]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-current mx-auto my-4" />
        <p className="text-muted-foreground text-sm">Loading AI suggested fix diff…</p>
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-center bg-[oklch(0.10_0.015_260)]">
        <div className="text-red-400 mb-2">⚠️</div>
        <p className="text-sm text-foreground/90">Error loading diff preview: {error}</p>
      </div>
    );
  }

  // Handle empty states
  const hasOriginalCode = Boolean(originalCode && originalCode.trim());
  const hasSuggestedCode = Boolean(suggestedCode && suggestedCode.trim());

  if (!hasOriginalCode && !hasSuggestedCode) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-center bg-[oklch(0.10_0.015_260)]">
        <p className="text-muted-foreground text-sm">No code available for diff preview</p>
      </div>
    );
  }

  // SSR fallback - renders simple text before Monaco loads
  if (!mounted) {
    return (
      <div className="flex-1 flex flex-col sm:flex-row gap-4 p-4 overflow-y-auto bg-[oklch(0.10_0.015_260)]" data-diff-preview>
        <div className="flex-1 min-w-0 rounded-md overflow-hidden">
          <div className="px-3 py-2 border-b bg-[oklch(0.13_0.015_260/0.8)] text-[10px] font-medium uppercase tracking-wider">
            Original Code ({filename})
          </div>
          <pre className="p-4 text-sm text-muted-foreground/70 whitespace-pre-wrap font-mono overflow-x-auto">
            {hasOriginalCode ? originalCode : "No original code"}
          </pre>
        </div>
        <div className="flex-1 min-w-0 rounded-md overflow-hidden">
          <div className="px-3 py-2 border-b bg-[oklch(0.13_0.015_260/0.8)] text-[10px] font-medium uppercase tracking-wider">
            AI Suggested Fix
          </div>
          <pre className="p-4 text-sm text-muted-foreground/70 whitespace-pre-wrap font-mono overflow-x-auto">
            {hasSuggestedCode ? suggestedCode : "No suggested code"}
          </pre>
        </div>
      </div>
    );
  }

  const handleLeftEditorDidMount: OnMount = (editor) => {
    leftEditorRef.current = editor;
  };

  const handleRightEditorDidMount: OnMount = (editor) => {
    rightEditorRef.current = editor;
  };

  // Monaco editor options
  const editorOptions = {
    theme: monacoTheme,
    fontSize: 13,
    fontFamily: "var(--font-geist-mono), 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    lineHeight: 24,
    tabSize: 2,
    insertSpaces: true,
    wordWrap: "on" as const,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    lineNumbers: "on" as const,
    cursorBlinking: "smooth" as const,
    cursorStyle: "line" as const,
    smoothScrolling: true,
    readOnly: true,
    automaticLayout: true,
    renderLineHighlight: "none" as const,
  };

  // Stacked/mobile layout
  if (window.innerWidth < 640) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden bg-[oklch(0.10_0.015_260)]" data-diff-preview>
        <div className="flex items-center justify-between px-3 py-2 border-b border-border/30 bg-[oklch(0.13_0.015_260/0.8)]">
          <span className="text-[10px] font-medium uppercase tracking-wider">Diff Preview</span>
          {onClose && (
            <button
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground cursor-pointer"
              aria-label="Close diff preview"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="flex-1 min-h-0 overflow-hidden lg:grid lg:grid-cols-2">
          {/* Original Code */}
          <div className="flex flex-col border-r border-border/30">
            <div className="px-3 py-2 bg-[oklch(0.13_0.015_260/0.8)] text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Original ({filename})
            </div>
            <div className="flex-1 overflow-auto p-2">
              <MonacoEditor
                height="100%"
                width="100%"
                value={hasOriginalCode ? originalCode : ""}
                language={monacoLanguage}
                theme={monacoTheme}
                options={editorOptions}
              />
            </div>
          </div>
          {/* Suggested Fix */}
          <div className="flex flex-col">
            <div className="px-3 py-2 bg-[oklch(0.13_0.015_260/0.8)] text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              AI Suggested
            </div>
            <div className="flex-1 overflow-auto p-2">
              <MonacoEditor
                height="100%"
                width="100%"
                value={hasSuggestedCode ? suggestedCode : ""}
                language={monacoLanguage}
                theme={monacoTheme}
                options={editorOptions}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Desktop: side-by-side layout
  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-diff-preview>
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/30 bg-[oklch(0.13_0.015_260/0.8)] sm:hidden">
        <span className="text-[10px] font-medium uppercase tracking-wider">Diff Preview</span>
        {onClose && (
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground cursor-pointer"
            aria-label="Close diff preview"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex-1 min-w-0 overflow-hidden bg-[oklch(0.10_0.015_260)] sm:grid sm:grid-cols-2">
        {/* Original Code Pane */}
        <div className="flex flex-col border-r border-border/30">
          <div className="px-3 py-2 border-b border-border/30 bg-[oklch(0.13_0.015_260/0.8)] text-[10px] font-medium uppercase tracking-wider">
            Original ({filename})
          </div>
          <div className="flex-1 overflow-auto p-2">
            <MonacoEditor
              height="100%"
              width="100%"
              value={hasOriginalCode ? originalCode : ""}
              language={monacoLanguage}
              theme={monacoTheme}
              options={editorOptions}
              onMount={handleLeftEditorDidMount}
            />
          </div>
        </div>

        {/* AI Suggested Fix Pane */}
        <div className="flex flex-col">
          <div className="px-3 py-2 border-b border-border/30 bg-[oklch(0.13_0.015_260/0.8)] text-[10px] font-medium uppercase tracking-wider flex items-center justify-between">
            <span>AI Suggested Fix</span>
            {!isFullFileReplacement && (
              <span className="text-[9px] font-mono bg-[var(--color-warning-amber)]/20 text-[var(--color-warning-amber)] px-1.5 py-0.5 rounded border border-[var(--color-warning-amber)]/30">
                snippet
              </span>
            )}
          </div>
          <div className="flex-1 overflow-auto p-2">
            <MonacoEditor
              height="100%"
              width="100%"
              value={hasSuggestedCode ? suggestedCode : ""}
              language={monacoLanguage}
              theme={monacoTheme}
              options={editorOptions}
              onMount={handleRightEditorDidMount}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

CodeDiffPreview.displayName = "CodeDiffPreview";