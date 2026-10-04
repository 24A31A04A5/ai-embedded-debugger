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
        <div className="lg-well overflow-hidden">
          <div className="flex h-12 lg:h-8 items-center justify-between border-b border-white/[0.06] pl-3 pr-1">
            <span className="font-mono text-[11px] text-muted-foreground">
              {isDiff ? "patch.diff" : "Corrected code"}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              aria-label="Copy corrected code"
              className={`flex h-11 lg:h-6 items-center gap-1 rounded-full px-3 lg:px-2.5 text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60 ${
                copied ? "bg-[var(--color-success-green)]/15 text-[var(--color-success-green)]" : "lg-ghost text-muted-foreground hover:text-foreground"
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
