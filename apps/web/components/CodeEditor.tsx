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
  const highlightRef = useRef<HTMLElement>(null);
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

  const handleScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (highlightRef.current?.parentElement) {
      highlightRef.current.parentElement.scrollTop = e.currentTarget.scrollTop;
      highlightRef.current.parentElement.scrollLeft = e.currentTarget.scrollLeft;
    }
  };

  return (
    <div className="relative flex-1 w-full overflow-hidden font-mono text-[13px] leading-6">
      {/* Syntax Highlighted Background */}
      <pre
        className="absolute inset-0 m-0 overflow-hidden bg-transparent p-4 text-foreground/80 whitespace-pre-wrap break-words"
        aria-hidden="true"
      >
        <code ref={highlightRef} className={`language-${language} block min-h-full`} />
      </pre>

      {/* Transparent Textarea Overlay */}
      <textarea
        className="absolute inset-0 m-0 w-full resize-none bg-transparent p-4 text-transparent caret-white outline-none placeholder:text-muted-foreground/30"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={handleScroll}
        placeholder={placeholder}
        spellCheck={false}
      />
    </div>
  );
}
