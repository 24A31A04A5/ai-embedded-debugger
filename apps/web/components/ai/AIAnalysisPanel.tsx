"use client";

import * as React from "react";
import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  Info,
  Minus,
  RotateCcw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { type FeedbackResponse } from "@/lib/api-client";
import { type DiagnosisResult } from "./types";
import { CauseList } from "./CauseList";
import { RecommendedSteps } from "./RecommendedSteps";
import { ProposedFix } from "./ProposedFix";
import { EvidencePanel } from "./EvidencePanel";
import { AIResponseSkeleton } from "./AIResponseSkeleton";

export type AnalysisInputs = {
  source: boolean;
  compiler: boolean;
  serial: boolean;
};

interface AIAnalysisPanelProps {
  diagnosis: DiagnosisResult | null;
  isAnalyzing: boolean;
  sessionId?: string | null;
  feedback?: FeedbackResponse | null;
  onSubmitFeedback?: (rating: number) => void;
  error?: string | null;
  onRetry?: () => void;
  inputs?: AnalysisInputs;
}

function SectionLabel({ children, aside }: { children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{children}</h3>
      {aside}
    </div>
  );
}

/** Progressive-disclosure section for secondary diagnosis details. */
function DetailSection({
  label,
  count,
  defaultOpen = false,
  children,
}: {
  label: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-ide-border-subtle">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full min-h-11 lg:min-h-8 items-center gap-1.5 px-4 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:bg-ide-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[var(--accent-purple)]/60"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <span className="flex-1 truncate">{label}</span>
        {typeof count === "number" && (
          <span className="rounded-full bg-white/10 px-1.5 font-mono text-[10px] font-medium normal-case leading-4">
            {count}
          </span>
        )}
      </button>
      {open && <div className="space-y-2 px-4 pb-4 pt-1">{children}</div>}
    </div>
  );
}

function severityVariant(severity: string) {
  if (severity === "critical" || severity === "high") return "error" as const;
  if (severity === "medium") return "warning" as const;
  return "outline" as const;
}

const ITEM = "space-y-1.5 rounded border border-ide-border-subtle bg-white/[0.02] p-2.5";

function ConfidenceMeter({ level }: { level: "high" | "medium" | "low" }) {
  const filled = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const color =
    level === "high"
      ? "bg-[var(--color-success-green)]"
      : level === "medium"
        ? "bg-[var(--color-warning-amber)]"
        : "bg-muted-foreground";
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span key={i} className={`h-1.5 w-7 rounded-full ${i < filled ? color : "bg-white/10"}`} />
        ))}
      </div>
      <span className="text-xs font-medium capitalize text-foreground/90">{level}</span>
    </div>
  );
}

