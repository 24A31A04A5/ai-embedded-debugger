"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import MonacoEditor, { type OnMount } from "@monaco-editor/react";
import { useTheme } from "next-themes";
import { CheckCircle2, FileWarning, Wrench, X, Download, RotateCcw, AlertTriangle, History } from "lucide-react";

import { Button } from "@/components/ui/button";
import { generateUnifiedDiff, downloadPatch } from "@/lib/diff-utils";
import { computeSimpleHash } from "@/lib/hash-utils";

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
  /** Current code content in the editor (for stale content detection) */
  currentCode?: string;
  /** Called when user applies the fix (receives suggested code) */
  onApplyFix?: (suggestedCode: string) => void;
  /** Whether a fix has been applied (shows success state) */
  fixApplied?: boolean;
  /** Called when undo triggered (receives original code) */
  onUndoFix?: (originalCode: string) => void;
  /** Called when redo triggered (receives redone code) */
  onRedoFix?: (redoneCode: string) => void;
  /** Whether undo is available */
  canUndo?: boolean;
  /** Whether redo is available */
  canRedo?: boolean;
  /** Hash of suggested code when fix was suggested (for stale detection) */
  suggestedCodeHash?: string;
  /** Callback when user exports patch */
  onExportPatch?: () => void;
}

// Safety validation result
type SafetyCheckResult = {
  isSafe: boolean;
  warnings: string[];
  blockingIssues: string[];
  canApplyAnyway: boolean;
};

/**
 * Performs safety validation on a proposed code fix
 */
