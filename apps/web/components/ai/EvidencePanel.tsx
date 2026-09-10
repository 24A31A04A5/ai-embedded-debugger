"use client";

import * as React from "react";
import { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, FileCode, FileTerminal, FileText, Layers, Quote, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { type DocumentCitation } from "./types";

interface EvidencePanelProps {
  evidence: string[];
  citations?: DocumentCitation[] | null;
  groundedSummary?: string | null;
}

function getEvidenceIcon(item: string) {
  const lower = item.toLowerCase();
  if (lower.includes(".c") || lower.includes(".h") || lower.includes(".cpp") || lower.includes("line")) {
    return <FileCode className="h-3.5 w-3.5 text-[var(--color-emerald)] shrink-0 mt-0.5" />;
  }
  if (lower.includes("serial") || lower.includes("log") || lower.includes("panic") || lower.includes("backtrace") || lower.includes("uart")) {
    return <FileTerminal className="h-3.5 w-3.5 text-[var(--color-warning-amber)] shrink-0 mt-0.5" />;
  }
  return <FileText className="h-3.5 w-3.5 text-[var(--accent-indigo)] shrink-0 mt-0.5" />;
}

const EVIDENCE_COLLAPSE_THRESHOLD = 4;
const CITATIONS_COLLAPSE_THRESHOLD = 3;

export function EvidencePanel({ evidence, citations, groundedSummary }: EvidencePanelProps) {
  const hasEvidence = evidence && evidence.length > 0;
  const hasCitations = citations && citations.length > 0;
  const totalCount = (hasEvidence ? evidence.length : 0) + (hasCitations ? citations.length : 0);

  const [evidenceExpanded, setEvidenceExpanded] = useState(
    !hasEvidence || evidence.length <= EVIDENCE_COLLAPSE_THRESHOLD
  );
  const [citationsExpanded, setCitationsExpanded] = useState(
    !hasCitations || citations.length <= CITATIONS_COLLAPSE_THRESHOLD
  );

  if (!hasEvidence && !hasCitations && !groundedSummary) return null;

  const visibleEvidence = evidenceExpanded || !hasEvidence
    ? evidence
    : evidence.slice(0, EVIDENCE_COLLAPSE_THRESHOLD);

  const visibleCitations = citationsExpanded || !hasCitations
    ? citations
    : citations!.slice(0, CITATIONS_COLLAPSE_THRESHOLD);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <Layers className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
          <span>Source Evidence &amp; Grounding</span>
        </div>
        {totalCount > 0 && (
          <Badge variant="outline" className="text-[10px] font-mono border-border/60">
            {totalCount} signal{totalCount === 1 ? "" : "s"} correlated
          </Badge>
        )}
      </div>

      {/* Grounded Summary Callout */}
      {groundedSummary && (
        <div className="p-3 rounded-xl border border-[var(--accent-purple)]/30 bg-[var(--accent-purple)]/5 text-xs text-foreground/90 leading-relaxed">
          <span className="font-semibold text-[var(--accent-purple)] mr-1">RAG Constraint:</span>
          {groundedSummary}
        </div>
      )}

      {/* Datasheet Citations */}
      {hasCitations && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5 text-[var(--accent-indigo)]" />
              <span>Datasheet &amp; Documentation Citations</span>
            </div>
            {citations!.length > CITATIONS_COLLAPSE_THRESHOLD && (
              <button
                type="button"
                onClick={() => setCitationsExpanded((e) => !e)}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/50 rounded px-1"
                aria-expanded={citationsExpanded}
              >
                {citationsExpanded ? (
                  <>
                    <ChevronUp className="h-3 w-3" />
                    <span>Collapse</span>
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3" />
                    <span>Show all {citations!.length}</span>
                  </>
                )}
              </button>
            )}
          </div>
          <div className="space-y-2">
            {visibleCitations!.map((cite, idx) => (
              <div
                key={cite.chunk_id || idx}
                className="p-3 rounded-xl border border-[var(--accent-indigo)]/30 bg-[var(--accent-indigo)]/5 space-y-1.5 transition-colors duration-150 hover:border-[var(--accent-indigo)]/50"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-foreground truncate">
                    {cite.document_name}
                  </span>
                  {typeof cite.page_number === "number" && (
                    <Badge variant="outline" className="text-[9px] font-mono shrink-0">
                      p. {cite.page_number}
                    </Badge>
                  )}
                </div>
                {cite.relevance_explanation && (
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {cite.relevance_explanation}
                  </p>
                )}
                {cite.relevant_snippet && (
                  <div className="flex items-start gap-1.5 p-2 rounded-lg bg-black/20 text-[11px] font-mono text-foreground/80">
                    <Quote className="h-3 w-3 shrink-0 mt-0.5 text-muted-foreground/60" />
                    <span className="break-words line-clamp-3">{cite.relevant_snippet}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Source Evidence & Observations */}
      {hasEvidence && (
        <div className="space-y-2">
          {evidence.length > EVIDENCE_COLLAPSE_THRESHOLD && (
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground">Correlated signals</span>
              <button
                type="button"
                onClick={() => setEvidenceExpanded((e) => !e)}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/50 rounded px-1"
                aria-expanded={evidenceExpanded}
              >
                {evidenceExpanded ? (
                  <>
                    <ChevronUp className="h-3 w-3" />
                    <span>Collapse</span>
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3" />
                    <span>Show all {evidence.length}</span>
                  </>
                )}
              </button>
            </div>
          )}
          <div className="space-y-1.5">
            {visibleEvidence.map((item, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2.5 p-3 rounded-xl border border-border/40 bg-card/40 hover:bg-card/70 hover:border-border/60 transition-all duration-150"
              >
                {getEvidenceIcon(item)}
                <p className="text-xs sm:text-sm font-mono text-muted-foreground leading-relaxed break-words flex-1">
                  {item}
                </p>
              </div>
            ))}
          </div>
          {!evidenceExpanded && evidence.length > EVIDENCE_COLLAPSE_THRESHOLD && (
            <button
              type="button"
              onClick={() => setEvidenceExpanded(true)}
              className="w-full text-center text-[11px] text-muted-foreground hover:text-foreground transition-colors duration-150 py-1.5 rounded-lg hover:bg-white/5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/50"
              aria-label={`Show ${evidence.length - EVIDENCE_COLLAPSE_THRESHOLD} more evidence items`}
            >
              + {evidence.length - EVIDENCE_COLLAPSE_THRESHOLD} more signal{evidence.length - EVIDENCE_COLLAPSE_THRESHOLD === 1 ? "" : "s"}
            </button>
          )}
        </div>
      )}

      <div className="flex items-center gap-1.5 pt-1 text-[11px] text-muted-foreground/70">
        <ShieldCheck className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
        <span>Grounded strictly on uploaded source code, compiler traces, and attached datasheets.</span>
      </div>
    </div>
  );
}
