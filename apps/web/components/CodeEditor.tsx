"use client";

import React, { useEffect, useRef, useState } from "react";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";

interface CodeEditorProps {
  value: string;
  onChange: (val: string) => void;
  language?: string;
  placeholder?: string;
}

export function CodeEditor({
  value,
  onChange,
  language = "c",
  placeholder = "",
}: CodeEditorProps) {
  const highlightViewportRef = useRef<HTMLPreElement>(null);
  const highlightRef = useRef<HTMLElement>(null);
  const lineNumberRef = useRef<HTMLDivElement>(null);
  const [syncedValue, setSyncedValue] = useState(value);

  // Sync value changes from parent
  useEffect(() => {
    setSyncedValue(value);
  }, [value]);

  useEffect(() => {
    if (highlightRef.current) {
      highlightRef.current.removeAttribute("data-highlighted");
      highlightRef.current.className = `language-${language}`;
      highlightRef.current.textContent = syncedValue || " "; // Space ensures height is maintained
      hljs.highlightElement(highlightRef.current);
    }
  }, [syncedValue, language]);

  useEffect(() => {
    if (!lineNumberRef.current) return;
    lineNumberRef.current.innerHTML = "";
    const lineCount = Math.max(1, syncedValue.split("\n").length);
    const fragment = document.createDocumentFragment();

    for (let index = 1; index <= lineCount; index += 1) {
      const line = document.createElement("div");
      line.textContent = String(index);
      fragment.appendChild(line);
    }

    lineNumberRef.current.appendChild(fragment);
  }, [syncedValue]);

  const handleScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (highlightViewportRef.current) {
      highlightViewportRef.current.scrollTop = e.currentTarget.scrollTop;
      highlightViewportRef.current.scrollLeft = e.currentTarget.scrollLeft;
    }
    if (lineNumberRef.current) {
      lineNumberRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  };

  const surfaceClassName =
    "absolute inset-0 m-0 h-full w-full box-border overflow-auto whitespace-pre bg-transparent p-4 font-mono text-[13px] leading-6 tracking-normal tab-size-2 outline-none";

  return (
    <div className="relative flex-1 w-full min-h-0 overflow-hidden bg-[oklch(0.10_0.015_260)] font-mono text-[13px] leading-6">
      <div className="absolute inset-0 flex min-h-0 overflow-hidden">
        <div
          ref={lineNumberRef}
          aria-hidden="true"
          className="h-full shrink-0 overflow-hidden border-r border-border/30 bg-[oklch(0.09_0.015_260)] px-3 py-4 text-right text-[11px] leading-6 tracking-tight text-muted-foreground/45 select-none"
          style={{ fontFamily: "var(--font-geist-mono)" }}
        />

        <div className="relative min-w-0 flex-1 overflow-hidden">
          <pre
            ref={highlightViewportRef}
            aria-hidden="true"
            className={`${surfaceClassName} z-0 text-foreground/90 pointer-events-none`}
          >
            <code
              ref={highlightRef}
              className={`language-${language} block min-h-full min-w-max`}
              style={{
                color: "var(--foreground)",
                fontFamily: "var(--font-geist-mono)",
                fontSize: "13px",
                lineHeight: "24px",
                letterSpacing: "normal",
                whiteSpace: "pre",
              }}
            />
          </pre>

          <textarea
            className={`${surfaceClassName} z-10 resize-none text-transparent caret-[var(--foreground)] selection:bg-[var(--accent-purple)]/25 selection:text-transparent placeholder:text-muted-foreground/30`}
            style={{
              fontFamily: "var(--font-geist-mono)",
              fontSize: "13px",
              lineHeight: "24px",
              letterSpacing: "normal",
              whiteSpace: "pre",
            }}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onScroll={handleScroll}
            placeholder={placeholder}
            spellCheck={false}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            aria-label="Code editor input"
            aria-multiline="true"
            data-gramm="false"
            data-lpignore="true"
          />
        </div>
      </div>
    </div>
  );
}
