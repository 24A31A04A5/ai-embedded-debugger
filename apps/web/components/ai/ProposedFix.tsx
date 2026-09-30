"use client";

import * as React from "react";
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { CodeViewer } from "@/components/CodeViewer";

interface ProposedFixProps {
  proposedFix: string;
  correctedCode?: string | null;
}

export function ProposedFix({ proposedFix, correctedCode }: ProposedFixProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const textToCopy = correctedCode || proposedFix;
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error("Failed to copy code to clipboard", e);
    }
  };

  const isDiff =
    correctedCode &&
    (correctedCode.includes("\n+") ||
      correctedCode.includes("\n-") ||
      correctedCode.startsWith("+") ||
      correctedCode.startsWith("-"));

  return (
    <div className="space-y-2.5">
      {proposedFix && <p className="text-xs leading-relaxed text-foreground/90">{proposedFix}</p>}

      {correctedCode && (
        <div className="overflow-hidden rounded border border-ide-border bg-ide-editor">
          <div className="flex h-11 lg:h-7 items-center justify-between border-b border-ide-border-subtle bg-ide-tabbar pl-2.5 pr-1">
            <span className="font-mono text-[11px] text-muted-foreground">
              {isDiff ? "patch.diff" : "Corrected code"}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              aria-label="Copy corrected code"
              className={`flex h-9 lg:h-6 items-center gap-1 rounded px-2 text-[11px] ${
                copied ? "text-[var(--color-success-green)]" : "text-muted-foreground hover:bg-ide-hover hover:text-foreground"
              }`}
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <CodeViewer
            code={correctedCode}
            language={isDiff ? "diff" : "cpp"}
            className="max-h-80 rounded-none border-0 bg-transparent p-3 text-[12px] leading-[18px]"
          />
        </div>
      )}
    </div>
  );
}
