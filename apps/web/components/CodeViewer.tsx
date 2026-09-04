"use client";

import React, { useEffect, useRef } from "react";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css"; // Using github dark style to match dark theme

interface CodeViewerProps {
  code: string;
  language?: string;
  className?: string;
}

export function CodeViewer({ code, language = "c", className = "" }: CodeViewerProps) {
  const codeRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (codeRef.current) {
      // Remove any previous highlight classes and attributes
      codeRef.current.removeAttribute("data-highlighted");
      codeRef.current.className = `language-${language}`;
      codeRef.current.textContent = code;
      hljs.highlightElement(codeRef.current);
    }
  }, [code, language]);

  return (
    <pre className={`max-w-full overflow-x-auto rounded-md border border-[var(--color-code-border)] bg-[#0d1117] p-4 font-mono text-[13px] text-foreground/80 ${className}`}>
      <code ref={codeRef} className={`language-${language}`}>
        {code}
      </code>
    </pre>
  );
}
