"use client";

import React, { useEffect, useRef } from "react";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";

interface CodeViewerProps {
  code: string;
  language?: string;
  className?: string;
  showLineNumbers?: boolean;
  highlightLines?: number[];
}

export function CodeViewer({
  code,
  language = "c",
  className = "",
  showLineNumbers = false,
  highlightLines = [],
}: CodeViewerProps) {
  const codeRef = useRef<HTMLElement>(null);
  const lineNumbersRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (codeRef.current) {
      codeRef.current.removeAttribute("data-highlighted");
      codeRef.current.className = `language-${language}`;
      codeRef.current.textContent = code;
      hljs.highlightElement(codeRef.current);
    }

    // Generate line numbers if needed
    if (showLineNumbers && lineNumbersRef.current) {
      const lineCount = code.split("\n").length;
      lineNumbersRef.current.innerHTML = "";
      for (let i = 1; i <= lineCount; i++) {
        const line = document.createElement("div");
        line.textContent = String(i);
        line.className = "text-[11px] leading-6 text-muted-foreground/50 select-none";
        if (highlightLines.includes(i)) {
          line.classList.add("bg-[var(--accent-purple)]/20", "font-semibold", "text-[var(--accent-purple)]");
        }
        lineNumbersRef.current.appendChild(line);
      }
    }
  }, [code, language, showLineNumbers, highlightLines]);

  return (
    <div className={`flex overflow-x-auto rounded-md border border-[var(--color-code-border)] bg-[#0d1117] ${className}`}>
      {showLineNumbers && (
        <div
          ref={lineNumbersRef}
          className="flex flex-col min-w-[3rem] px-2 py-4 border-r border-[var(--color-code-border)] bg-[#0d1117]/80 text-right select-none"
          style={{ fontFamily: "var(--font-geist-mono)", fontSize: "13px", lineHeight: "24px" }}
        />
      )}
      <pre className="flex-1 min-w-0 p-4 font-mono text-[13px] text-foreground/80 overflow-x-auto" style={{ fontFamily: "var(--font-geist-mono)", fontSize: "13px", lineHeight: "24px" }}>
        <code ref={codeRef} className={`language-${language}`}>
          {code}
        </code>
      </pre>
    </div>
  );
}