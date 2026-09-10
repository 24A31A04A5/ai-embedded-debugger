"use client";

import * as React from "react";
import { useState } from "react";
import { Check, Copy, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
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
    <div className="space-y-3">
      {/* Explanation text */}
      <div className="p-3.5 rounded-xl border border-border/50 bg-card/60 backdrop-blur-sm">
        <p className="text-xs sm:text-sm leading-relaxed text-foreground/90 font-medium">
          {proposedFix}
        </p>
      </div>

      {/* Corrected Code Block */}
      {correctedCode && (
        <div className="rounded-xl border border-border/60 bg-[var(--color-code-bg)] overflow-hidden shadow-lg">
          <div className="flex items-center justify-between px-3.5 py-2 border-b border-border/50 bg-card/80 text-xs">
            <div className="flex items-center gap-2 text-muted-foreground font-mono text-[11px]">
              <Wrench className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
              <span>{isDiff ? "Proposed Patch Diff" : "Corrected Firmware Snippet"}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2.5 text-[11px] gap-1.5 text-muted-foreground hover:text-foreground"
              onClick={handleCopy}
              aria-label="Copy corrected code"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-[var(--color-success-green)]" />
                  <span className="text-[var(--color-success-green)] font-medium">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy Code</span>
                </>
              )}
            </Button>
          </div>

          <div className="overflow-x-auto">
            <CodeViewer
              code={correctedCode}
              language={isDiff ? "diff" : "cpp"}
              className="border-0 rounded-none p-4 text-[12px] sm:text-[13px] leading-relaxed"
            />
          </div>
        </div>
      )}
    </div>
  );
}