export function AIAnalysisPanel({
  diagnosis,
  isAnalyzing,
  sessionId,
  feedback,
  onSubmitFeedback,
  error,
  onRetry,
  inputs,
}: AIAnalysisPanelProps) {
  const status = isAnalyzing
    ? { label: "Analyzing", dot: "bg-[var(--accent-purple)] animate-pulse motion-reduce:animate-none", text: "text-[oklch(0.80_0.10_290)]" }
    : error
      ? { label: "Analysis failed", dot: "bg-[var(--color-error-red)]", text: "text-[var(--color-error-red)]" }
      : diagnosis
        ? { label: "Analysis complete", dot: "bg-[var(--color-success-green)]", text: "text-foreground/90" }
        : { label: "Awaiting analysis", dot: "bg-muted-foreground/60", text: "text-muted-foreground" };

  const evidenceCount = (diagnosis?.evidence_used?.length ?? 0) + (diagnosis?.datasheet_citations?.length ?? 0);

  return (
    <section aria-label="AI debug" className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-ide-ai">
      {/* Panel title */}
      <div className="flex h-11 lg:h-9 shrink-0 items-center justify-between gap-2 border-b border-ide-border px-4">
        <h2 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-foreground/85">
          <Sparkles className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
          AI Debug
        </h2>
        <span role="status" aria-live="polite" className={`flex items-center gap-1.5 text-[11px] ${status.text}`}>
          <span className={`h-2 w-2 rounded-full ${status.dot}`} aria-hidden="true" />
          {status.label}
        </span>
      </div>

      <div className="ide-scroll min-h-0 flex-1 overflow-y-auto">
        {isAnalyzing && <AIResponseSkeleton />}

        {!isAnalyzing && error && (
          <div className="space-y-3 p-4">
            <div className="flex items-start gap-2.5 rounded border border-[var(--color-error-red)]/30 bg-[var(--color-error-red)]/[0.07] p-3">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-error-red)]" />
              <div className="min-w-0 space-y-1">
                <p className="text-xs font-semibold text-foreground">Diagnostic analysis error</p>
                <p className="text-xs leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">{error}</p>
              </div>
            </div>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                className="min-h-11 lg:min-h-8 gap-1.5 rounded border-ide-border bg-transparent text-xs"
                onClick={onRetry}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry analysis
              </Button>
            )}
          </div>
        )}

        {!isAnalyzing && !error && !diagnosis && (
          <div className="space-y-4 p-4">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Run <span className="font-medium text-[oklch(0.80_0.10_290)]">Analyze with AI</span> to correlate your
              source, compiler output, and serial logs into a root cause, evidence, and a proposed fix.
            </p>
            {inputs && (
              <div>
                <SectionLabel>Inputs</SectionLabel>
                <ul className="space-y-1 text-xs">
                  {(
                    [
                      ["Source code", inputs.source],
                      ["Compiler output", inputs.compiler],
                      ["Serial / UART logs", inputs.serial],
                    ] as const
                  ).map(([label, present]) => (
                    <li key={label} className="flex items-center gap-2">
                      {present ? (
                        <Check className="h-3.5 w-3.5 text-[var(--color-success-green)]" />
                      ) : (
                        <Minus className="h-3.5 w-3.5 text-muted-foreground/50" />
                      )}
                      <span className={present ? "text-foreground/90" : "text-muted-foreground"}>{label}</span>
                      <span className="ml-auto text-[10px] text-muted-foreground/60">{present ? "provided" : "empty"}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {!isAnalyzing && diagnosis && (
          <div className="pb-4">
            <div className="space-y-5 p-4">
              {/* Root cause */}
              <section>
                <SectionLabel>Root Cause</SectionLabel>
                <div className="border-l-2 border-[var(--accent-purple)] pl-3">
                  <p className="text-[13px] font-medium leading-relaxed text-foreground">
                    {diagnosis.root_cause_summary || diagnosis.problem_observed}
                  </p>
                  {diagnosis.root_cause_summary && diagnosis.problem_observed && (
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                      <span className="text-foreground/70">Observed: </span>
                      {diagnosis.problem_observed}
                    </p>
                  )}
                </div>
              </section>

              {/* Confidence */}
              {diagnosis.confidence_level && (
                <section>
                  <SectionLabel>Confidence</SectionLabel>
                  <ConfidenceMeter level={diagnosis.confidence_level} />
                </section>
              )}

              {/* Evidence */}
              {(evidenceCount > 0 || diagnosis.grounded_summary) && (
                <section>
                  <SectionLabel
                    aside={
                      evidenceCount > 0 ? (
                        <span className="font-mono text-[10px] text-muted-foreground/70">
                          {evidenceCount} signal{evidenceCount === 1 ? "" : "s"}
                        </span>
                      ) : undefined
                    }
                  >
                    Evidence
                  </SectionLabel>
                  <EvidencePanel
                    evidence={diagnosis.evidence_used ?? []}
                    citations={diagnosis.datasheet_citations}
                    groundedSummary={diagnosis.grounded_summary}
                  />
                </section>
              )}

              {/* Proposed fix */}
              {(diagnosis.proposed_fix || diagnosis.corrected_code) && (
                <section>
                  <SectionLabel>Proposed Fix</SectionLabel>
                  <ProposedFix proposedFix={diagnosis.proposed_fix} correctedCode={diagnosis.corrected_code} />
                </section>
              )}

              {/* Recommended steps */}
              {diagnosis.recommended_steps?.length > 0 && (
                <section>
                  <SectionLabel>Recommended Steps</SectionLabel>
                  <RecommendedSteps steps={diagnosis.recommended_steps} />
                </section>
              )}
            </div>

            {/* Secondary details */}
            {diagnosis.likely_causes?.length > 0 && (
              <DetailSection label="Likely causes" count={diagnosis.likely_causes.length}>
                <CauseList causes={diagnosis.likely_causes} />
              </DetailSection>
            )}

            {diagnosis.code_issues && diagnosis.code_issues.length > 0 && (
              <DetailSection label="Code issues" count={diagnosis.code_issues.length}>
                {diagnosis.code_issues.map((issue, idx) => (
                  <div key={idx} className={ITEM}>
                    <div className="flex flex-wrap items-center justify-between gap-1.5">
                      <div className="flex items-center gap-2">
                        <Badge variant={severityVariant(issue.severity)} className="rounded px-1.5 font-mono text-[9px] uppercase">
                          {issue.severity}
                        </Badge>
                        <span className="text-xs font-medium capitalize text-foreground">{issue.kind.replace(/_/g, " ")}</span>
                      </div>
                      {issue.location && (
                        <span className="font-mono text-[10px] text-muted-foreground">{issue.location}</span>
                      )}
                    </div>
                    <p className="text-xs leading-relaxed text-foreground/90">{issue.description}</p>
                    {issue.evidence && (
                      <pre className="overflow-x-auto rounded bg-black/25 p-2 font-mono text-[11px] text-muted-foreground">
                        {issue.evidence}
                      </pre>
                    )}
                    {issue.suggestion && (
                      <p className="text-[11px] leading-relaxed text-[var(--color-success-green)]">
                        <span className="font-semibold">Fix: </span>
                        {issue.suggestion}
                      </p>
                    )}
                  </div>
                ))}
              </DetailSection>
            )}

            {diagnosis.compiler_messages && diagnosis.compiler_messages.length > 0 && (
              <DetailSection label="Compiler diagnostics" count={diagnosis.compiler_messages.length}>
                {diagnosis.compiler_messages.map((msg, idx) => (
                  <div key={idx} className={ITEM}>
                    <div className="flex flex-wrap items-center justify-between gap-1.5">
                      <div className="flex items-center gap-1.5">
                        {msg.is_root_cause && (
                          <Badge variant="error" className="rounded px-1.5 font-mono text-[9px] uppercase">
                            Root cause
                          </Badge>
                        )}
                        <Badge variant="outline" className="rounded border-ide-border px-1.5 font-mono text-[9px] uppercase">
                          {msg.message_type.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      {(msg.file || typeof msg.line === "number") && (
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {msg.file || ""}
                          {msg.line ? `:${msg.line}` : ""}
                          {msg.column ? `:${msg.column}` : ""}
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-xs leading-relaxed text-foreground/90 [overflow-wrap:anywhere]">{msg.message}</p>
                    {msg.suggested_fix && (
                      <p className="text-[11px] leading-relaxed text-[var(--color-success-green)]">
                        <span className="font-semibold">Suggestion: </span>
                        {msg.suggested_fix}
                      </p>
                    )}
                  </div>
                ))}
              </DetailSection>
            )}

            {diagnosis.serial_log_events && diagnosis.serial_log_events.length > 0 && (
              <DetailSection label="Serial events" count={diagnosis.serial_log_events.length}>
                {diagnosis.serial_log_events.map((evt, idx) => (
                  <div key={idx} className={ITEM}>
                    <div className="flex flex-wrap items-center justify-between gap-1.5">
                      <div className="flex items-center gap-2">
                        <Badge variant={severityVariant(evt.severity)} className="rounded px-1.5 font-mono text-[9px] uppercase">
                          {evt.event_type.replace(/_/g, " ")}
                        </Badge>
                        {evt.is_repeated && (
                          <span className="font-mono text-[10px] text-[var(--color-warning-amber)]">
                            repeated{evt.repeat_count ? ` ${evt.repeat_count}×` : ""}
                          </span>
                        )}
                      </div>
                      {evt.timestamp && <span className="font-mono text-[10px] text-muted-foreground">{evt.timestamp}</span>}
                    </div>
                    <p className="text-xs leading-relaxed text-foreground/90">{evt.message}</p>
                    {evt.evidence && (
                      <pre className="overflow-x-auto rounded bg-black/25 p-2 font-mono text-[11px] text-muted-foreground">
                        {evt.evidence}
                      </pre>
                    )}
                    {evt.suggested_action && (
                      <p className="text-[11px] leading-relaxed text-[var(--color-success-green)]">
                        <span className="font-semibold">Action: </span>
                        {evt.suggested_action}
                      </p>
                    )}
                  </div>
                ))}
              </DetailSection>
            )}

            {diagnosis.risks_limitations && (
              <DetailSection label="Risks & limitations" defaultOpen>
                <div className="flex items-start gap-2 text-xs leading-relaxed text-foreground/90">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-warning-amber)]" />
                  <p>{diagnosis.risks_limitations}</p>
                </div>
              </DetailSection>
            )}

            {diagnosis.follow_up_required && (
              <DetailSection label="Follow-up verification" defaultOpen>
                <div className="flex items-start gap-2 text-xs leading-relaxed text-foreground/90">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-info-blue)]" />
                  <p>{diagnosis.follow_up_required}</p>
                </div>
              </DetailSection>
            )}

            {sessionId && onSubmitFeedback && (
              <div className="flex items-center justify-between gap-3 border-t border-ide-border-subtle px-4 pt-3">
                <span className="text-xs text-muted-foreground">Was this diagnosis accurate?</span>
                <div className="flex gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className={`h-11 w-11 lg:h-7 lg:w-7 rounded ${
                          feedback?.rating === 1
                            ? "bg-[var(--color-success-green)]/15 text-[var(--color-success-green)]"
                            : "text-muted-foreground hover:bg-ide-hover hover:text-[var(--color-success-green)]"
                        }`}
                        onClick={() => onSubmitFeedback(1)}
                        aria-label="Mark diagnosis as helpful"
                        aria-pressed={feedback?.rating === 1}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top">{feedback?.rating === 1 ? "Marked as helpful" : "Mark as helpful"}</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className={`h-11 w-11 lg:h-7 lg:w-7 rounded ${
                          feedback?.rating === 0
                            ? "bg-[var(--color-error-red)]/15 text-[var(--color-error-red)]"
                            : "text-muted-foreground hover:bg-ide-hover hover:text-[var(--color-error-red)]"
                        }`}
                        onClick={() => onSubmitFeedback(0)}
                        aria-label="Mark diagnosis as unhelpful"
                        aria-pressed={feedback?.rating === 0}
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top">{feedback?.rating === 0 ? "Marked as unhelpful" : "Mark as unhelpful"}</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
