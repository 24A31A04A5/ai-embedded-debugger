"use client";

import React, { useEffect, useRef, useState } from "react";
import MonacoEditor, { type OnMount } from "@monaco-editor/react";
import { useTheme } from "next-themes";

interface CodeEditorProps {
  value: string;
  onChange: (val: string) => void;
  language?: string;
  placeholder?: string;
}

// Map editor languages to Monaco languages
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

// Monaco editor options optimized for embedded debugging
const MONACO_OPTIONS: Omit<Record<string, unknown>, "wrapLines" | "wordWrapStrategy" | "placeholder"> = {
  theme: "vs-dark",
  fontSize: 13,
  fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
  lineHeight: 24,
  letterSpacing: 0,
  tabSize: 2,
  insertSpaces: true,
  wordWrap: "on",
  minimap: {
    enabled: false,
  },
  scrollBeyondLastLine: false,
  folding: true,
  foldingStrategy: "auto",
  lineNumbers: "on",
  lineNumbersMinChars: 3,
  roundedChars: false,
  cursorBlinking: "smooth",
  cursorStyle: "line",
  smoothScrolling: true,
  mouseWheelZoom: false,
  quickSuggestions: {
    other: true,
    comments: false,
    strings: false,
  },
  suggest: {
    showKeywords: false,
    showSnippets: false,
  },
  accessibilitySupport: "on",
  cursorSurroundings: 0,
  selectionHighlight: true,
  renderLineHighlight: "none",
  codeLenses: false,
};

// Type for the Monaco editor instance - matches IStandaloneCodeEditor
type MonacoEditorInstance = {
  getValue(): string;
  setValue(value: string): void;
};

export function CodeEditor({
  value,
  onChange,
  language = "c",
  placeholder = "",
}: CodeEditorProps) {
  const editorRef = useRef<MonacoEditorInstance | null>(null);
  const [mounted, setMounted] = useState(false);
  const { resolvedTheme } = useTheme();

  // Ensure component is mounted before rendering Monaco (prevents SSR issues)
  useEffect(() => {
    setMounted(true);
  }, []);

  // Handle editor mount
  const handleEditorDidMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  // Handle value changes
  const handleEditorChange = (newValue: string | undefined) => {
    if (newValue !== undefined) {
      onChange(newValue);
    }
  };

  // Get the monospace font from CSS variables
  const getFontFamily = () => {
    return "var(--font-geist-mono), 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace";
  };

  // Get Monaco theme based on Next.js theme
  const getMonacoTheme = () => {
    return resolvedTheme === "dark" ? "vs-dark" : "light";
  };

  // Apply theme changes using updateOptions
  useEffect(() => {
    if (editorRef.current) {
      const theme = resolvedTheme === "dark" ? "vs-dark" : "light";
      (editorRef.current as unknown as { updateOptions: (options: { theme?: string }) => void }).updateOptions({ theme });
    }
  }, [resolvedTheme]);

  // Handle value prop changes
  useEffect(() => {
    if (editorRef.current && value !== undefined) {
      const currentValue = editorRef.current.getValue();
      if (currentValue !== value) {
        editorRef.current.setValue(value);
      }
    }
  }, [value]);

  // SSR fallback - renders a simple terminal-style view before Monaco loads
  if (!mounted) {
    return (
      <div className="relative flex-1 w-full min-h-0 overflow-hidden bg-[oklch(0.0a_0.015_260)] font-mono text-[13px] leading-6">
        <div className="absolute inset-0 flex min-h-0 overflow-hidden">
          <div
            aria-hidden="true"
            className="h-full shrink-0 overflow-hidden border-r border-border/30 bg-[oklch(0.09_0.015_260)] px-3 py-4 text-right text-[11px] leading-6 tracking-tight text-muted-foreground/45 select-none"
            style={{ fontFamily: "var(--font-geist-mono)" }}
          />
          <div className="relative min-w-0 flex-1 overflow-hidden p-3">
            <pre
              className="w-full h-full resize-none bg-transparent text-transparent caret-[var(--foreground)] selection:bg-[var(--accent-purple)]/25 selection:text-transparent placeholder:text-muted-foreground/30 font-mono text-[13px] leading-6 tracking-normal tab-size-2 outline-none whitespace-pre-wrap"
              style={{
                fontFamily: "var(--font-geist-mono)",
                fontSize: "13px",
                lineHeight: "24px",
                letterSpacing: "normal",
                color: "var(--foreground)",
              }}
            >
              {value || placeholder || "Code preview will appear here after hydration..."}
            </pre>
          </div>
        </div>
      </div>
    );
  }

  const editorOptions = {
    ...MONACO_OPTIONS,
    fontFamily: getFontFamily(),
    theme: getMonacoTheme(),
    wordWrap: "on" as const,
    placeholder,
  };

  return (
    <div className="relative flex-1 w-full min-h-0 overflow-hidden bg-[oklch(0.10_0.015_260)] font-mono text-[13px] leading-6">
      <MonacoEditor
        height="100%"
        width="100%"
        value={value ?? ""}
        language={LANGUAGE_MAP[language] || "plaintext"}
        beforeMount={(monaco) => {
          // Load language configurations for C/C++ if available
          if (language === "cpp" || language === "c") {
            monaco.languages.registerCompletionItemProvider("cpp", {
              provideCompletionItems: () => ({ items: [] }),
            });
          }
        }}
        onMount={handleEditorDidMount}
        onChange={handleEditorChange}
        options={editorOptions}
      />
    </div>
  );
}