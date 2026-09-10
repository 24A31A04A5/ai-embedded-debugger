"use client";

import * as React from "react";
import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bug,
  ChevronDown,
  ChevronUp,
  Code2,
  Cpu,
  FileSearch,
  FileTerminal,
  Lightbulb,
  RotateCcw,
  Sparkles,
  Terminal,
  ThumbsDown,
  ThumbsUp,
  Wrench,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { AIRetrievalBadge } from "./AIRetrievalBadge";
import { AIResponseSkeleton } from "./AIResponseSkeleton";

interface AIAnalysisPanelProps {
  diagnosis: DiagnosisResult | null;
  isAnalyzing: boolean;
  sessionId?: string | null;
  feedback?: FeedbackResponse | null;
  onSubmitFeedback?: (rating: number) => void;
  error?: string | null;
  onRetry?: () => void;
}

/** Collapsible section wrapper for dense item lists */
function CollapsibleSection({
  label,
  count,
  children,
  defaultOpen = true,
}: {
  label: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 rounded-lg px-1 py-0.5 text-left transition-colors duration-150 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/40"
        aria-expanded={isOpen}
      >
        <span className="text-[11px] font-medium text-muted-foreground/80">
          {label}
        </span>
        <div className="flex items-center gap-1.5">
          <Badge variant="outline" className="text-[9px] font-mono border-border/50">
            {count}
          </Badge>
          <span className="text-muted-foreground/60">
            {isOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </span>
        </div>
      </button>
      {isOpen && (
        <div className="space-y-2 animate-fade-in motion-reduce:animate-none">
          {children}
        </div>
      )}
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
}: AIAnalysisPanelProps) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden border-t border-border/60 lg:border-t-0 lg:border-l bg-background">
      {/* Panel Top Control Header */}
      <div className="flex items-center justify-between border-b border-border/40 bg-[oklch(0.13_0.015_260/0.85)] backdrop-blur-xl px-4 py-2.5 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-[var(--accent-purple)] to-[var(--accent-indigo)] text-white shadow-sm shadow-[var(--accent-purple)]/20">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <span className="text-xs font-semibold tracking-tight text-foreground flex items-center gap-1.5">
            <span>AI Diagnostic Intelligence</span>
          </span>
          {diagnosis?.confidence_level && (
            <span className="hidden sm:inline-block rounded bg-[var(--accent-purple)]/10 px-1.5 py-0.5 text-[9px] font-mono font-medium text-[var(--accent-purple)] border border-[var(--accent-purple)]/20 uppercase">
              {diagnosis.confidence_level} Confidence
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {diagnosis && (
            <AIRetrievalBadge
              evidenceCount={diagnosis.evidence_used?.length}
              citationCount={diagnosis.datasheet_citations?.length}
              className="hidden sm:inline-flex"
            />
          )}

          <Badge
            variant={
              isAnalyzing
                ? "ai"
                : error
                  ? "error"
                  : diagnosis
                    ? "success"
                    : "outline"
            }
            className="text-[10px] font-medium"
          >
            {isAnalyzing
              ? "Analyzing..."
              : error
                ? "Analysis Failed"
                : diagnosis
                  ? "Diagnosis Complete"
                  : "Awaiting Analysis"}
          </Badge>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto">
        {/* Loading state */}
        {isAnalyzing && <AIResponseSkeleton />}

        {/* Error state */}
        {!isAnalyzing && error && (
          <div className="flex h-full flex-col items-center justify-center gap-4 px-6 py-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--color-error-red)]/30 bg-[var(--color-error-red)]/10 text-[var(--color-error-red)] shadow-sm">
              <AlertCircle className="h-6 w-6" />
            </div>
            <div className="max-w-sm space-y-1.5">
              <h3 className="text-sm font-semibold text-foreground">
                Diagnostic Analysis Error
              </h3>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {error}
              </p>
            </div>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 text-xs gap-1.5 border-border/60 hover:border-[var(--accent-purple)]/50 transition-all duration-150 active:scale-95"
                onClick={onRetry}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Retry Analysis</span>
              </Button>
            )}
          </div>
        )}

        {/* Empty state */}
        {!isAnalyzing && !error && !diagnosis && (
          <div className="flex h-full flex-col items-center justify-center gap-4 px-6 py-12 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--accent-purple)]/30 bg-[var(--accent-purple)]/10 text-[var(--accent-purple)] shadow-[0_0_20px_oklch(0.60_0.22_290/0.15)]">
              <Cpu className="h-7 w-7" />
            </div>

            <div className="max-w-xs space-y-1.5">
              <h3 className="text-sm font-semibold font-display text-foreground">
                AI Diagnostic Engine Ready
              </h3>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Click{" "}
                <span className="font-semibold text-[var(--accent-purple)]">
                  &quot;Analyze with AI&quot;
                </span>{" "}
                to correlate compiler error cascades, UART panic logs, and MCU register maps.
              </p>
            </div>

            <div className="mt-4 w-full max-w-sm space-y-2 text-left">
              {[
                {
                  icon: Bug,
                  title: "Compiler Error Disassembly",
                  desc: "Pinpoints undeclared types, linker clashes, and syntax faults",
                },
                {
                  icon: FileSearch,
                  title: "Datasheet RAG Cross-Reference",
                  desc: "Verifies register bitmasks and peripheral pin allocations",
                },
                {
                  icon: Wrench,
                  title: "Automated Patch Generation",
                  desc: "Produces verified C/C++ diffs ready to commit",
                },
              ].map((feat, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 p-2.5 rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm transition-all duration-200 hover:border-[var(--accent-purple)]/40 hover:bg-card/80"
                >
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-purple)]/10 border border-[var(--accent-purple)]/20 text-[var(--accent-purple)]">
                    <feat.icon className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-foreground/90">{feat.title}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{feat.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Diagnosis completed view */}
        {!isAnalyzing && diagnosis && (
          <div className="flex flex-col gap-6 p-4 sm:p-6">

            {/* 1. Problem Observed */}
            <section className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <Bug className="h-3.5 w-3.5 text-[var(--color-error-red)]" />
                <span>Problem Observed</span>
              </div>
              <Alert variant="ai" className="border-[var(--accent-purple)]/30 bg-[var(--accent-purple)]/5">
                <AlertCircle className="h-4 w-4 text-[var(--accent-purple)]" />
                <AlertTitle className="text-xs font-semibold text-foreground">
                  Diagnostic Symptom Identified
                </AlertTitle>
                <AlertDescription className="text-xs sm:text-sm leading-relaxed text-foreground/90 mt-1">
                  {diagnosis.problem_observed}
                </AlertDescription>
              </Alert>
            </section>

            <Separator className="bg-border/40" />

            {/* 2. Likely Causes & Root Cause Summary */}
            <section className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <Lightbulb className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
                  <span>Likely Causes &amp; Plausibility</span>
                </div>
                <span className="text-[11px] text-muted-foreground">
                  {diagnosis.likely_causes.length} evaluated
                </span>
              </div>
              <CauseList
                causes={diagnosis.likely_causes}
                rootCauseSummary={diagnosis.root_cause_summary}
                confidenceLevel={diagnosis.confidence_level}
              />
            </section>

            <Separator className="bg-border/40" />

            {/* 3. Proposed Fix & Recommended Steps */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <Wrench className="h-3.5 w-3.5 text-[var(--color-emerald)]" />
                <span>Proposed Rectification &amp; Code Diff</span>
              </div>
              <ProposedFix
                proposedFix={diagnosis.proposed_fix}
                correctedCode={diagnosis.corrected_code}
              />

              {diagnosis.recommended_steps && diagnosis.recommended_steps.length > 0 && (
                <div className="pt-2 space-y-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Recommended Verification Steps
                  </span>
                  <RecommendedSteps steps={diagnosis.recommended_steps} />
                </div>
              )}
            </section>

            <Separator className="bg-border/40" />

            {/* 4. Structured Code Issues (collapsible when more than 2 items) */}
            {diagnosis.code_issues && diagnosis.code_issues.length > 0 && (
              <>
                <section className="space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    <Code2 className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
                    <span>Detected C/C++ Code Issues</span>
                  </div>
                  <CollapsibleSection
                    label={`${diagnosis.code_issues.length} issue${diagnosis.code_issues.length === 1 ? "" : "s"} detected`}
                    count={diagnosis.code_issues.length}
                    defaultOpen={diagnosis.code_issues.length <= 3}
                  >
                    {diagnosis.code_issues.map((issue, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-border/50 bg-card/60 space-y-1.5 transition-colors duration-150 hover:border-border/70"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={
                                issue.severity === "critical" || issue.severity === "high"
                                  ? "error"
                                  : issue.severity === "medium"
                                    ? "warning"
                                    : "outline"
                              }
                              className="text-[9px] uppercase tracking-wider font-mono"
                            >
                              {issue.severity}
                            </Badge>
                            <span className="text-xs font-medium text-foreground capitalize">
                              {issue.kind.replace(/_/g, " ")}
                            </span>
                          </div>
                          {issue.location && (
                            <span className="text-[10px] font-mono text-muted-foreground bg-white/5 px-1.5 py-0.5 rounded border border-border/40">
                              {issue.location}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-foreground/90 leading-relaxed">
                          {issue.description}
                        </p>
                        {issue.evidence && (
                          <div className="p-2 rounded-lg bg-black/20 text-[11px] font-mono text-muted-foreground break-words">
                            {issue.evidence}
                          </div>
                        )}
                        {issue.suggestion && (
                          <p className="text-[11px] text-[var(--color-emerald)] leading-relaxed flex items-start gap-1">
                            <span className="font-semibold shrink-0">Fix:</span>
                            <span>{issue.suggestion}</span>
                          </p>
                        )}
                      </div>
                    ))}
                  </CollapsibleSection>
                </section>
                <Separator className="bg-border/40" />
              </>
            )}

            {/* 5. Parsed Compiler Messages (collapsible) */}
            {diagnosis.compiler_messages && diagnosis.compiler_messages.length > 0 && (
              <>
                <section className="space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    <FileTerminal className="h-3.5 w-3.5 text-[var(--color-warning-amber)]" />
                    <span>Compiler Diagnostics Disassembly</span>
                  </div>
                  <CollapsibleSection
                    label={`${diagnosis.compiler_messages.length} diagnostic${diagnosis.compiler_messages.length === 1 ? "" : "s"}`}
                    count={diagnosis.compiler_messages.length}
                    defaultOpen={diagnosis.compiler_messages.length <= 4}
                  >
                    {diagnosis.compiler_messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-border/50 bg-card/60 space-y-1.5 transition-colors duration-150 hover:border-border/70"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <div className="flex items-center gap-2">
                            {msg.is_root_cause && (
                              <Badge variant="error" className="text-[9px] uppercase tracking-wider font-mono">
                                Root Cause
                              </Badge>
                            )}
                            <Badge variant="outline" className="text-[9px] uppercase tracking-wider font-mono">
                              {msg.message_type.replace(/_/g, " ")}
                            </Badge>
                          </div>
                          {(msg.file || typeof msg.line === "number") && (
                            <span className="text-[10px] font-mono text-muted-foreground">
                              {msg.file || ""}{msg.line ? `:${msg.line}` : ""}{msg.column ? `:${msg.column}` : ""}
                            </span>
                          )}
                        </div>
                        <p className="text-xs font-mono text-foreground/90 leading-relaxed break-words">
                          {msg.message}
                        </p>
                        {msg.suggested_fix && (
                          <p className="text-[11px] text-[var(--color-emerald)] leading-relaxed flex items-start gap-1">
                            <span className="font-semibold shrink-0">Suggestion:</span>
                            <span>{msg.suggested_fix}</span>
                          </p>
                        )}
                      </div>
                    ))}
                  </CollapsibleSection>
                </section>
                <Separator className="bg-border/40" />
              </>
            )}

            {/* 6. Serial Log Events (collapsible) */}
            {diagnosis.serial_log_events && diagnosis.serial_log_events.length > 0 && (
              <>
                <section className="space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    <Terminal className="h-3.5 w-3.5 text-[var(--accent-indigo)]" />
                    <span>Runtime Fault &amp; Serial Events</span>
                  </div>
                  <CollapsibleSection
                    label={`${diagnosis.serial_log_events.length} event${diagnosis.serial_log_events.length === 1 ? "" : "s"} captured`}
                    count={diagnosis.serial_log_events.length}
                    defaultOpen={diagnosis.serial_log_events.length <= 3}
                  >
                    {diagnosis.serial_log_events.map((evt, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-border/50 bg-card/60 space-y-1.5 transition-colors duration-150 hover:border-border/70"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={
                                evt.severity === "critical" || evt.severity === "high"
                                  ? "error"
                                  : evt.severity === "medium"
                                    ? "warning"
                                    : "outline"
                              }
                              className="text-[9px] uppercase tracking-wider font-mono"
                            >
                              {evt.event_type.replace(/_/g, " ")}
                            </Badge>
                            {evt.is_repeated && (
                              <span className="text-[10px] text-[var(--color-warning-amber)] font-mono">
                                (Repeated{evt.repeat_count ? ` ${evt.repeat_count}x` : ""})
                              </span>
                            )}
                          </div>
                          {evt.timestamp && (
                            <span className="text-[10px] font-mono text-muted-foreground">
                              {evt.timestamp}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-foreground/90 leading-relaxed">
                          {evt.message}
                        </p>
                        {evt.evidence && (
                          <div className="p-2 rounded-lg bg-black/20 text-[11px] font-mono text-muted-foreground break-words">
                            {evt.evidence}
                          </div>
                        )}
                        {evt.suggested_action && (
                          <p className="text-[11px] text-[var(--color-emerald)] leading-relaxed flex items-start gap-1">
                            <span className="font-semibold shrink-0">Action:</span>
                            <span>{evt.suggested_action}</span>
                          </p>
                        )}
                      </div>
                    ))}
                  </CollapsibleSection>
                </section>
                <Separator className="bg-border/40" />
              </>
            )}

            {/* 7. Evidence Used & RAG Grounding */}
            {(diagnosis.evidence_used?.length > 0 || diagnosis.datasheet_citations?.length || diagnosis.grounded_summary) && (
              <>
                <section>
                  <EvidencePanel
                    evidence={diagnosis.evidence_used}
                    citations={diagnosis.datasheet_citations}
                    groundedSummary={diagnosis.grounded_summary}
                  />
                </section>
                <Separator className="bg-border/40" />
              </>
            )}

            {/* 8. Risks & Limitations / Follow-up */}
            {(diagnosis.risks_limitations || diagnosis.follow_up_required) && (
              <section className="space-y-3">
                {diagnosis.risks_limitations && (
                  <Alert variant="warning" className="border-[var(--color-warning-amber)]/40 bg-[var(--color-warning-amber)]/10">
                    <AlertTriangle className="h-4 w-4 text-[var(--color-warning-amber)]" />
                    <AlertTitle className="text-xs font-semibold text-[var(--color-warning-amber)]">
                      Potential Risks &amp; Side-Effects
                    </AlertTitle>
                    <AlertDescription className="text-xs sm:text-sm leading-relaxed text-foreground/90 mt-1">
                      {diagnosis.risks_limitations}
                    </AlertDescription>
                  </Alert>
                )}

                {diagnosis.follow_up_required && (
                  <Alert variant="info" className="border-[var(--color-info-blue)]/40 bg-[var(--color-info-blue)]/10">
                    <InfoIcon className="h-4 w-4 text-[var(--color-info-blue)]" />
                    <AlertTitle className="text-xs font-semibold text-[var(--color-info-blue)]">
                      Follow-up Hardware Verification
                    </AlertTitle>
                    <AlertDescription className="text-xs sm:text-sm leading-relaxed text-foreground/90 mt-1">
                      {diagnosis.follow_up_required}
                    </AlertDescription>
                  </Alert>
                )}
              </section>
            )}

            {/* 9. Feedback Rating */}
            {sessionId && onSubmitFeedback && (
              <section className="mt-2 flex items-center justify-between rounded-xl border border-border/50 bg-card/60 backdrop-blur-sm p-3.5 shadow-sm">
                <div>
                  <span className="text-xs font-medium text-foreground">
                    Was this diagnosis accurate?
                  </span>
                  <p className="text-[10px] text-muted-foreground">
                    Helps refine prompt embeddings for your target hardware.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className={`h-8 w-8 p-0 rounded-lg transition-all duration-150 active:scale-95 ${
                          feedback?.rating === 1
                            ? "bg-[var(--color-emerald)]/20 text-[var(--color-emerald)] border border-[var(--color-emerald)]/40 shadow-sm scale-105"
                            : "text-muted-foreground hover:text-[var(--color-emerald)] hover:bg-[var(--color-emerald)]/10 hover:border hover:border-[var(--color-emerald)]/20"
                        }`}
                        onClick={() => onSubmitFeedback(1)}
                        aria-label="Mark diagnosis as helpful"
                        aria-pressed={feedback?.rating === 1}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {feedback?.rating === 1 ? "Marked as helpful" : "Mark as helpful"}
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className={`h-8 w-8 p-0 rounded-lg transition-all duration-150 active:scale-95 ${
                          feedback?.rating === 0
                            ? "bg-[var(--color-error-red)]/20 text-[var(--color-error-red)] border border-[var(--color-error-red)]/40 shadow-sm scale-105"
                            : "text-muted-foreground hover:text-[var(--color-error-red)] hover:bg-[var(--color-error-red)]/10 hover:border hover:border-[var(--color-error-red)]/20"
                        }`}
                        onClick={() => onSubmitFeedback(0)}
                        aria-label="Mark diagnosis as unhelpful"
                        aria-pressed={feedback?.rating === 0}
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {feedback?.rating === 0 ? "Marked as unhelpful" : "Mark as unhelpful"}
                    </TooltipContent>
                  </Tooltip>
                </div>
              </section>
            )}

          </div>
        )}
      </div>
    </div>
  );
}

function InfoIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