function validateFixSafety(
  proposedCode: string,
  currentCode: string,
  filename: string,
  isFullFileReplacement: boolean
): SafetyCheckResult {
  const warnings: string[] = [];
  const blockingIssues: string[] = [];
  let canApplyAnyway = false;

  // Check for empty proposal
  if (!proposedCode || proposedCode.trim().length === 0) {
    blockingIssues.push("Proposed fix is empty");
    return { isSafe: false, warnings, blockingIssues, canApplyAnyway };
  }

  // Check for suspicious patterns that might indicate a hallucinated fix
  const suspiciousPatterns = [
    /function\s+\w*\s*\(\s*\)\s*\{/,  // Generic function without context
    /class\s+\w*\s*\{/,  // Class definition without context
    /^\s*\n\s*\n\s*\n/,  // Mostly whitespace
  ];

  for (const pattern of suspiciousPatterns) {
    if (pattern.test(proposedCode)) {
      if (!isFullFileReplacement) {
        warnings.push(`Proposed fix appears to be incomplete or placeholder code`);
      }
      break;
    }
  }

  // Check if this looks like a snippet with proper context
  if (!isFullFileReplacement) {
    const hasContext = proposedCode.includes("//") || proposedCode.includes("#include") ||
                       proposedCode.includes("#define") || proposedCode.includes("void") ||
                       proposedCode.includes("int main") || proposedCode.includes("setup(") ||
                       proposedCode.includes("loop(");

    if (!hasContext && proposedCode.split("\n").length < 3) {
      warnings.push("Fix appears to be a very short snippet - verify it fits your context");
    }
  }

  // Check for massive changes that might indicate wrong target
  if (isFullFileReplacement) {
    const ratio = proposedCode.length / Math.max(currentCode.length, 1);
    if (ratio > 10 || ratio < 0.1) {
      warnings.push(`Significant size difference between current and proposed code (${(ratio).toFixed(1)}x) - possible wrong file target`);
      // Size mismatch is a warning, user can apply anyway after review
      canApplyAnyway = true;
    }
  }

  return { isSafe: blockingIssues.length === 0, warnings, blockingIssues, canApplyAnyway };
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
 * Features:
 * - Read-only both panes (no user editing)
 * - Dark/light theme compatible via Next.js theme
 * - SSR-safe with client-only rendering fallback
 * - Responsive: stacked layout on narrow screens
 * - Apply Fix button with safety validation
 * - Undo/Redo capability after applying fix
 * - Patch export (unified diff format)
 * - Stale content detection
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
  currentCode = "",
  onApplyFix,
  fixApplied = false,
  onUndoFix,
  onRedoFix,
  canUndo = false,
  canRedo = false,
  suggestedCodeHash,
  onExportPatch,
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

  // Safety validation state
  const [validationOpen, setValidationOpen] = useState(false);
  const [validationResult, setValidationResult] = useState<SafetyCheckResult | null>(null);

  // Stale detection state
  const [showStaleWarning, setShowStaleWarning] = useState(false);
  const isStale = suggestedCodeHash && currentCode && computeSimpleHash(currentCode) !== suggestedCodeHash;

  // Check stale on mount and when currentCode changes
  useEffect(() => {
    if (isStale) {
      setShowStaleWarning(true);
    }
  }, [isStale]);

  // Handle Apply Fix click
  const handleApplyFix = useCallback(() => {
    if (!onApplyFix || !suggestedCode) return;

    // Block if content is stale - this is a critical issue
    if (isStale) {
      setShowStaleWarning(true);
      return;
    }

    // Run safety check
    const result = validateFixSafety(suggestedCode, currentCode, filename, isFullFileReplacement);
    setValidationResult(result);

    if (!result.isSafe) {
      // Block application due to critical issues (empty, placeholder)
      setValidationOpen(true);
      return;
    }

    // Auto-apply if safe and no warnings
    if (result.warnings.length === 0) {
      onApplyFix(suggestedCode);
    } else {
      setValidationOpen(true);
    }
  }, [onApplyFix, suggestedCode, currentCode, filename, isFullFileReplacement, isStale]);

  // Handle confirm apply with warnings
  const handleConfirmApply = useCallback(() => {
    if (!onApplyFix || !suggestedCode) return;

    // Block stale content - cannot apply fix to changed code
    if (isStale) {
      setValidationOpen(false);
      return;
    }

    onApplyFix(suggestedCode);
    setValidationOpen(false);
  }, [onApplyFix, suggestedCode, isStale]);

  // Handle confirm stale content (force apply despite change)
  const handleConfirmStaleApply = useCallback(() => {
    if (!onApplyFix || !suggestedCode) return;
    onApplyFix(suggestedCode);
    setShowStaleWarning(false);
  }, [onApplyFix, suggestedCode]);

  // Handle export patch
  const handleExportPatch = useCallback(() => {
    try {
      const diff = generateUnifiedDiff(originalCode, suggestedCode, filename);
      downloadPatch(diff, `${filename.replace(/\.[^.]+$/, "")}.patch`);
      if (onExportPatch) onExportPatch();
    } catch (e) {
      console.error("Failed to export patch", e);
    }
  }, [originalCode, suggestedCode, filename, onExportPatch]);

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

  // Safety validation dialog
  const SafetyValidationDialog = () => {
    if (!validationResult) return null;

    const hasBlocking = validationResult.blockingIssues.length > 0;
    const hasWarnings = validationResult.warnings.length > 0;
    const isSafe = validationResult.isSafe;

    if (!validationOpen && isSafe) return null;

    return (
      <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-10 rounded-xl p-4">
        <div className="bg-card rounded-xl border border-border/60 p-4 w-full max-w-sm">
          <div className="flex items-start gap-3">
            <FileWarning className="h-5 w-5 text-[var(--color-warning-amber)] shrink-0 mt-0.5" />
            <div className="flex-1 space-y-2">
              <h4 className="text-sm font-semibold text-foreground">
                Safety Check
              </h4>
              {hasBlocking && (
                <div className="bg-red-50 border border-red-200 dark:bg-red-950/30 dark:border-red-800 rounded-lg p-2.5">
                  <p className="text-xs text-red-700 dark:text-red-300 font-medium">Blocking Issues:</p>
                  <ul className="text-xs text-red-600 dark:text-red-400 ml-2 list-disc list-inside">
                    {validationResult.blockingIssues.map((issue, i) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              {hasWarnings && (
                <div className="bg-amber-50 border border-amber-200 dark:bg-amber-950/30 dark:border-amber-800 rounded-lg p-2.5">
                  <p className="text-xs text-amber-700 dark:text-amber-300 font-medium">Warnings:</p>
                  <ul className="text-xs text-amber-600 dark:text-amber-400 ml-2 list-disc list-inside">
                    {validationResult.warnings.map((warning, i) => (
                      <li key={i}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-3">
            {hasBlocking ? (
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => setValidationOpen(false)}
              >
                Close
              </Button>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs"
                  onClick={() => setValidationOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="text-xs"
                  onClick={handleConfirmApply}
                >
                  Apply Anyway
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  // Stale content warning dialog
  const StaleWarningDialog = () => {
    if (!showStaleWarning) return null;

    return (
      <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-10 rounded-xl p-4">
        <div className="bg-card rounded-xl border border-border/60 p-4 w-full max-w-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-[var(--color-warning-amber)] shrink-0 mt-0.5" />
            <div className="flex-1 space-y-2">
              <h4 className="text-sm font-semibold text-foreground">
                Code Has Changed
              </h4>
              <p className="text-xs text-muted-foreground">
                The code in the editor has been modified since this fix was suggested.
                Applying the fix may not produce the expected results.
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() => setShowStaleWarning(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              className="text-xs"
              onClick={handleConfirmStaleApply}
            >
              Apply Anyway
            </Button>
          </div>
        </div>
      </div>
    );
  };

  // Stacked/mobile layout
  if (window.innerWidth < 640) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden bg-[oklch(0.10_0.015_260)] relative" data-diff-preview>
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
        <SafetyValidationDialog />
        <StaleWarningDialog />
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
            <div className="px-3 py-2 bg-[oklch(0.13_0.015_260/0.8)] text-[10px] font-medium uppercase tracking-wider text-muted-foreground flex items-center justify-between">
              <span>AI Suggested</span>
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
              />
            </div>
            {(onApplyFix || onUndoFix || onRedoFix || onExportPatch) && (
              <div className="p-2 border-t border-border/30 space-y-2">
                {/* Action buttons row */}
                <div className="flex gap-2">
                  {onApplyFix && !fixApplied && (
                    <Button
                      variant="default"
                      size="sm"
                      className="flex-1 text-xs"
                      onClick={handleApplyFix}
                      disabled={fixApplied}
                    >
                      <Wrench className="h-3.5 w-3.5 mr-1.5" />
                      <span>Apply Fix</span>
                    </Button>
                  )}
                  {fixApplied && onUndoFix && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 text-xs"
                      onClick={() => onUndoFix(originalCode)}
                    >
                      <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                      <span>Undo</span>
                    </Button>
                  )}
                  {canUndo && onUndoFix && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => onUndoFix(originalCode)}
                      title="Undo (Ctrl+Z)"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {canRedo && onRedoFix && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => onRedoFix(suggestedCode)}
                      title="Redo (Ctrl+Y)"
                    >
                      <History className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {onExportPatch && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs"
                      onClick={handleExportPatch}
                      title="Export Patch"
                    >
                      <Download className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
                {/* Fix applied state */}
                {fixApplied && (
                  <div className="flex items-center justify-center gap-2 p-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    <span className="text-xs text-emerald-400 font-medium">Fix Applied</span>
                  </div>
                )}
              </div>
            )}
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

      <SafetyValidationDialog />
      <StaleWarningDialog />

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

          {/* Action Buttons */}
          {(onApplyFix || onUndoFix || onRedoFix || onExportPatch) && (
            <div className="p-3 border-t border-border/30 bg-[oklch(0.13_0.015_260/0.6)] space-y-2">
              {/* Action buttons row */}
              <div className="flex items-center gap-2 flex-wrap">
                {onApplyFix && !fixApplied && (
                  <Button
                    variant="default"
                    size="sm"
                    className={`flex-1 sm:flex-none text-xs gap-1.5 ${fixApplied ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}`}
                    onClick={handleApplyFix}
                    disabled={fixApplied}
                  >
                    <Wrench className="h-3.5 w-3.5" />
                    <span>Apply Fix</span>
                  </Button>
                )}
                {fixApplied && onUndoFix && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 sm:flex-none text-xs gap-1.5"
                    onClick={() => onUndoFix(originalCode)}
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    <span>Undo</span>
                  </Button>
                )}
                {canUndo && onUndoFix && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => onUndoFix(originalCode)}
                    title="Undo (Ctrl+Z)"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </Button>
                )}
                {canRedo && onRedoFix && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => onRedoFix(suggestedCode)}
                    title="Redo (Ctrl+Y)"
                  >
                    <History className="h-3.5 w-3.5" />
                  </Button>
                )}
                {onExportPatch && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs ml-auto"
                    onClick={handleExportPatch}
                    title="Export Patch"
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Export Patch</span>
                  </Button>
                )}
              </div>
              {/* Fix applied state */}
              {fixApplied && (
                <div className="flex items-center justify-center gap-2 p-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-xs text-emerald-400 font-medium">Fix Applied</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

CodeDiffPreview.displayName = "CodeDiffPreview";